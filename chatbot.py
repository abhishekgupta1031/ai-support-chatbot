import random
import json
import os
import re

from nltk.stem import PorterStemmer


# =========================
# NLP SETUP
# =========================

stemmer = PorterStemmer()


def tokenize(text):
    text = text.lower()

    return re.findall(
        r"[a-zA-Z0-9]+",
        text
    )


def stem_words(words):
    return [
        stemmer.stem(word)
        for word in words
    ]


# =========================
# FAQ FILE
# =========================

FAQ_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "faq.json"
)


# =========================
# LOAD FAQs
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


# =========================
# INTENTS
# =========================

intents = {

    "greeting": {
        "keywords": [
            "hello", "hi", "hey", "namaste",
            "hii", "helo", "morning", "afternoon"
        ],
        "responses": [
            "Hello! 👋 How can I help you today?",
            "Hi! Welcome to our AI Support Chatbot.",
            "Hey! 😊 What can I do for you?"
        ]
    },

    "how_are_you": {
        "keywords": [
            "how", "are", "you", "doing",
            "well", "good"
        ],
        "responses": [
            "I'm doing great! Thanks for asking. 😊",
            "I'm good and ready to help you!",
            "I'm doing well. How can I assist you?"
        ]
    },

    "name": {
        "keywords": [
            "name", "called", "who"
        ],
        "responses": [
            "I'm an AI-Powered Customer Support Chatbot. 🤖",
            "You can call me AI Support Assistant."
        ]
    },

    "help": {
        "keywords": [
            "help", "support", "problem",
            "issue", "assist", "assistance"
        ],
        "responses": [
            "Sure! I can help with orders, payments, refunds, delivery and account issues.",
            "Of course! Please describe your problem and I'll try to help."
        ]
    },

    "order": {
        "keywords": [
            "order", "orders", "ordered",
            "purchase", "buy", "bought",
            "shipment", "package",
            "track", "tracking"
        ],
        "responses": [
            "Sure! Please provide your order ID so I can help you.",
            "I can help with your order. Please share your order ID.",
            "Would you like help with order status, cancellation, or an order problem?"
        ]
    },

    "delivery": {
        "keywords": [
            "delivery", "deliver", "arrive",
            "shipping", "ship", "courier",
            "days", "late", "delay"
        ],
        "responses": [
            "Standard delivery usually takes 3–5 business days.",
            "Your delivery time depends on your location and shipping method.",
            "If your delivery is delayed, please provide your order ID."
        ]
    },

    "refund": {
        "keywords": [
            "refund", "refunds", "money",
            "return", "returned", "reimburse"
        ],
        "responses": [
            "I can help with your refund. Please provide your order ID and the reason for the refund.",
            "Refunds are usually processed within 5–7 business days after approval.",
            "If you want to return an order, please provide your order ID."
        ]
    },

    "payment": {
        "keywords": [
            "payment", "pay", "paid", "card",
            "transaction", "charge", "charged",
            "debit", "deducted", "bank"
        ],
        "responses": [
            "If your payment failed, please check your payment details or try another payment method.",
            "If money was deducted but your order was not confirmed, please contact support with your transaction details.",
            "If you have a payment problem, please provide the transaction details."
        ]
    },

    "account": {
        "keywords": [
            "account", "profile", "login",
            "signin", "access", "username"
        ],
        "responses": [
            "I can help with account-related issues. What problem are you facing?",
            "For account problems, please check your registered email and login details."
        ]
    },

    "password": {
        "keywords": [
            "password", "forgot", "reset",
            "forgotten", "change"
        ],
        "responses": [
            "If you forgot your password, use the 'Forgot Password' option on the login page.",
            "You can reset your password using your registered email address."
        ]
    },

    "cancel": {
        "keywords": [
            "cancel", "cancellation",
            "cancelled", "stop"
        ],
        "responses": [
            "I can help with order cancellation. Please provide your order ID.",
            "Orders can usually be cancelled before they are shipped."
        ]
    },

    "thanks": {
        "keywords": [
            "thank", "thanks",
            "thankyou", "thx", "appreciate"
        ],
        "responses": [
            "You're welcome! 😊",
            "Happy to help!",
            "Anytime! 👍"
        ]
    },

    "bye": {
        "keywords": [
            "bye", "goodbye",
            "see", "later", "exit"
        ],
        "responses": [
            "Goodbye! Have a great day! 👋",
            "See you soon!",
            "Thanks for chatting with me!"
        ]
    }
}


# =========================
# CALCULATE SIMILARITY
# =========================

def calculate_score(
    user_words,
    keywords
):

    if not user_words or not keywords:
        return 0

    keyword_words = tokenize(
        " ".join(keywords)
    )

    keyword_stems = stem_words(
        keyword_words
    )

    score = 0.0

    for word in user_words:

        if word in keyword_words:
            score += 1.0
            continue

        word_stem = stemmer.stem(word)

        if word_stem in keyword_stems:
            score += 0.8
            continue

        for keyword in keyword_words:

            if (
                len(word) >= 4
                and len(keyword) >= 4
                and (
                    word in keyword
                    or keyword in word
                )
            ):
                score += 0.4
                break

    return score


# =========================
# FIND FAQ RESPONSE
# =========================

def find_faq_response(message):

    faqs = load_faqs()

    user_words = tokenize(
        message
    )

    if not user_words:
        return None

    best_answer = None
    best_score = 0

    for faq in faqs:

        keywords = faq.get(
            "keywords",
            []
        )

        score = calculate_score(
            user_words,
            keywords
        )

        if score > best_score:

            best_score = score

            best_answer = faq.get(
                "answer"
            )

    if (
        best_answer
        and best_score >= 1.0
    ):
        return best_answer

    return None


