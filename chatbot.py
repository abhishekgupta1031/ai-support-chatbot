import random
import json
import os
import re

from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


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
            "hello",
            "hi",
            "hey",
            "namaste",
            "hii",
            "helo",
            "morning",
            "afternoon"
        ],

        "responses": [
            "Hello! 👋 How can I help you today?",
            "Hi! Welcome to our AI Support Chatbot.",
            "Hey! 😊 What can I do for you?"
        ]
    },

    "how_are_you": {
        "keywords": [
            "how",
            "are",
            "you",
            "doing",
            "well",
            "good"
        ],

        "responses": [
            "I'm doing great! Thanks for asking. 😊",
            "I'm good and ready to help you!",
            "I'm doing well. How can I assist you?"
        ]
    },

    "name": {
        "keywords": [
            "name",
            "called",
            "who"
        ],

        "responses": [
            "I'm an AI-Powered Customer Support Chatbot. 🤖",
            "You can call me AI Support Assistant."
        ]
    },

    "help": {
        "keywords": [
            "help",
            "support",
            "problem",
            "issue",
            "assist",
            "assistance"
        ],

        "responses": [
            "Sure! I can help with orders, payments, refunds, delivery and account issues.",
            "Of course! Please describe your problem and I'll try to help."
        ]
    },

    "order": {
        "keywords": [
            "order",
            "orders",
            "ordered",
            "purchase",
            "buy",
            "bought",
            "shipment",
            "package",
            "track",
            "tracking"
        ],

        "responses": [
            "Sure! Please provide your order ID so I can help you.",
            "I can help with your order. Please share your order ID.",
            "Would you like help with order status, cancellation, or an order problem?"
        ]
    },

    "delivery": {
        "keywords": [
            "delivery",
            "deliver",
            "arrive",
            "shipping",
            "ship",
            "courier",
            "days",
            "late",
            "delay"
        ],

        "responses": [
            "Standard delivery usually takes 3–5 business days.",
            "Your delivery time depends on your location and shipping method.",
            "If your delivery is delayed, please provide your order ID."
        ]
    },

    "refund": {
        "keywords": [
            "refund",
            "refunds",
            "money",
            "return",
            "returned",
            "reimburse"
        ],

        "responses": [
            "I can help with your refund. Please provide your order ID and the reason for the refund.",
            "Refunds are usually processed within 5–7 business days after approval.",
            "If you want to return an order, please provide your order ID."
        ]
    },

    "payment": {
        "keywords": [
            "payment",
            "pay",
            "paid",
            "card",
            "transaction",
            "charge",
            "charged",
            "debit",
            "deducted",
            "bank"
        ],

        "responses": [
            "If your payment failed, please check your payment details or try another payment method.",
            "If money was deducted but your order was not confirmed, please contact support with your transaction details.",
            "If you have a payment problem, please provide the transaction details."
        ]
    },

    "account": {
        "keywords": [
            "account",
            "profile",
            "login",
            "signin",
            "access",
            "username"
        ],

        "responses": [
            "I can help with account-related issues. What problem are you facing?",
            "For account problems, please check your registered email and login details."
        ]
    },

    "password": {
        "keywords": [
            "password",
            "forgot",
            "reset",
            "forgotten",
            "change"
        ],

        "responses": [
            "If you forgot your password, use the 'Forgot Password' option on the login page.",
            "You can reset your password using your registered email address."
        ]
    },

    "cancel": {
        "keywords": [
            "cancel",
            "cancellation",
            "cancelled",
            "stop"
        ],

        "responses": [
            "I can help with order cancellation. Please provide your order ID.",
            "Orders can usually be cancelled before they are shipped."
        ]
    },

    "thanks": {
        "keywords": [
            "thank",
            "thanks",
            "thankyou",
            "thx",
            "appreciate"
        ],

        "responses": [
            "You're welcome! 😊",
            "Happy to help!",
            "Anytime! 👍"
        ]
    },

    "bye": {
        "keywords": [
            "bye",
            "goodbye",
            "see",
            "later",
            "exit"
        ],

        "responses": [
            "Goodbye! Have a great day! 👋",
            "See you soon!",
            "Thanks for chatting with me!"
        ]
    }
}


