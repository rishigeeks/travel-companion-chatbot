import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from groq import Groq
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize Groq Client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None
    logging.warning("GROQ_API_KEY not found in environment variables.")

# --- Real-World Search Tools ---
# --- Internal Knowledge Base (Failsafe) ---
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "GROQ_API_KEY not configured."}), 500

    data = request.json
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    try:
        # Step 1: Get search results first (Simple RAG approach for reliability)
        search_results = search_world_data(user_message)
        context = "Here are the search results for the user's query:\n" + json.dumps(search_results)
        
        # Step 2: Send to Groq
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": context},
                {"role": "user", "content": user_message}
            ],
            temperature=0.2
        )
        
        return jsonify({"response": completion.choices[0].message.content})

    except Exception as e:
        logging.error(f"Error during chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