# =========================
# FIND BEST INTENT
# =========================

def find_best_intent(message):

    words = tokenize(
        message
    )

    if not words:
        return None, 0

    best_intent = None
    best_score = 0

    for intent, data in intents.items():

        score = calculate_score(
            words,
            data["keywords"]
        )

        if score > best_score:

            best_score = score
            best_intent = intent

    return (
        best_intent,
        best_score
    )


# =========================
# ORDER ID DETECTION
# =========================

def extract_order_id(message):

    """
    Detect actual order IDs only.

    Valid:
    ORD12345
    ORD-12345
    ORD 12345

    ORDER12345
    ORDER-12345
    ORDER 12345

    #12345

    Invalid:
    order problem
    order status
    my order
    """

    patterns = [

        r"\bORD[- ]?[A-Z0-9]{4,}\b",

        r"\bORDER[- ]?[0-9]{4,}\b",

        r"#\d{4,}"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            message,
            re.IGNORECASE
        )

        if match:

            order_id = match.group(0)

            if order_id.lower() in [
                "order",
                "orders"
            ]:
                continue

            return order_id

    return None


# =========================
# CONTEXT RESPONSE
# =========================

def handle_context(
    message,
    context=None
):

    if context is None:
        context = {}

    message_lower = message.lower().strip()

    # ==================================
    # ORDER ID
    # ==================================

    order_id = extract_order_id(
        message
    )

    if order_id:

        context["order_id"] = order_id

        # Important:
        # If user gives an order ID,
        # remember that the current topic
        # is order-related.
        context["last_intent"] = "order"

        return (
            f"Thanks! 👍 I received your "
            f"order ID **{order_id}**.\n\n"
            "I can help you with the order "
            "status, delivery, cancellation, "
            "or other order-related questions."
        )

    # ==================================
    # ORDER STATUS
    # ==================================

    if "status" in message_lower:

        if context.get("order_id"):

            return (
                f"For order "
                f"{context['order_id']}, "
                "please contact support for "
                "the latest real-time status."
            )

        if context.get("last_intent") == "order":

            return (
                "Sure! Please provide your "
                "order ID so I can help you "
                "check the order status."
            )

    # ==================================
    # FOLLOW-UP QUESTIONS
    # ==================================

    if context.get("last_intent"):

        last_intent = context[
            "last_intent"
        ]

        # User says YES

        if message_lower in [
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay"
        ]:

            if last_intent == "order":

                return (
                    "Sure! Please provide your "
                    "order ID so I can help you "
                    "check the order."
                )

            if last_intent == "delivery":

                return (
                    "Sure! Please provide your "
                    "order ID and I'll help you "
                    "with the delivery."
                )

            if last_intent == "refund":

                return (
                    "Sure! Please provide your "
                    "order ID and I'll help you "
                    "with the refund."
                )

            if last_intent == "cancel":

                return (
                    "Sure! Please provide your "
                    "order ID and I'll help you "
                    "with the cancellation."
                )

    return None


# =========================
# MAIN RESPONSE FUNCTION
# =========================

def get_response(
    message,
    context=None
):

    words = tokenize(
        message
    )

    if not words:

        return (
            "Please type a message "
            "so I can help you. 😊"
        )

    if context is None:
        context = {}

    # ==================================
    # STEP 1: CONTEXT
    # ==================================

    context_response = handle_context(
        message,
        context
    )

    if context_response:
        return context_response

    # ==================================
    # STEP 2: FAQ
    # ==================================

    faq_response = find_faq_response(
        message
    )

    if faq_response:
        return faq_response

    # ==================================
    # STEP 3: INTENT
    # ==================================

    best_intent, best_score = find_best_intent(
        message
    )

    if best_intent:

        context["last_intent"] = (
            best_intent
        )

    # ==================================
    # NO INTENT
    # ==================================

    if not best_intent:

        return (
            "I'm not completely sure "
            "what you mean. 🤔\n\n"
            "I can help you with:\n"
            "📦 Orders\n"
            "🚚 Delivery & Order Tracking\n"
            "💰 Refunds & Returns\n"
            "💳 Payments\n"
            "👤 Account Problems\n"
            "🔐 Password Reset\n\n"
            "Please try asking your "
            "question in another way."
        )

    # ==================================
    # CONFIDENCE
    # ==================================

    total_words = len(
        words
    )

    confidence = (
        best_score / total_words
    )

    # ==================================
    # STRONG MATCH
    # ==================================

    if (
        best_score >= 1.5
        or confidence >= 0.50
    ):

        return random.choice(
            intents[
                best_intent
            ]["responses"]
        )

    # ==================================
    # MEDIUM MATCH
    # ==================================

    if (
        best_score >= 0.8
        or confidence >= 0.25
    ):

        return (
            "I think you're asking about "
            f"{best_intent.replace('_', ' ')}. 🤔\n\n"
            + random.choice(
                intents[
                    best_intent
                ]["responses"]
            )
        )

    # ==================================
    # SMART FALLBACK
    # ==================================

    return (
        "I'm not completely sure "
        "what you mean. 🤔\n\n"
        "I can help you with:\n"
        "📦 Orders\n"
        "🚚 Delivery & Order Tracking\n"
        "💰 Refunds & Returns\n"
        "💳 Payments\n"
        "👤 Account Problems\n"
        "🔐 Password Reset\n\n"
        "Please try asking your "
        "question in another way."
    )