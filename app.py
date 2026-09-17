from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from chatbot import get_response, find_best_intent
import sqlite3
from datetime import datetime, timedelta
import json
import os
import secrets
import resend
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.environ.get(
    "RESEND_FROM_EMAIL",
    "onboarding@resend.dev"
)

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

DB_NAME = "chatbot.db"
FAQ_FILE = os.path.join("data", "faq.json")


# ========================= DATABASE =========================

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            intent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(chat_logs)")
    columns = [row["name"] for row in cursor.fetchall()]

    if "intent" not in columns:
        cursor.execute(
            "ALTER TABLE chat_logs ADD COLUMN intent TEXT"
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at DATETIME NOT NULL,
            used INTEGER DEFAULT 0
        )
    """)

    if ADMIN_USERNAME and ADMIN_PASSWORD:
        admin = cursor.execute(
            """
            SELECT id
            FROM admin_credentials
            WHERE username = ?
            """,
            (ADMIN_USERNAME,)
        ).fetchone()

        if not admin:
            cursor.execute(
                """
                INSERT INTO admin_credentials
                (username, password_hash)
                VALUES (?, ?)
                """,
                (
                    ADMIN_USERNAME,
                    generate_password_hash(ADMIN_PASSWORD)
                )
            )

    conn.commit()
    conn.close()


def save_chat(user_message, bot_response, intent=None):
    try:
        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO chat_logs
            (user_message, bot_response, intent)
            VALUES (?, ?, ?)
            """,
            (
                user_message,
                bot_response,
                intent
            )
        )

        conn.commit()
        conn.close()

    except Exception as e:
        print("Database logging error:", e)


# ========================= FAQ MANAGEMENT =========================

def load_faqs():
    try:
        os.makedirs(
            os.path.dirname(FAQ_FILE),
            exist_ok=True
        )

        if not os.path.exists(FAQ_FILE):
            return []

        with open(
            FAQ_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, dict):
            faqs = data.get("faqs", [])

            if isinstance(faqs, list):
                return faqs

            return []

        if isinstance(data, list):
            return data

        return []

    except json.JSONDecodeError:
        print("Invalid JSON format in faq.json")
        return []

    except Exception as e:
        print("FAQ loading error:", e)
        return []


def save_faqs(faqs):
    try:
        os.makedirs(
            os.path.dirname(FAQ_FILE),
            exist_ok=True
        )

        if not isinstance(faqs, list):
            faqs = []

        with open(
            FAQ_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                {
                    "faqs": faqs
                },
                file,
                indent=4,
                ensure_ascii=False
            )

        return True

    except Exception as e:
        print("FAQ save error:", e)
        return False


# ========================= HOME / CHAT =========================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data:
        return jsonify({
            "response": "Please enter a message."
        })

    user_message = data.get(
        "message",
        ""
    ).strip()

    if not user_message:
        return jsonify({
            "response": "Please enter a message."
        })

    try:
        bot_response = get_response(
            user_message
        )

        intent_result = find_best_intent(
            user_message
        )

        intent = (
            intent_result[0]
            if isinstance(intent_result, tuple)
            else intent_result
        )

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
            "response":
                "Sorry, something went wrong. Please try again."
        }), 500


@app.route("/clear-context", methods=["POST"])
def clear_context():
    session.pop(
        "chat_context",
        None
    )

    return jsonify({
        "success": True,
        "message": "Conversation context cleared."
    })


# ========================= HISTORY =========================

