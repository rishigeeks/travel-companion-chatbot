import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
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

# --- Mock APIs (Tools) ---
# To prevent hallucination, the AI must rely ONLY on these tools.

def search_restaurants(location: str, cuisine: str = "") -> str:
    """Searches for restaurants in a given location.
    
    Args:
        location: The city or area to search in.
        cuisine: Optional type of food (e.g., Italian, Mexican).
    """
    logging.info(f"API CALL: search_restaurants(location='{location}', cuisine='{cuisine}')")
    
    # Mock database
    mock_db = {
        "new york": [
            {"name": "Joe's Pizza", "cuisine": "Italian", "rating": 4.8, "price": "$"},
            {"name": "Le Bernardin", "cuisine": "French", "rating": 4.9, "price": "$$$$"}
        ],
        "tokyo": [
            {"name": "Sukiyabashi Jiro", "cuisine": "Japanese", "rating": 4.9, "price": "$$$$"},
            {"name": "Ichiran Ramen", "cuisine": "Japanese", "rating": 4.7, "price": "$$"}
        ]
    }
    
    loc_key = location.lower()
    if loc_key in mock_db:
        results = mock_db[loc_key]
        if cuisine:
            results = [r for r in results if cuisine.lower() in r["cuisine"].lower()]
        
        if not results:
            return json.dumps({"status": "no_results", "message": f"No {cuisine} restaurants found in {location}."})
        return json.dumps({"status": "success", "results": results})
    
    return json.dumps({"status": "no_results", "message": f"Could not find any restaurant data for {location}."})

def search_events(location: str, date: str = "") -> str:
    """Searches for upcoming events in a given location.
    
    Args:
        location: The city or area to search in.
        date: Optional date (e.g., 'today', 'this weekend').
    """
    logging.info(f"API CALL: search_events(location='{location}', date='{date}')")
    
    mock_db = {
        "new york": [
            {"name": "Broadway Show: Hamilton", "date": "tonight", "type": "Theater"},
            {"name": "Central Park SummerStage", "date": "this weekend", "type": "Music"}
        ],
        "london": [
            {"name": "West End: Les Misérables", "date": "tonight", "type": "Theater"},
            {"name": "Premier League Match", "date": "this weekend", "type": "Sports"}
        ]
    }
    
    loc_key = location.lower()
    if loc_key in mock_db:
        return json.dumps({"status": "success", "results": mock_db[loc_key]})
    
    return json.dumps({"status": "no_results", "message": f"Could not find any event data for {location}."})

def get_travel_tips(location: str) -> str:
    """Gets travel tips, customs, and etiquette for a destination.
    
    Args:
        location: The destination city or country.
    """
    logging.info(f"API CALL: get_travel_tips(location='{location}')")
    
    mock_db = {
        "tokyo": ["Tipping is not customary and can be considered rude.", "Always take off your shoes when entering someone's home.", "Stand on the left on escalators."],
        "paris": ["Always say 'Bonjour' when entering a shop.", "Don't speak too loudly in public transport.", "The service charge is usually included in restaurant bills."]
    }
    
    loc_key = location.lower()
    if loc_key in mock_db:
        return json.dumps({"status": "success", "tips": mock_db[loc_key]})
    
    return json.dumps({"status": "no_results", "message": f"No travel tips available for {location}."})

# Register tools
tools_list = [search_restaurants, search_events, get_travel_tips]

# Strict System Prompt to prevent hallucination
SYSTEM_PROMPT = """You are a highly reliable and factual Travel Companion Chatbot.
Your primary goal is to provide accurate recommendations for restaurants, events, and travel tips.

CRITICAL RULES (ANTI-HALLUCINATION):
1. You MUST NEVER guess, make up, or hallucinate any restaurants, events, or specific travel facts.
2. You MUST ALWAYS use the provided tools (search_restaurants, search_events, get_travel_tips) to gather information before answering.
3. If the user asks for restaurants or events, you must call the relevant tool.
4. If the tool returns "no_results" or empty data, you MUST honestly tell the user that you couldn't find any information for that query. Do NOT invent a place.
5. Base your final response ONLY on the data returned by the tools.
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
    app.run(debug=True, port=5000)
