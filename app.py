
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    session,
    url_for
)

from chatbot import (
    get_response,
    find_best_intent
)

import sqlite3
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

load_dotenv()


# =========================
# APPLICATION
# =========================

app = Flask(__name__)


# =========================
# SECURITY CONFIGURATION
# =========================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD"
)


# =========================
# PROJECT PATHS
# =========================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "chatbot.db"
)

FAQ_FILE = os.path.join(
    BASE_DIR,
    "data",
    "faq.json"
)


# =========================
# DATABASE CONNECTION
# =========================

def get_db_connection():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================
# DATABASE INITIALIZATION
# =========================

def init_db():

    conn = get_db_connection()

    cursor = conn.cursor()

    # Create table if it does not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            intent TEXT
        )
    """)

    # Safe migration for existing databases
    cursor.execute("""
        PRAGMA table_info(chat_logs)
    """)

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "intent" not in columns:

        cursor.execute("""
            ALTER TABLE chat_logs
            ADD COLUMN intent TEXT
        """)

    conn.commit()

    conn.close()


# =========================
# SAVE CHAT
# =========================

def save_chat(
    user_message,
    bot_response,
    intent=None
):

    try:

        conn = get_db_connection()

        cursor = conn.cursor()

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute("""
            INSERT INTO chat_logs
            (
                user_message,
                bot_response,
                timestamp,
                intent
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_message,
            bot_response,
            timestamp,
            intent
        ))

        conn.commit()

        conn.close()

        return True

    except sqlite3.Error as error:

        print(
            "Database Error:",
            error
        )

        return False


# =========================
# FAQ FUNCTIONS
# =========================

def load_faqs():

    try:

        with open(
            FAQ_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return data.get(
            "faqs",
            []
        )

    except FileNotFoundError:

        print(
            "FAQ file not found:",
            FAQ_FILE
        )

        return []

    except json.JSONDecodeError:

        print(
            "Invalid JSON format in faq.json"
        )

        return []


def save_faqs(faqs):

    try:

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

    except OSError as error:

        print(
            "FAQ Save Error:",
            error
        )

        return False


# =========================
# HOME
# =========================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================
# CHAT API
# =========================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "response":
                "Invalid request."
            }), 400

        user_message = data.get(
            "message",
            ""
        ).strip()

        if not user_message:

            return jsonify({
                "response":
                "Please type a message."
            }), 400

        context = session.get(
            "chat_context",
            {}
        )

        # Existing chatbot response
        response = get_response(
            user_message,
            context
        )

        session["chat_context"] = context

        session.modified = True


        # =========================
        # DETECT INTENT
        # =========================

        try:

            detected_intent, intent_score = (
                find_best_intent(
                    user_message
                )
            )

        except Exception as intent_error:

            print(
                "Intent Detection Error:",
                intent_error
            )

            detected_intent = None


        # Save chat + intent
        save_chat(
            user_message,
            response,
            detected_intent
        )


        return jsonify({
            "response": response
        })

    except Exception as error:

        print(
            "Chat Error:",
            error
        )

        return jsonify({
            "response":
            "Sorry, something went wrong. Please try again."
        }), 500


# =========================
# CLEAR CHAT CONTEXT
# =========================

@app.route(
    "/clear-context",
    methods=["POST"]
)
def clear_context():

    try:

        session.pop(
            "chat_context",
            None
        )

        session.modified = True

        return jsonify({
            "success": True,
            "message":
            "Conversation context cleared."
        })

    except Exception as error:

        print(
            "Clear Context Error:",
            error
        )

        return jsonify({
            "success": False,
            "message":
            "Unable to clear conversation context."
        }), 500


# =========================
# CHAT HISTORY
# =========================

