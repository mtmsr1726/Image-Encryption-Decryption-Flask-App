from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_from_directory
)

from encryption import encrypt_image
from decryption import decrypt_image
from database import get_db_connection, init_db

from werkzeug.utils import secure_filename
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

import cv2
import os

from datetime import datetime
from psycopg2 import IntegrityError


# =========================
# FLASK CONFIGURATION
# =========================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-secret-change-this"
)

UPLOAD_FOLDER = "static/uploads"
ENCRYPTED_FOLDER = "static/encrypted"
DECRYPTED_FOLDER = "static/decrypted"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ENCRYPTED_FOLDER, exist_ok=True)
os.makedirs(DECRYPTED_FOLDER, exist_ok=True)


# =========================
# DATABASE INITIALIZATION
# =========================

init_db()


# =========================
# HOME
# =========================

@app.route("/")
def home():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM image_history
            WHERE sender=%s
            """,
            (session["user"],)
        )
        sent_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM image_history
            WHERE receiver=%s
            """,
            (session["user"],)
        )
        received_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM users"
        )
        total_users = cur.fetchone()[0]

    finally:
        conn.close()

    return render_template(
        "index.html",
        username=session["user"],
        sent_count=sent_count,
        received_count=received_count,
        total_users=total_users
    )


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template(
                "register.html",
                error="Passwords do not match"
            )

        if not email.endswith("@gmail.com"):
            return render_template(
                "register.html",
                error="Please enter a valid Gmail address"
            )

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO users(username, email, password)
                VALUES(%s, %s, %s)
                """,
                (username, email, hashed_password)
            )

            conn.commit()

            return redirect("/login")

        except IntegrityError:

            conn.rollback()

            return render_template(
                "register.html",
                error="Username or Email already exists"
            )

        finally:
            conn.close()

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()

        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT *
                FROM users
                WHERE email=%s
                """,
                (email,)
            )

            user = cur.fetchone()

        finally:
            conn.close()

        if user and check_password_hash(user["password"], password):

            session["user"] = user["username"]

            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid Email or Password"
        )

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# SENDER
# =========================

@app.route("/sender", methods=["GET", "POST"])
def sender():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT username
            FROM users
            WHERE username != %s
            """,
            (session["user"],)
        )

        users = cur.fetchall()

    finally:
        conn.close()

    if request.method == "POST":

        if "image" not in request.files:
            return render_template(
                "sender.html",
                users=users,
                error="Please select an image"
            )

        image = request.files["image"]

        receiver = request.form["receiver_username"]
        secret_key = request.form["secret_key"]

        allowed_extensions = {"png", "jpg", "jpeg"}

        if not image.filename or "." not in image.filename:
            return render_template(
                "sender.html",
                users=users,
                error="Please select an image file"
            )

        ext = image.filename.rsplit(".", 1)[1].lower()

        if ext not in allowed_extensions:
            return render_template(
                "sender.html",
                users=users,
                error="Only PNG, JPG and JPEG images are allowed"
            )

        if not secret_key:
            return render_template(
                "sender.html",
                users=users,
                error="Please enter a secret key"
            )

        conn = get_db_connection()

        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT username
                FROM users
                WHERE username=%s
                """,
                (receiver,)
            )

            user = cur.fetchone()

            if not user:
                return render_template(
                    "sender.html",
                    users=users,
                    error="Receiver username not found"
                )

            original_filename = secure_filename(image.filename)

            filepath = os.path.join(
                UPLOAD_FOLDER,
                original_filename
            )

            image.save(filepath)

            encrypted = encrypt_image(
                filepath,
                secret_key
            )

            filename_without_ext = os.path.splitext(
                original_filename
            )[0]

            encrypted_name = (
                "enc_" +
                filename_without_ext +
                ".png"
            )

            encrypted_path = os.path.join(
                ENCRYPTED_FOLDER,
                encrypted_name
            )

            cv2.imwrite(
                encrypted_path,
                cv2.cvtColor(
                    encrypted,
                    cv2.COLOR_RGB2BGR
                )
            )

            cur.execute(
                """
                INSERT INTO images(
                    sender_username,
                    receiver_username,
                    filename,
                    secret_key
                )
                VALUES(%s, %s, %s, %s)
                """,
                (
                    session["user"],
                    receiver,
                    encrypted_name,
                    secret_key
                )
            )

            current_user = session["user"]

            sent_time = datetime.now()

            cur.execute(
                """
                INSERT INTO image_history(
                    sender,
                    receiver,
                    encrypted_filename,
                    original_filename,
                    secret_key,
                    sent_time
                )
                VALUES(%s, %s, %s, %s, %s, %s)
                """,
                (
                    current_user,
                    receiver,
                    encrypted_name,
                    original_filename,
                    secret_key,
                    sent_time
                )
            )

            conn.commit()

            return render_template(
                "result.html",
                message="Image Sent Successfully",
                image_name=encrypted_name,
                image_path="encrypted/" + encrypted_name
            )

        except Exception:
            conn.rollback()
            app.logger.exception("Image sending failed")
            return render_template(
                "sender.html",
                users=users,
                error="Unable to send image. Please try again."
            )

        finally:
            conn.close()

    return render_template(
        "sender.html",
        users=users
    )


# =========================
# RECEIVER
# =========================

