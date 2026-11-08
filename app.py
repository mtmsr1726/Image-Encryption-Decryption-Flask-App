from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_from_directory,
    url_for,
)

from encryption import encrypt_image
from decryption import decrypt_image
from database import get_db_connection, init_db
from supabase_storage import upload_file, download_file

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from psycopg2 import IntegrityError
from datetime import datetime
from uuid import uuid4

import cv2
import os


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-secret-change-this"
)

UPLOAD_FOLDER = "static/uploads"
ENCRYPTED_FOLDER = "static/encrypted"
DECRYPTED_FOLDER = "static/decrypted"

for folder in (UPLOAD_FOLDER, ENCRYPTED_FOLDER, DECRYPTED_FOLDER):
    os.makedirs(folder, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

BUCKET_NAME = "aegispix-images"

# Initialize PostgreSQL database
init_db()


# =========================================================
# STORAGE HELPERS
# =========================================================

def storage_object_path(category, filename):
    return f"{category}/{filename}"


def ensure_local_file(storage_path, local_path):

    if not os.path.exists(local_path):

        os.makedirs(
            os.path.dirname(local_path),
            exist_ok=True
        )

        download_file(
            storage_path,
            local_path
        )

    return local_path


def upload_to_storage(local_path, category, filename):

    object_path = storage_object_path(
        category,
        filename
    )

    upload_file(
        local_path,
        object_path
    )

    return object_path


def allowed_image(filename):

    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_encrypted_local_path(filename):

    safe_name = secure_filename(filename)

    local_path = os.path.join(
        ENCRYPTED_FOLDER,
        safe_name
    )

    object_path = storage_object_path(
        "encrypted",
        safe_name
    )

    return ensure_local_file(
        object_path,
        local_path
    )


# =========================================================
# HOME
# =========================================================

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


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not username or not email or not password:

            return render_template(
                "register.html",
                error="Please fill in all fields"
            )

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


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

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

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user"] = user["username"]

            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid Email or Password"
        )

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================================================
# SENDER
# =========================================================

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
            ORDER BY username
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

        receiver = request.form.get(
            "receiver_username", ""
        ).strip()

        secret_key = request.form.get(
            "secret_key", ""
        )

        if not allowed_image(image.filename):

            return render_template(
                "sender.html",
                users=users,
                error="Only PNG, JPG and JPEG images are allowed"
            )

        if not receiver:

            return render_template(
                "sender.html",
                users=users,
                error="Please select a receiver"
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

            receiver_user = cur.fetchone()

            if not receiver_user:

                return render_template(
                    "sender.html",
                    users=users,
                    error="Receiver username not found"
                )

            # Generate unique filenames

            original_filename = secure_filename(
                image.filename
            )

            extension = original_filename.rsplit(
                ".", 1
            )[1].lower()

            unique_id = uuid4().hex

            stored_original_name = (
                f"{unique_id}.{extension}"
            )

            original_path = os.path.join(
                UPLOAD_FOLDER,
                stored_original_name
            )

            image.save(original_path)

            # Encrypt image

            encrypted = encrypt_image(
                original_path,
                secret_key
            )

            encrypted_name = (
                f"enc_{unique_id}.png"
            )

            encrypted_path = os.path.join(
                ENCRYPTED_FOLDER,
                encrypted_name
            )

            written = cv2.imwrite(
                encrypted_path,
                cv2.cvtColor(
                    encrypted,
                    cv2.COLOR_RGB2BGR
                )
            )

            if not written:
                raise RuntimeError(
                    "Could not write encrypted image"
                )

            # Upload encrypted image to Supabase

            upload_to_storage(
                encrypted_path,
                "encrypted",
                encrypted_name
            )

            # Upload original image to Supabase

            upload_to_storage(
                original_path,
                "original",
                stored_original_name
            )

            sent_time = datetime.now()

            # Insert into images table

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

            # Insert into history table

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
                    session["user"],
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

            app.logger.exception(
                "Image sending failed"
            )

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


# =========================================================
# RECEIVER
# =========================================================

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

        image_name = secure_filename(
            request.form.get("image_name", "")
        )

        secret_key = request.form.get(
            "secret_key", ""
        )

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

            image_data = cur.fetchone()

        finally:

            conn.close()

        if not image_data:

            return render_template(
                "receiver.html",
                images=images,
                error="Invalid Secret Key"
            )

        try:

            # Download encrypted image if not cached locally

            encrypted_path = get_encrypted_local_path(
                image_name
            )

            # Decrypt image

            decrypted = decrypt_image(
                encrypted_path,
                secret_key
            )

            output_name = (
                "dec_"
                + os.path.splitext(image_name)[0]
                + ".png"
            )

            output_path = os.path.join(
                DECRYPTED_FOLDER,
                output_name
            )

            written = cv2.imwrite(
                output_path,
                cv2.cvtColor(
                    decrypted,
                    cv2.COLOR_RGB2BGR
                )
            )

            if not written:
                raise RuntimeError(
                    "Could not write decrypted image"
                )

            # Upload decrypted image to Supabase

            upload_to_storage(
                output_path,
                "decrypted",
                output_name
            )

            return render_template(
                "result.html",
                message="Image Decrypted Successfully",
                image_name=output_name,
                image_path="decrypted/" + output_name
            )

        except Exception:

            app.logger.exception(
                "Image decryption failed"
            )

            return render_template(
                "receiver.html",
                images=images,
                error="Unable to decrypt image. Please try again."
            )

    return render_template(
        "receiver.html",
        images=images
    )


# =========================================================
# HISTORY
# =========================================================

@app.route("/history")
def history():

    if "user" not in session:
        return redirect("/login")

    search = request.args.get(
        "search", ""
    ).strip()

    conn = get_db_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT *
            FROM image_history
            WHERE (sender=%s OR receiver=%s)
            AND (
                sender ILIKE %s
                OR receiver ILIKE %s
                OR original_filename ILIKE %s
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

        history_rows = cur.fetchall()

    finally:

        conn.close()

    return render_template(
        "history.html",
        history=history_rows,
        search=search
    )


# =========================================================
# VIEW HISTORY
# =========================================================

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

    try:

        get_encrypted_local_path(
            image["encrypted_filename"]
        )

    except Exception:

        app.logger.exception(
            "Could not retrieve historical image"
        )

        return "Image file is temporarily unavailable", 503

    if image["sender"] == session["user"]:

        return render_template(
            "view_sent.html",
            image=image
        )

    return render_template(
        "verify_key.html",
        image=image
    )


# =========================================================
# DECRYPT HISTORY
# =========================================================

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
            (
                image_id,
                session["user"]
            )
        )

        image = cur.fetchone()

    finally:

        conn.close()

    if image is None:
        return "Image not found", 404

    entered_key = request.form.get(
        "secret_key", ""
    )

    if entered_key != image["secret_key"]:

        return render_template(
            "verify_key.html",
            image=image,
            error="❌ Wrong Secret Key"
        )

    try:

        encrypted_path = get_encrypted_local_path(
            image["encrypted_filename"]
        )

        decrypted = decrypt_image(
            encrypted_path,
            entered_key
        )

        decrypted_file = (
            "dec_"
            + os.path.splitext(
                image["encrypted_filename"]
            )[0]
            + ".png"
        )

        output_path = os.path.join(
            DECRYPTED_FOLDER,
            decrypted_file
        )

        written = cv2.imwrite(
            output_path,
            cv2.cvtColor(
                decrypted,
                cv2.COLOR_RGB2BGR
            )
        )

        if not written:
            raise RuntimeError(
                "Could not write decrypted image"
            )

        upload_to_storage(
            output_path,
            "decrypted",
            decrypted_file
        )

        return render_template(
            "view_received.html",
            image=image,
            decrypted_file=decrypted_file
        )

    except Exception:

        app.logger.exception(
            "Historical image decryption failed"
        )

        return render_template(
            "verify_key.html",
            image=image,
            error="Unable to decrypt image. Please try again."
        )


# =========================================================
# PROFILE
# =========================================================

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


# =========================================================
# STATS
# =========================================================

@app.route("/stats")
def stats():

    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    try:

        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM users"
        )

        users_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM images"
        )

        images_count = cur.fetchone()[0]

    finally:

        conn.close()

    return render_template(
        "stats.html",
        users=users_count,
        images=images_count
    )


# =========================================================
# DELETE HISTORY
# =========================================================

@app.route(
    "/delete_history/<int:image_id>",
    methods=["GET", "POST"]
)
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


# =========================================================
# FAVICON
# =========================================================

@app.route("/favicon.ico")
def favicon():

    return send_from_directory(
        "static",
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )


# =========================================================
# CHECK HISTORY
# =========================================================

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
            (
                session["user"],
                session["user"]
            )
        )

        rows = cur.fetchall()

    finally:

        conn.close()

    return str(rows)


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "500.html"
    ), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)