@app.route("/history")
def history():
    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    logs = conn.execute(
        """
        SELECT *
        FROM chat_logs
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    conn.close()

    return render_template(
        "history.html",
        logs=logs
    )


# ========================= ADMIN LOGIN =========================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(
            url_for("admin")
        )

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

        admin = conn.execute(
            """
            SELECT *
            FROM admin_credentials
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if (
            admin
            and check_password_hash(
                admin["password_hash"],
                password
            )
        ):
            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(
                url_for("admin")
            )

        if (
            ADMIN_USERNAME
            and ADMIN_PASSWORD
            and username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):
            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(
                url_for("admin")
            )

        error = "Invalid username or password."

    return render_template(
        "admin_login.html",
        error=error
    )


@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    session.pop(
        "admin_username",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ========================= ADMIN DASHBOARD =========================

@app.route("/admin")
def admin():

    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    total_chats = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM chat_logs
        """
    ).fetchone()["count"]

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    today_chats = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM chat_logs
        WHERE DATE(timestamp) = ?
        """,
        (today,)
    ).fetchone()["count"]

    total_responses = conn.execute(
        """
        SELECT COUNT(*)
        FROM chat_logs
        WHERE bot_response IS NOT NULL
        """
    ).fetchone()[0]

    recent_chats = conn.execute(
        """
        SELECT *
        FROM chat_logs
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    daily_labels = []
    daily_counts = []

    for i in range(6, -1, -1):

        date_value = (
            datetime.now()
            - timedelta(days=i)
        ).strftime("%Y-%m-%d")

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM chat_logs
            WHERE DATE(timestamp) = ?
            """,
            (date_value,)
        ).fetchone()[0]

        daily_labels.append(
            date_value
        )

        daily_counts.append(
            count
        )

    intent_rows = conn.execute(
        """
        SELECT
            COALESCE(intent, 'unknown') AS intent,
            COUNT(*) AS count
        FROM chat_logs
        GROUP BY intent
        ORDER BY count DESC
        """
    ).fetchall()

    intent_labels = [
        row["intent"]
        for row in intent_rows
    ]

    intent_counts = [
        row["count"]
        for row in intent_rows
    ]

    conn.close()

    faqs = load_faqs()

    return render_template(
        "admin.html",
        faqs=faqs,
        total_chats=total_chats,
        today_chats=today_chats,
        total_responses=total_responses,
        recent_chats=recent_chats,
        daily_labels=json.dumps(
            daily_labels
        ),
        daily_counts=json.dumps(
            daily_counts
        ),
        intent_labels=json.dumps(
            intent_labels
        ),
        intent_counts=json.dumps(
            intent_counts
        )
    )


# ========================= ADD FAQ =========================

@app.route(
    "/admin/add",
    methods=["POST"]
)
def add_faq():

    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    question = request.form.get(
        "question",
        ""
    ).strip()

    keywords_text = request.form.get(
        "keywords",
        ""
    ).strip()

    answer = request.form.get(
        "answer",
        ""
    ).strip()

    if not question or not answer:
        return redirect(
            url_for("admin")
        )

    keywords = [
        keyword.strip()
        for keyword in keywords_text.split(",")
        if keyword.strip()
    ]

    faqs = load_faqs()

    if not isinstance(faqs, list):
        faqs = []

    faqs.append({
        "question": question,
        "keywords": keywords,
        "answer": answer
    })

    save_faqs(faqs)

    return redirect(
        url_for("admin")
    )


# ========================= DELETE FAQ =========================

@app.route(
    "/admin/delete/<int:index>",
    methods=["POST"]
)
def delete_faq(index):

    if not session.get("admin_logged_in"):
        return redirect(
            url_for("admin_login")
        )

    faqs = load_faqs()

    if 0 <= index < len(faqs):

        faqs.pop(index)

        save_faqs(faqs)

    return redirect(
        url_for("admin")
    )


# ========================= FORGOT PASSWORD =========================

@app.route(
    "/admin/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    message = None
    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        if not username:
            return render_template(
                "forgot_password.html",
                message=None,
                error="Please enter your admin username."
            )

        conn = get_db_connection()

        admin = conn.execute(
            """
            SELECT username
            FROM admin_credentials
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if not admin:
            conn.close()

            return render_template(
                "forgot_password.html",
                message=None,
                error="Admin account was not found."
            )

        if not ADMIN_EMAIL:
            conn.close()

            return render_template(
                "forgot_password.html",
                message=None,
                error=(
                    "Password reset email is not configured. "
                    "Please check ADMIN_EMAIL in Render."
                )
            )

        if not RESEND_API_KEY:
            conn.close()

            return render_template(
                "forgot_password.html",
                message=None,
                error=(
                    "Resend email service is not configured. "
                    "Please check RESEND_API_KEY in Render."
                )
            )

        token = secrets.token_urlsafe(32)

        expires_at = (
            datetime.utcnow()
            + timedelta(minutes=15)
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn.execute(
            """
            UPDATE password_reset_tokens
            SET used = 1
            WHERE username = ?
            AND used = 0
            """,
            (username,)
        )

        conn.execute(
            """
            INSERT INTO password_reset_tokens
            (
                username,
                token,
                expires_at,
                used
            )
            VALUES (?, ?, ?, 0)
            """,
            (
                username,
                token,
                expires_at
            )
        )

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

            try:
                cleanup_conn = get_db_connection()

                cleanup_conn.execute(
                    """
                    UPDATE password_reset_tokens
                    SET used = 1
                    WHERE token = ?
                    """,
                    (token,)
                )

                cleanup_conn.commit()
                cleanup_conn.close()

            except Exception as cleanup_error:
                print(
                    "Token cleanup error:",
                    cleanup_error
                )

            error = (
                "Unable to send the reset email. "
                "Please check the Resend configuration."
            )

    return render_template(
        "forgot_password.html",
        message=message,
        error=error
    )


# ========================= SEND RESET EMAIL =========================

def send_reset_email(
    username,
    reset_link
):

    if not RESEND_API_KEY:
        print(
            "RESEND_API_KEY is missing."
        )
        return False

    try:

        response = resend.Emails.send({
            "from": RESEND_FROM_EMAIL,
            "to": [ADMIN_EMAIL],
            "subject": "AI Support Chatbot - Password Reset",
            "html": f"""
                <div style="
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: auto;
                    padding: 30px;
                    border: 1px solid #e5e7eb;
                    border-radius: 12px;
                ">

                    <h2>
                        AI Support Chatbot
                    </h2>

                    <p>
                        Hello <strong>{username}</strong>,
                    </p>

                    <p>
                        A password reset was requested
                        for your admin account.
                    </p>

                    <p>
                        Click the button below to
                        create a new password:
                    </p>

                    <p>
                        <a href="{reset_link}"
                           style="
                               display: inline-block;
                               padding: 12px 20px;
                               background: #4f46e5;
                               color: white;
                               text-decoration: none;
                               border-radius: 8px;
                               font-weight: bold;
                           ">
                           Reset Password
                        </a>
                    </p>

                    <p>
                        This link will expire in
                        <strong>15 minutes</strong>.
                    </p>

                    <p>
                        If you did not request this
                        password reset, you can safely
                        ignore this email.
                    </p>

                    <hr>

                    <p style="color: #6b7280;">
                        AI Support Chatbot
                    </p>

                </div>
            """
        })

        print(
            "Resend email response:",
            response
        )

        return True

    except Exception as e:

        print(
            "Resend email error:",
            e
        )

        return False


# ========================= RESET PASSWORD =========================

@app.route(
    "/admin/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    conn = get_db_connection()

    reset_record = conn.execute(
        """
        SELECT *
        FROM password_reset_tokens
        WHERE token = ?
        AND used = 0
        """,
        (token,)
    ).fetchone()

    if not reset_record:

        conn.close()

        return render_template(
            "reset_password.html",
            error=(
                "This password reset link is invalid "
                "or has already been used."
            ),
            success=None
        )

    try:

        expires_at = datetime.strptime(
            reset_record["expires_at"],
            "%Y-%m-%d %H:%M:%S"
        )

    except ValueError:

        conn.close()

        return render_template(
            "reset_password.html",
            error="Invalid password reset link.",
            success=None
        )

    if datetime.utcnow() > expires_at:

        conn.close()

        return render_template(
            "reset_password.html",
            error=(
                "This password reset link has expired."
            ),
            success=None
        )

    error = None

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

            error = (
                "Password must be at least "
                "8 characters long."
            )

        elif new_password != confirm_password:

            error = (
                "Passwords do not match."
            )

        else:

            password_hash = (
                generate_password_hash(
                    new_password
                )
            )

            conn.execute(
                """
                UPDATE admin_credentials
                SET password_hash = ?
                WHERE username = ?
                """,
                (
                    password_hash,
                    reset_record["username"]
                )
            )

            conn.execute(
                """
                UPDATE password_reset_tokens
                SET used = 1
                WHERE token = ?
                """,
                (token,)
            )

            conn.commit()
            conn.close()

            return render_template(
                "reset_password.html",
                error=None,
                success=(
                    "Password changed successfully. "
                    "You can now login with your new password."
                )
            )

    conn.close()

    return render_template(
        "reset_password.html",
        error=error,
        success=None
    )


# ========================= START APPLICATION =========================

init_db()


if __name__ == "__main__":
    app.run(debug=True)