@app.route("/receiver", methods=["GET", "POST"])
def receiver():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                encrypted_filename,
                sender,
                sent_time
            FROM image_history
            WHERE receiver=%s
            ORDER BY id DESC
            """,
            (session["user"],)
        )

        images = cur.fetchall()

    finally:
        conn.close()

    if request.method == "POST":

        image_name = request.form["image_name"]
        secret_key = request.form["secret_key"]

        conn = get_db_connection()

        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT *
                FROM images
                WHERE filename=%s
                AND secret_key=%s
                AND receiver_username=%s
                """,
                (
                    image_name,
                    secret_key,
                    session["user"]
                )
            )

            data = cur.fetchone()

        finally:
            conn.close()

        if not data:
            return render_template(
                "receiver.html",
                images=images,
                error="Invalid Secret Key"
            )

        encrypted_path = os.path.join(
            ENCRYPTED_FOLDER,
            image_name
        )

        if not os.path.exists(encrypted_path):
            return render_template(
                "receiver.html",
                images=images,
                error="Encrypted image file not found"
            )

        decrypted = decrypt_image(
            encrypted_path,
            secret_key
        )

        output_name = (
            "dec_" +
            os.path.splitext(image_name)[0] +
            ".png"
        )

        output_path = os.path.join(
            DECRYPTED_FOLDER,
            output_name
        )

        cv2.imwrite(
            output_path,
            cv2.cvtColor(
                decrypted,
                cv2.COLOR_RGB2BGR
            )
        )

        return render_template(
            "result.html",
            message="Image Decrypted Successfully",
            image_name=output_name,
            image_path="decrypted/" + output_name
        )

    return render_template(
        "receiver.html",
        images=images
    )


# =========================
# HISTORY
# =========================

@app.route("/history")
def history():

    if "user" not in session:
        return redirect("/login")

    search = request.args.get("search", "")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM image_history
            WHERE
                (sender=%s OR receiver=%s)
            AND
                (
                    sender LIKE %s
                    OR receiver LIKE %s
                    OR original_filename LIKE %s
                )
            ORDER BY sent_time DESC
            """,
            (
                session["user"],
                session["user"],
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            )
        )

        history = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "history.html",
        history=history,
        search=search
    )


# =========================
# VIEW HISTORY
# =========================

@app.route("/view_history/<int:image_id>")
def view_history(image_id):

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM image_history
            WHERE id=%s
            AND (sender=%s OR receiver=%s)
            """,
            (
                image_id,
                session["user"],
                session["user"]
            )
        )

        image = cur.fetchone()

    finally:
        conn.close()

    if image is None:
        return "Image not found", 404

    if image["sender"] == session["user"]:
        return render_template(
            "view_sent.html",
            image=image
        )

    return render_template(
        "verify_key.html",
        image=image
    )


# =========================
# DECRYPT HISTORY
# =========================

@app.route(
    "/decrypt_history/<int:image_id>",
    methods=["POST"]
)
def decrypt_history(image_id):

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM image_history
            WHERE id=%s
            AND receiver=%s
            """,
            (image_id, session["user"])
        )

        image = cur.fetchone()

    finally:
        conn.close()

    if image is None:
        return "Image not found", 404

    entered_key = request.form["secret_key"]

    if entered_key != image["secret_key"]:
        return render_template(
            "verify_key.html",
            image=image,
            error="❌ Wrong Secret Key"
        )

    encrypted_path = os.path.join(
        ENCRYPTED_FOLDER,
        image["encrypted_filename"]
    )

    if not os.path.exists(encrypted_path):
        return render_template(
            "verify_key.html",
            image=image,
            error="Encrypted image file not found"
        )

    decrypted = decrypt_image(
        encrypted_path,
        entered_key
    )

    decrypted_file = (
        "dec_" +
        os.path.splitext(image["encrypted_filename"])[0] +
        ".png"
    )

    output_path = os.path.join(
        DECRYPTED_FOLDER,
        decrypted_file
    )

    cv2.imwrite(
        output_path,
        cv2.cvtColor(
            decrypted,
            cv2.COLOR_RGB2BGR
        )
    )

    return render_template(
        "view_received.html",
        image=image,
        decrypted_file=decrypted_file
    )


# =========================
# PROFILE
# =========================

@app.route("/profile")
def profile():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM users
            WHERE username=%s
            """,
            (session["user"],)
        )

        user = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM image_history
            WHERE sender=%s
            """,
            (session["user"],)
        )

        sent_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM image_history
            WHERE receiver=%s
            """,
            (session["user"],)
        )

        received_count = cur.fetchone()[0]

    finally:
        conn.close()

    if user is None:
        session.clear()
        return redirect("/login")

    return render_template(
        "profile.html",
        username=user["username"],
        email=user["email"],
        sent_count=sent_count,
        received_count=received_count
    )


# =========================
# STATS
# =========================

@app.route("/stats")
def stats():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM images")
        images = cur.fetchone()[0]

    finally:
        conn.close()

    return render_template(
        "stats.html",
        users=users,
        images=images
    )


# =========================
# DELETE HISTORY
# =========================

@app.route("/delete_history/<int:image_id>")
def delete_history(image_id):

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM image_history
            WHERE id=%s
            AND (sender=%s OR receiver=%s)
            """,
            (
                image_id,
                session["user"],
                session["user"]
            )
        )

        conn.commit()

    finally:
        conn.close()

    return redirect("/history")


# =========================
# FAVICON
# =========================

@app.route("/favicon.ico")
def favicon():

    return send_from_directory(
        "static",
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )


# =========================
# CHECK HISTORY
# =========================

@app.route("/check_history")
def check_history():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM image_history
            WHERE sender=%s OR receiver=%s
            ORDER BY id DESC
            """,
            (session["user"], session["user"])
        )

        rows = cur.fetchall()

    finally:
        conn.close()

    return str(rows)


# =========================
# ERROR HANDLERS
# =========================

@app.errorhandler(404)
def page_not_found(error):

    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):

    return render_template("500.html"), 500


# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True)