# =========================
# PREPARE TF-IDF MODEL
# =========================

intent_names = list(intents.keys())

intent_documents = [
    " ".join(intents[intent]["keywords"])
    for intent in intent_names
]

vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),
    sublinear_tf=True
)

intent_vectors = vectorizer.fit_transform(
    intent_documents
)


# =========================
# TF-IDF INTENT MATCHING
# =========================

def find_tfidf_intent(message):

    if not message.strip():
        return None, 0.0

    user_vector = vectorizer.transform(
        [message.lower()]
    )

    similarities = cosine_similarity(
        user_vector,
        intent_vectors
    )[0]

    best_index = similarities.argmax()

    best_score = float(
        similarities[best_index]
    )

    return (
        intent_names[best_index],
        best_score
    )


# =========================
# KEYWORD SIMILARITY
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

    if not faqs:
        return None

    faq_questions = []
    faq_answers = []

    for faq in faqs:

        question = faq.get(
            "question",
            ""
        )

        if question:

            faq_questions.append(
                question
            )

            faq_answers.append(
                faq.get(
                    "answer",
                    ""
                )
            )

    if not faq_questions:
        return None

    try:

        faq_vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True
        )

        faq_vectors = faq_vectorizer.fit_transform(
            faq_questions
        )

        user_vector = faq_vectorizer.transform(
            [message]
        )

        similarities = cosine_similarity(
            user_vector,
            faq_vectors
        )[0]

        best_index = similarities.argmax()

        best_score = float(
            similarities[best_index]
        )

        if best_score >= 0.35:

            return faq_answers[
                best_index
            ]

    except ValueError:
        pass

    # Keyword fallback

    user_words = tokenize(
        message
    )

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
# ORDER ID DETECTION
# =========================

def extract_order_id(message):

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
# SMART CONTEXT RESPONSE
# =========================

def handle_context(
    message,
    context=None
):

    if context is None:
        context = {}

    message_lower = message.lower().strip()

    # =========================
    # ORDER ID
    # =========================

    order_id = extract_order_id(
        message
    )

    if order_id:

        context["order_id"] = order_id
        context["last_intent"] = "order"
        context["last_message"] = message

        return (
            f"Thanks! 👍 I received your "
            f"order ID **{order_id}**.\n\n"
            "I can help you with the order "
            "status, delivery, cancellation, "
            "refund, or other order-related questions."
        )

    # =========================
    # ORDER STATUS
    # =========================

    if any(
        word in message_lower
        for word in [
            "status",
            "where is my order",
            "where's my order",
            "track my order",
            "track order",
            "tracking"
        ]
    ):

        if context.get("order_id"):

            context["last_intent"] = "order"
            context["last_message"] = message

            return (
                f"For order "
                f"{context['order_id']}, "
                "please contact support for "
                "the latest real-time status."
            )

        if context.get("last_intent") == "order":

            context["last_message"] = message

            return (
                "Sure! Please provide your "
                "order ID so I can help you "
                "check the order status."
            )

    # =========================
    # ORDER + DELIVERY
    # =========================

    if any(
        word in message_lower
        for word in [
            "delivery",
            "delivered",
            "arrive",
            "shipping",
            "shipment",
            "courier"
        ]
    ):

        if context.get("order_id"):

            context["last_intent"] = "delivery"
            context["last_message"] = message

            return (
                f"For order "
                f"{context['order_id']}, "
                "standard delivery usually "
                "takes 3–5 business days. "
                "For the latest delivery update, "
                "please contact support."
            )

    # =========================
    # ORDER + REFUND
    # =========================

    if any(
        word in message_lower
        for word in [
            "refund",
            "return",
            "money back",
            "reimburse"
        ]
    ):

        if context.get("order_id"):

            context["last_intent"] = "refund"
            context["last_message"] = message

            return (
                f"I can help with the refund "
                f"for order {context['order_id']}. "
                "Please provide the reason for "
                "the refund so support can assist you."
            )

    # =========================
    # ORDER + CANCELLATION
    # =========================

    if any(
        word in message_lower
        for word in [
            "cancel",
            "cancellation",
            "cancelled"
        ]
    ):

        if context.get("order_id"):

            context["last_intent"] = "cancel"
            context["last_message"] = message

            return (
                f"I can help with cancellation "
                f"for order {context['order_id']}. "
                "Orders can usually be cancelled "
                "before they are shipped."
            )

    # =========================
    # GENERIC FOLLOW-UP
    # =========================

    follow_up_messages = [
        "what about it",
        "what about that",
        "and it",
        "and that",
        "what about this",
        "tell me more",
        "more information",
        "more info",
        "what next",
        "then what",
        "now what"
    ]

    if message_lower in follow_up_messages:

        last_intent = context.get(
            "last_intent"
        )

        if last_intent == "order":

            if context.get("order_id"):

                return (
                    f"For order "
                    f"{context['order_id']}, "
                    "I can help with status, "
                    "delivery, refund, or cancellation."
                )

            return (
                "I can help with your order. "
                "Please provide your order ID."
            )

        if last_intent == "delivery":

            return (
                "For delivery assistance, "
                "please provide your order ID."
            )

        if last_intent == "refund":

            return (
                "For refund assistance, "
                "please provide your order ID "
                "and the reason for the refund."
            )

        if last_intent == "cancel":

            return (
                "For cancellation assistance, "
                "please provide your order ID."
            )

    # =========================
    # YES / CONFIRMATION
    # =========================

    if message_lower in [
        "yes",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "please do",
        "yes please"
    ]:

        last_intent = context.get(
            "last_intent"
        )

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

    # =========================
    # SAVE LAST MESSAGE
    # =========================

    context["last_message"] = message

    return None