@app.route("/history")
def history():

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_message,
            bot_response,
            timestamp
        FROM chat_logs
        ORDER BY id DESC
    """)

    chats = cursor.fetchall()

    conn.close()

    return render_template(
        "history.html",
        chats=chats
    )


# =========================
# ADMIN LOGIN
# =========================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            ADMIN_USERNAME
            and ADMIN_PASSWORD
            and username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin")
            )

        return render_template(
            "admin_login.html",
            error="Invalid username or password."
        )

    return render_template(
        "admin_login.html",
        error=None
    )


# =========================
# ADMIN LOGOUT
# =========================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin")
def admin():

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    cursor = conn.cursor()


    # =========================
    # TOTAL CHATS
    # =========================

    cursor.execute("""
        SELECT COUNT(*)
        FROM chat_logs
    """)

    total_chats = cursor.fetchone()[0]


    # =========================
    # TODAY'S CHATS
    # =========================

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    cursor.execute("""
        SELECT COUNT(*)
        FROM chat_logs
        WHERE timestamp LIKE ?
    """, (
        today + "%",
    ))

    today_chats = cursor.fetchone()[0]


    # =========================
    # TOTAL BOT RESPONSES
    # =========================

    cursor.execute("""
        SELECT COUNT(bot_response)
        FROM chat_logs
    """)

    total_responses = cursor.fetchone()[0]


    # =========================
    # RECENT ACTIVITY
    # =========================

    cursor.execute("""
        SELECT
            user_message,
            bot_response,
            timestamp
        FROM chat_logs
        ORDER BY id DESC
        LIMIT 5
    """)

    recent_chats = cursor.fetchall()


    # =========================
    # LAST 7 DAYS ANALYTICS
    # =========================

    daily_labels = []
    daily_counts = []

    for days_ago in range(
        6,
        -1,
        -1
    ):

        date_value = (
            datetime.now()
            - timedelta(days=days_ago)
        )

        date_string = date_value.strftime(
            "%Y-%m-%d"
        )

        display_date = date_value.strftime(
            "%d %b"
        )

        cursor.execute("""
            SELECT COUNT(*)
            FROM chat_logs
            WHERE timestamp LIKE ?
        """, (
            date_string + "%",
        ))

        count = cursor.fetchone()[0]

        daily_labels.append(
            display_date
        )

        daily_counts.append(
            count
        )


    # =========================
    # INTENT ANALYTICS
    # =========================

    cursor.execute("""
        SELECT
            intent,
            COUNT(*) AS count
        FROM chat_logs
        WHERE intent IS NOT NULL
        AND intent != ''
        GROUP BY intent
        ORDER BY count DESC
    """)

    intent_rows = cursor.fetchall()

    intent_labels = []
    intent_counts = []

    for row in intent_rows:

        intent_labels.append(
            row["intent"].replace(
                "_",
                " "
            ).title()
        )

        intent_counts.append(
            row["count"]
        )


    conn.close()


    # =========================
    # FAQ DATA
    # =========================

    faqs = load_faqs()

    total_faqs = len(faqs)


    # =========================
    # RENDER DASHBOARD
    # =========================

    return render_template(
        "admin.html",

        faqs=faqs,

        total_chats=total_chats,

        today_chats=today_chats,

        total_responses=total_responses,

        total_faqs=total_faqs,

        recent_chats=recent_chats,

        daily_labels=daily_labels,

        daily_counts=daily_counts,

        intent_labels=intent_labels,

        intent_counts=intent_counts
    )


# =========================
# ADD FAQ
# =========================

@app.route(
    "/admin/add",
    methods=["POST"]
)
def add_faq():

    if not session.get(
        "admin_logged_in"
    ):

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


    if (
        not question
        or not keywords_text
        or not answer
    ):

        return redirect(
            url_for("admin")
        )


    keywords = [

        keyword.strip()

        for keyword
        in keywords_text.split(",")

        if keyword.strip()

    ]


    if not keywords:

        return redirect(
            url_for("admin")
        )


    faqs = load_faqs()


    faqs.append({

        "question": question,

        "keywords": keywords,

        "answer": answer

    })


    save_faqs(
        faqs
    )


    return redirect(
        url_for("admin")
    )


# =========================
# DELETE FAQ
# =========================

@app.route(
    "/admin/delete/<int:index>",
    methods=["POST"]
)
def delete_faq(index):

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    faqs = load_faqs()


    if 0 <= index < len(faqs):

        faqs.pop(index)

        save_faqs(
            faqs
        )


    return redirect(
        url_for("admin")
    )


# =========================
# START APPLICATION
# =========================

# Initialize database when the
# application starts, including Gunicorn.
init_db()


if __name__ == "__main__":

    app.run(
        debug=True
    )