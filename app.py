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
def search_world_data(query: str) -> list:
    """Searches the live web for factual information."""
    logging.info(f"WEB SEARCH CALL: {query}")
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return results
    except Exception as e:
        logging.error(f"Search error: {e}")
        return []

SYSTEM_PROMPT = """You are a highly reliable and factual Travel Companion Chatbot.
Your primary goal is to provide accurate recommendations for restaurants, events, and travel tips ANYWHERE in the world.

CRITICAL RULES (ANTI-HALLUCINATION):
1. You MUST NEVER guess, make up, or hallucinate any restaurants, events, or specific travel facts.
2. ALWAYS base your final response ONLY on real-world facts. 
3. If the user asks for a recommendation, I will provide you with search results. Use ONLY those results.
4. If no results are found, honestly tell the user you couldn't find information for that query.
5. Be conversational, but remain strictly factual.
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
            model="llama-3.1-70b-versatile",
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