# =========================
# BEST INTENT
# =========================

def find_best_intent(message):

    words = tokenize(
        message
    )

    if not words:
        return None, 0

    # Traditional keyword score

    keyword_best_intent = None
    keyword_best_score = 0

    for intent, data in intents.items():

        score = calculate_score(
            words,
            data["keywords"]
        )

        if score > keyword_best_score:

            keyword_best_score = score
            keyword_best_intent = intent

    # Advanced TF-IDF score

    tfidf_intent, tfidf_score = (
        find_tfidf_intent(
            message
        )
    )

    # Combine both methods

    if keyword_best_intent is None:

        return (
            tfidf_intent,
            tfidf_score
        )

    if tfidf_score >= 0.35:

        if (
            tfidf_intent
            == keyword_best_intent
        ):

            combined_score = (
                keyword_best_score
                + tfidf_score
            )

            return (
                keyword_best_intent,
                combined_score
            )

        return (
            tfidf_intent,
            tfidf_score
        )

    return (
        keyword_best_intent,
        keyword_best_score
    )


# =========================
# MAIN RESPONSE
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

    # =========================
    # STEP 1: CONTEXT
    # =========================

    context_response = handle_context(
        message,
        context
    )

    if context_response:
        return context_response

    # =========================
    # STEP 2: FAQ
    # =========================

    faq_response = find_faq_response(
        message
    )

    if faq_response:

        context["last_message"] = message

        return faq_response

    # =========================
    # STEP 3: INTENT
    # =========================

    best_intent, best_score = (
        find_best_intent(
            message
        )
    )

    if best_intent:

        context["last_intent"] = (
            best_intent
        )

        context["last_message"] = message

    # =========================
    # NO INTENT
    # =========================

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

    # =========================
    # CONFIDENCE
    # =========================

    total_words = len(
        words
    )

    confidence = (
        best_score / max(
            total_words,
            1
        )
    )

    # =========================
    # STRONG MATCH
    # =========================

    if (
        best_score >= 1.5
        or confidence >= 0.50
    ):

        return random.choice(
            intents[
                best_intent
            ]["responses"]
        )

    # =========================
    # MEDIUM MATCH
    # =========================

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

    # =========================
    # SMART FALLBACK
    # =========================

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