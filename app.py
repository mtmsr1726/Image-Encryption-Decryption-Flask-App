        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM images")
        images_count = cur.fetchone()[0]
    finally:
        conn.close()

    return render_template(
        "stats.html",
        users=users_count,
        images=images_count,
    )


# =========================================================
# DELETE HISTORY
# =========================================================

@app.route("/delete_history/<int:image_id>", methods=["GET", "POST"])
def delete_history(image_id):
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Only delete a history row belonging to the logged-in user.
        cur.execute(
            """
            DELETE FROM image_history
            WHERE id=%s AND (sender=%s OR receiver=%s)
            """,
            (image_id, session["user"], session["user"]),
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
        mimetype="image/vnd.microsoft.icon",
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
            (session["user"], session["user"]),
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
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
