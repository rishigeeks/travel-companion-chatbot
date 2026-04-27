import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from google import genai
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize Gemini Client
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None
    logging.warning("GEMINI_API_KEY not found in environment variables. Application will not function fully.")

# --- Real-World Search Tools ---
# To prevent hallucination, the AI must rely ONLY on these tools.

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
                return json.dumps({"status": "no_results", "message": f"Could not find any live data for '{query}'."})
            return json.dumps({"status": "success", "results": results})
    except Exception as e:
        logging.error(f"Search error: {e}")
        return json.dumps({"status": "error", "message": "The search service is temporarily unavailable."})

# Register tools
tools_list = [search_world_data]

# Strict System Prompt to prevent hallucination
SYSTEM_PROMPT = """You are a highly reliable and factual Travel Companion Chatbot.
Your primary goal is to provide accurate recommendations for restaurants, events, and travel tips ANYWHERE in the world.

CRITICAL RULES (ANTI-HALLUCINATION):
1. You MUST NEVER guess, make up, or hallucinate any restaurants, events, or specific travel facts.
2. You MUST ALWAYS use the 'search_world_data' tool to gather live information from the web before answering.
3. If the tool returns "no_results" or empty data, you MUST honestly tell the user that you couldn't find any information for that query. Do NOT invent a place.
4. Base your final response ONLY on the data returned by the search tool.
5. When providing results, summarize them clearly and mention that these are live search results.
6. Be conversational, polite, and helpful, but remain strictly factual.
"""

# Store chat sessions (in-memory for prototype)
chat_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "Gemini API key is not configured. Please add it to your environment variables."}), 500

    data = request.json
    user_message = data.get('message')
    session_id = data.get('session_id', 'default')

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if session_id not in chat_sessions:
        chat_sessions[session_id] = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=tools_list,
                temperature=0.1, # Low temperature for factual responses
            )
        )

    chat_session = chat_sessions[session_id]

    try:
        response = chat_session.send_message(user_message)
        
        # Check if the response contains text
        if response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"response": "I processed your request using my tools, but I don't have a final text response. Could you rephrase?"})

    except Exception as e:
        logging.error(f"Error during chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Use the PORT environment variable if available (for deployment)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
