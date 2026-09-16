from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    session,
    url_for
)

from chatbot import get_response, find_best_intent

import sqlite3
from datetime import datetime, timedelta
import json
import os
import secrets
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")


# =========================================================
# DATABASE
# =========================================================

DB_NAME = "chatbot.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    cursor = conn.cursor()

    # Chat logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            intent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Check whether old database has intent column
    cursor.execute("PRAGMA table_info(chat_logs)")
    columns = [column["name"] for column in cursor.fetchall()]

    if "intent" not in columns:
        cursor.execute("""
            ALTER TABLE chat_logs
            ADD COLUMN intent TEXT
        """)

    # Admin credentials
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # Password reset tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at DATETIME NOT NULL,
            used INTEGER DEFAULT 0
        )
    """)

    # Initialize admin account from .env
    if ADMIN_USERNAME and ADMIN_PASSWORD:

        cursor.execute("""
            SELECT id
            FROM admin_credentials
            WHERE username = ?
        """, (ADMIN_USERNAME,))

        existing_admin = cursor.fetchone()

        if not existing_admin:
            password_hash = generate_password_hash(ADMIN_PASSWORD)

            cursor.execute("""
                INSERT INTO admin_credentials
                (username, password_hash)
                VALUES (?, ?)
            """, (
                ADMIN_USERNAME,
                password_hash
            ))

    conn.commit()
    conn.close()


# =========================================================
# CHAT LOGGING
# =========================================================

def save_chat(user_message, bot_response, intent=None):

    try:
        conn = get_db_connection()

        conn.execute("""
            INSERT INTO chat_logs
            (user_message, bot_response, intent)
            VALUES (?, ?, ?)
        """, (
            user_message,
            bot_response,
            intent
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print("Database logging error:", e)


# =========================================================
# FAQ MANAGEMENT
# =========================================================

FAQ_FILE = os.path.join("data", "faq.json")


def load_faqs():

    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception:
        return []


def save_faqs(faqs):

    os.makedirs("data", exist_ok=True)

    with open(
        FAQ_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            faqs,
            file,
            indent=4,
            ensure_ascii=False
        )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# CHAT API
# =========================================================

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    if not data:
        return jsonify({
            "response": "Please enter a message."
        })

    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "response": "Please enter a message."
        })

    try:

        bot_response = get_response(user_message)

        intent_result = find_best_intent(user_message)

        if isinstance(intent_result, tuple):
            intent = intent_result[0]
        else:
            intent = intent_result

        save_chat(
            user_message,
            bot_response,
            intent
        )

        return jsonify({
            "response": bot_response
        })

    except Exception as e:

        print("Chat error:", e)

        return jsonify({
            "response": "Sorry, something went wrong. Please try again."
        }), 500


# =========================================================
# CLEAR CONTEXT
# =========================================================

@app.route("/clear-context", methods=["POST"])
def clear_context():

    session.pop("chat_context", None)

    return jsonify({
        "success": True,
        "message": "Conversation context cleared."
    })


# =========================================================
# CHAT HISTORY
# =========================================================

@app.route("/history")
def history():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    logs = conn.execute("""
        SELECT *
        FROM chat_logs
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return render_template(
        "history.html",
        logs=logs
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db_connection()

        admin = conn.execute("""
            SELECT *
            FROM admin_credentials
            WHERE username = ?
        """, (username,)).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password_hash"],
            password
        ):

            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(url_for("admin"))

        # Backward compatibility:
        # If database account is not available,
        # allow environment credentials.
        if (
            ADMIN_USERNAME
            and ADMIN_PASSWORD
            and username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(url_for("admin"))

        error = "Invalid username or password."

    return render_template(
        "admin_login.html",
        error=error
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)

    return redirect(url_for("admin_login"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    total_chats = conn.execute("""
        SELECT COUNT(*) AS count
        FROM chat_logs
    """).fetchone()["count"]

    today = datetime.now().strftime("%Y-%m-%d")

    today_chats = conn.execute("""
        SELECT COUNT(*) AS count
        FROM chat_logs
        WHERE DATE(timestamp) = ?
    """, (today,)).fetchone()["count"]

    total_responses = conn.execute("""
        SELECT COUNT(*)
        FROM chat_logs
        WHERE bot_response IS NOT NULL
    """).fetchone()[0]

    recent_chats = conn.execute("""
        SELECT *
        FROM chat_logs
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    # Last 7 days
    daily_labels = []
    daily_counts = []

    for i in range(6, -1, -1):

        date_value = (
            datetime.now() - timedelta(days=i)
        ).strftime("%Y-%m-%d")

        count = conn.execute("""
            SELECT COUNT(*)
            FROM chat_logs
            WHERE DATE(timestamp) = ?
        """, (date_value,)).fetchone()[0]

        daily_labels.append(date_value)
        daily_counts.append(count)

    # Intent analytics
    intent_rows = conn.execute("""
        SELECT
            COALESCE(intent, 'unknown') AS intent,
            COUNT(*) AS count
        FROM chat_logs
        GROUP BY intent
        ORDER BY count DESC
    """).fetchall()

    intent_labels = [
        row["intent"]
        for row in intent_rows
    ]

    intent_counts = [
        row["count"]
        for row in intent_rows
    ]

    conn.close()

    return render_template(
        "admin.html",
        total_chats=total_chats,
        today_chats=today_chats,
        total_responses=total_responses,
        recent_chats=recent_chats,
        daily_labels=json.dumps(daily_labels),
        daily_counts=json.dumps(daily_counts),
        intent_labels=json.dumps(intent_labels),
        intent_counts=json.dumps(intent_counts)
    )


# =========================================================
# ADD FAQ
# =========================================================

@app.route("/admin/add", methods=["POST"])
def add_faq():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    question = request.form.get(
        "question",
        ""
    ).strip()

    answer = request.form.get(
        "answer",
        ""
    ).strip()

    if question and answer:

        faqs = load_faqs()

        faqs.append({
            "question": question,
            "answer": answer
        })

        save_faqs(faqs)

    return redirect(url_for("admin"))


# =========================================================
# DELETE FAQ
# =========================================================

@app.route("/admin/delete/<int:index>")
def delete_faq(index):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    faqs = load_faqs()

    if 0 <= index < len(faqs):

        faqs.pop(index)

        save_faqs(faqs)

    return redirect(url_for("admin"))


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route("/admin/forgot-password", methods=["GET", "POST"])
def forgot_password():

    message = None
    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        if not username:

            error = "Please enter your admin username."

            return render_template(
                "forgot_password.html",
                message=message,
                error=error
            )

        conn = get_db_connection()

        admin = conn.execute("""
            SELECT username
            FROM admin_credentials
            WHERE username = ?
        """, (username,)).fetchone()

        if not admin:

            conn.close()

            error = "Admin account was not found."

            return render_template(
                "forgot_password.html",
                message=message,
                error=error
            )

        # Check email configuration
        if not ADMIN_EMAIL:

            conn.close()

            error = (
                "Password reset email is not configured yet. "
                "Please configure ADMIN_EMAIL in environment variables."
            )

            return render_template(
                "forgot_password.html",
                message=message,
                error=error
            )

        # Generate secure token
        token = secrets.token_urlsafe(32)

        expires_at = (
            datetime.utcnow() + timedelta(minutes=15)
        ).strftime("%Y-%m-%d %H:%M:%S")

        # Invalidate previous unused tokens
        conn.execute("""
            UPDATE password_reset_tokens
            SET used = 1
            WHERE username = ?
            AND used = 0
        """, (username,))

        conn.execute("""
            INSERT INTO password_reset_tokens
            (username, token, expires_at, used)
            VALUES (?, ?, ?, 0)
        """, (
            username,
            token,
            expires_at
        ))

        conn.commit()
        conn.close()

        reset_link = url_for(
            "reset_password",
            token=token,
            _external=True
        )

        email_sent = send_reset_email(
            username,
            reset_link
        )

        if email_sent:

            message = (
                "A password reset link has been sent "
                "to the registered admin email."
            )

        else:

            error = (
                "Unable to send the reset email. "
                "Please check SMTP environment variables."
            )

    return render_template(
        "forgot_password.html",
        message=message,
        error=error
    )


# =========================================================
# SEND RESET EMAIL
# =========================================================

def send_reset_email(username, reset_link):

    if not all([
        SMTP_HOST,
        SMTP_USERNAME,
        SMTP_PASSWORD,
        ADMIN_EMAIL
    ]):
        print("SMTP configuration is incomplete.")
        return False

    try:

        message = EmailMessage()

        message["Subject"] = "AI Support Chatbot - Password Reset"

        message["From"] = SMTP_USERNAME
        message["To"] = ADMIN_EMAIL

        message.set_content(
            f"""
Hello {username},

A password reset was requested for your AI Support Chatbot admin account.

Use the link below to create a new password:

{reset_link}

This link will expire in 15 minutes.

If you did not request this password reset, you can safely ignore this email.

AI Support Chatbot
"""
        )

        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT
        ) as server:

            server.starttls()

            server.login(
                SMTP_USERNAME,
                SMTP_PASSWORD
            )

            server.send_message(message)

        return True

    except Exception as e:

        print("Email sending error:", e)

        return False


# =========================================================
# RESET PASSWORD
# =========================================================

@app.route("/admin/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    conn = get_db_connection()

    reset_record = conn.execute("""
        SELECT *
        FROM password_reset_tokens
        WHERE token = ?
        AND used = 0
    """, (token,)).fetchone()

    if not reset_record:

        conn.close()

        return render_template(
            "reset_password.html",
            error="This password reset link is invalid or has already been used.",
            success=None
        )

    expires_at = datetime.strptime(
        reset_record["expires_at"],
        "%Y-%m-%d %H:%M:%S"
    )

    if datetime.utcnow() > expires_at:

        conn.close()

        return render_template(
            "reset_password.html",
            error="This password reset link has expired.",
            success=None
        )

    error = None
    success = None

    if request.method == "POST":

        new_password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if len(new_password) < 8:

            error = "Password must be at least 8 characters long."

        elif new_password != confirm_password:

            error = "Passwords do not match."

        else:

            password_hash = generate_password_hash(
                new_password
            )

            conn.execute("""
                UPDATE admin_credentials
                SET password_hash = ?
                WHERE username = ?
            """, (
                password_hash,
                reset_record["username"]
            ))

            # Mark token as used
            conn.execute("""
                UPDATE password_reset_tokens
                SET used = 1
                WHERE token = ?
            """, (token,))

            conn.commit()
            conn.close()

            success = (
                "Password changed successfully. "
                "You can now login with your new password."
            )

            return render_template(
                "reset_password.html",
                error=None,
                success=success
            )

    conn.close()

    return render_template(
        "reset_password.html",
        error=error,
        success=success
    )


# =========================================================
# INITIALIZE DATABASE
# =========================================================

init_db()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )