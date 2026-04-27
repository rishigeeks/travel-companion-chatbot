import os
import json
import logging
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize Gemini Client
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Using 'gemini-pro' for maximum compatibility
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        system_instruction="""You are a highly reliable and factual Travel Companion Chatbot.
Your primary goal is to provide accurate recommendations for restaurants, events, and travel tips ANYWHERE in the world.

CRITICAL RULES (ANTI-HALLUCINATION):
1. You MUST NEVER guess, make up, or hallucinate any restaurants, events, or specific travel facts.
2. You MUST ALWAYS use the 'search_world_data' tool to gather live information from the web before answering.
3. If the tool returns "no_results" or empty data, you MUST honestly tell the user that you couldn't find any information for that query. Do NOT invent a place.
4. Base your final response ONLY on the data returned by the search tool.
5. When providing results, summarize them clearly and mention that these are live search results.
6. Be conversational, polite, and helpful, but remain strictly factual.
"""
    )
else:
    model = None
    logging.warning("GEMINI_API_KEY not found in environment variables. Application will not function fully.")

# --- Real-World Search Tools ---
def search_world_data(query: str) -> str:
    """Searches the live web for factual information about restaurants, events, or travel tips.
    
    Args:
        query: A specific search query (e.g., 'best restaurants in Manali', 'upcoming events in London').
    """
    logging.info(f"WEB SEARCH CALL: {query}")
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            if not results:
                return {"status": "no_results", "message": f"Could not find any live data for '{query}'."}
            return {"status": "success", "results": results}
    except Exception as e:
        logging.error(f"Search error: {e}")
        return {"status": "error", "message": "The search service is temporarily unavailable."}

# Store chat sessions
chat_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not model:
        return jsonify({"error": "Gemini API key is not configured."}), 500

    data = request.json
    user_message = data.get('message')
    session_id = data.get('session_id', 'default')

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if session_id not in chat_sessions:
        # Note: gemini-pro (1.0) handles tools slightly differently in the old SDK
        # We will use the standard chat for now
        chat_sessions[session_id] = model.start_chat(history=[], enable_automatic_function_calling=True)

    chat_session = chat_sessions[session_id]

    try:
        response = chat_session.send_message(user_message, tools=[search_world_data])
        return jsonify({"response": response.text})

    except Exception as e:
        logging.error(f"Error during chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
