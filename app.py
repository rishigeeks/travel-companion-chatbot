import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from groq import Groq
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-dev-key')

# --- Database Setup (SQLite for local testing/ephemeral cloud) ---
# NOTE: On Render Free Tier, this database is deleted every time the server restarts.
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'

logging.basicConfig(level=logging.INFO)

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    conversations = db.relationship('Conversation', backref='author', lazy=True)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, default="New Chat")
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10), nullable=False) # 'user' or 'bot'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize Database
with app.app_context():
    db.create_all()

# --- Initialize Groq Client ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None
    logging.warning("GROQ_API_KEY not found in environment variables.")

# --- Real-World Search Tools ---
INTERNAL_KNOWLEDGE = {
    "manali": [
        {"name": "Johnson Cafe", "specialty": "Trout & Live Music", "vibe": "Rustic"},
        {"name": "Cafe 1947", "specialty": "Italian & Riverside view", "vibe": "Vintage"},
        {"name": "The Lazy Dog", "specialty": "Multi-cuisine", "vibe": "Relaxed riverside"}
    ],
    "delhi": [
        {"name": "United Coffee House", "specialty": "Classic Indian & European", "vibe": "Royal/Heritage"},
        {"name": "Diggin", "specialty": "Italian", "vibe": "Floral/Aesthetic"},
        {"name": "Ama Cafe", "specialty": "Tibetan Breakfast & Desserts", "vibe": "Cozy/Majnu ka Tilla"}
    ]
}

def search_world_data(query: str) -> list:
    """Searches the live web for factual information with an internal failsafe."""
    clean_query = query.lower().replace("suggest me", "").replace("find me", "").replace("tell me about", "").strip()
    
    # Check internal knowledge first
    for city in INTERNAL_KNOWLEDGE:
        if city in clean_query:
            logging.info(f"INTERNAL KNOWLEDGE HIT: {city}")
            return INTERNAL_KNOWLEDGE[city]
            
    # Fallback to web search
    search_term = f"best {clean_query}" if ("cafes" in clean_query or "restaurants" in clean_query) else clean_query
    logging.info(f"WEB SEARCH CALL: {search_term}")
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(search_term, max_results=5)]
            return results
    except Exception as e:
        logging.error(f"Search error: {e}")
        return []

SYSTEM_PROMPT = """You are a highly reliable and factual Travel Companion Chatbot named Tripster.
Your primary goal is to provide accurate recommendations for restaurants, events, and travel tips ANYWHERE in the world.

RULES:
1. ALWAYS try to use live data first if available.
2. If live search results are empty or unavailable, you MUST use your own internal AI training data to provide high-quality recommendations. 
3. FORMATTING IS CRITICAL: Your answers must be extremely readable for all age groups (especially young learners).
4. Use **bolding** for names, use bullet points for lists, and keep paragraphs very short (1-2 sentences).
5. Use emojis to make the text fun and approachable!
6. Ensure you suggest at least 3-5 great spots for any city requested.
"""

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

# -- Auth Routes --
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
        
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, password=hashed_password)
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    return jsonify({"success": True, "username": user.username})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and bcrypt.check_password_hash(user.password, password):
        login_user(user)
        return jsonify({"success": True, "username": user.username})
    else:
        return jsonify({"error": "Login Unsuccessful. Please check username and password"}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"success": True})

@app.route('/api/user', methods=['GET'])
def get_user():
    if current_user.is_authenticated:
        return jsonify({"logged_in": True, "username": current_user.username})
    return jsonify({"logged_in": False})

# -- History Routes --
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.date_posted.desc()).all()
    return jsonify([{"id": c.id, "title": c.title, "date": c.date_posted.strftime("%Y-%m-%d %H:%M")} for c in conversations])

@app.route('/api/conversations/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    conversation = Conversation.query.get_or_404(conv_id)
    if conversation.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.timestamp).all()
    return jsonify([{"role": m.role, "content": m.content} for m in messages])

# -- Main Chat Route --
@app.route('/api/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "GROQ_API_KEY not configured."}), 500

    data = request.json
    user_message = data.get('message')
    conv_id = data.get('conversation_id') # Can be null for new chat

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # History tracking context
    messages_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation = None

    if current_user.is_authenticated:
        if conv_id:
            conversation = Conversation.query.get(conv_id)
            if conversation and conversation.user_id == current_user.id:
                # Load previous messages for context
                past_messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.timestamp).all()
                for m in past_messages:
                    # Groq roles are 'user' or 'assistant'
                    role = "assistant" if m.role == "bot" else "user"
                    messages_history.append({"role": role, "content": m.content})
        
        # Create new conversation if needed
        if not conversation:
            # Generate a simple title from the first message
            title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            conversation = Conversation(title=title, author=current_user)
            db.session.add(conversation)
            db.session.commit()
            
        # Save user message
        new_msg = Message(role='user', content=user_message, conversation_id=conversation.id)
        db.session.add(new_msg)
        db.session.commit()

    try:
        # Step 1: Get search results first (Simple RAG approach for reliability)
        search_results = search_world_data(user_message)
        context = "Here are the search results for the user's query:\n" + json.dumps(search_results)
        
        messages_history.append({"role": "system", "content": context})
        messages_history.append({"role": "user", "content": user_message})

        # Step 2: Send to Groq
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_history,
            temperature=0.2
        )
        
        bot_response = completion.choices[0].message.content
        
        # Save bot response if authenticated
        if current_user.is_authenticated and conversation:
            bot_msg = Message(role='bot', content=bot_response, conversation_id=conversation.id)
            db.session.add(bot_msg)
            db.session.commit()
        
        response_data = {"response": bot_response}
        if current_user.is_authenticated and conversation:
            response_data["conversation_id"] = conversation.id
            
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error during chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
