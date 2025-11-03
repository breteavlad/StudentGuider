import os
import sqlite3
from gtts import gTTS
from fuzzywuzzy import process
from StudentReceiver import StudentReceiver
import time
import re
from TestMonitor import MapAssistant
from RomanianStreetMatcher import RomanianStreetMatcher
# Import announcement functions
from FindStudentsInfo import (
    is_schedule_query, 
    is_announcement_query, 
    is_announcement_number_query,
    open_schedule,
    list_announcements_verbally,
    open_announcement_by_number,
    open_announcement_by_keyword
)

def normalize(text):
    return re.sub(r"[^\w\s]", "", text).strip().lower()

def search_database(question_text, cursor):
    """Search the database for an answer to the question"""
    if "lab" in question_text or "laborator" in question_text:
        cursor.execute("SELECT intrebare, raspuns FROM group_questions")
    elif "curs" in question_text:
        cursor.execute("SELECT intrebare, raspuns FROM series_questions")
    else:
        cursor.execute("SELECT intrebare, raspuns FROM general_questions")

    rows = cursor.fetchall()
    if not rows:
        return None

    norm_q = normalize(question_text)
    norm_map = {normalize(q): (q, a) for q, a in rows}
    if not norm_map:
        return None

    best, score = process.extractOne(norm_q, list(norm_map.keys()))
    print(f"[DEBUG] Best match: '{best}' (score={score})")
    
    if score > 70:
        return norm_map[best][1]
    return None


def getResponseFromDB(receiver, conn, mapper, question_text, conversation_state):
    """
    Process a recognized question and return appropriate response.
    question_text: Already recognized text from audio
    conversation_state: Dict to track if we're in announcement selection mode
    """
    cursor = conn.cursor()
    print(f"[DEBUG] Processing question: '{question_text}'")
    
    if not question_text.strip():
        return None

    # Check if user is selecting an announcement by number
    if conversation_state.get('waiting_for_announcement_number', False):
        number_str = is_announcement_number_query(question_text)
        if number_str:
            conversation_state['waiting_for_announcement_number'] = False
            return open_announcement_by_number(number_str)
        # If not a number but they said something else, process as new query
        conversation_state['waiting_for_announcement_number'] = False

    # Check for schedule query FIRST
    if is_schedule_query(question_text):
        return open_schedule()
    
    # Check for announcement query BEFORE database search
    if is_announcement_query(question_text):
        query_lower = question_text.lower()
        
        # Check for specific announcement keywords that should trigger keyword search
        announcement_topics = ["deepmind", "deep mind", "results", "bursa", "scholarship", 
                              "volunteer", "grant", "esc", "best", "registration", "chestionar"]
        
        has_topic = any(topic in query_lower for topic in announcement_topics)
        
        # If asking about a specific topic, search by keyword
        if has_topic:
            # Extract the main keyword
            for topic in announcement_topics:
                if topic in query_lower:
                    return open_announcement_by_keyword(topic)
        
        # Generic announcement request with question words
        if any(phrase in query_lower for phrase in ["what are", "show me", "list", "tell me about"]):
            conversation_state['waiting_for_announcement_number'] = True
            return list_announcements_verbally()
        
        # If contains "announcement" word explicitly, search by keyword
        if "announcement" in query_lower:
            for phrase in ["announcement about", "announcement for", "announcement regarding"]:
                if phrase in query_lower:
                    keyword = query_lower.split(phrase)[-1].strip()
                    if keyword:
                        return open_announcement_by_keyword(keyword)
            
            # Default: list all announcements
            conversation_state['waiting_for_announcement_number'] = True
            return list_announcements_verbally()
        
        # If we detected it as announcement query but no specific pattern, 
        # treat the whole question as keyword search
        return open_announcement_by_keyword(question_text)

    # Location queries
    is_location_query = (
        "where" in question_text.lower() or
        ("is the" in question_text.lower() and any(word in question_text.lower() for word in ["nearest", "closest"])) or
        ("are the" in question_text.lower() and any(word in question_text.lower() for word in ["nearest", "closest", "restroom", "bathroom", "parking"]))
    )
    
    if is_location_query:
        place_name = question_text.lower()
        
        patterns = [
            r"\bwhere can i find\b", r"\bwhere do i find\b", r"\bwhere is\b", r"\bwhere's\b",
            r"\bwhere are\b", r"\bwhere\b", r"\bis the\b", r"\bare the\b", r"\bfind me\b", 
            r"\bshow me\b", r"\btell me where\b", r"\bthe\b", r"\ba\b", r"\ban\b", 
            r"\bin cluj\b", r"\bnear me\b", r"\bplease\b",
            r"\bnearest\b", r"\bclosest\b"
        ]

        for pattern in patterns:
            place_name = re.sub(pattern, "", place_name)

        place_name = re.sub(r"\s+", " ", place_name).strip()
        place_name = re.sub(r"\b(or|and)\s*$", "", place_name).strip()
        
        corrections = {
            r"\b(sports? )?guy\b": "hall",
            r"\bgym or sports hall\b": "gym",
            r"\bparking lot\b": "parking",
            r"\brestrooms?\b": "bathroom",
            r"\btoilets?\b": "bathroom",
        }
        
        for pattern, replacement in corrections.items():
            place_name = re.sub(pattern, replacement, place_name)
        
        place_name = re.sub(r"\s+", " ", place_name).strip()
        print(f"[DEBUG] Cleaned place name: '{place_name}'")

        if len(place_name) < 2:
            return "Sorry, I didn't catch the location you're looking for. Could you please repeat that?"
        
        search_attempts = []
        if " or " in place_name:
            alternatives = [alt.strip() for alt in place_name.split(" or ") if len(alt.strip()) >= 2]
            search_attempts.extend(alternatives)
            print(f"[DEBUG] Will try alternatives: {alternatives}")
        else:
            search_attempts.append(place_name)
        
        print(f"[DEBUG] Detected location query. Searching for location...")
        
        try:
            distance = None
            found_place = None
            
            for attempt in search_attempts:
                print(f"[DEBUG] Trying: '{attempt}'")
                result = mapper.generate_map(attempt)
                if result:
                    distance, dest_name = result
                    found_place = dest_name
                    break
            
            if distance is not None and found_place:
                response = f"{found_place} is approximately {distance:.2f} kilometers away. I've opened the map for you."
                print(f"[DEBUG] Location response: {response}")
                return response
            else:
                print(f"[DEBUG] Location not found on map, searching database...")
                db_response = search_database(question_text, cursor)
                if db_response:
                    return db_response
                else:
                    return f"Sorry, I couldn't find information about {place_name}."
        except Exception as e:
            print(f"[ERROR] Map generation failed: {e}")
            import traceback
            traceback.print_exc()
            db_response = search_database(question_text, cursor)
            if db_response:
                return db_response
            else:
                return f"Sorry, I encountered an error while searching for {place_name}."
    
    # Only search database as last resort
    return search_database(question_text, cursor)

def speak_response(text):
    try:
        print(f"[DEBUG] Speaking: '{text}'")
        tts = gTTS(text=text, lang="en")
        tts.save("response.mp3")
        os.system("mpg123 response.mp3")
        os.remove("response.mp3")
    except Exception as e:
        print(f"[ERROR] TTS error: {e}")


def interactionTTS(MAX_IDLE, receiver, studentName, conn, mapper):
    last_interaction = time.time()
    prompted = False
    conversation_state = {'waiting_for_announcement_number': False}
    
    while True:
        if time.time() - last_interaction > MAX_IDLE:
            speak_response("Session stopped due to inactivity")
            break
            
        if not prompted:
            speak_response(f"Hello, {studentName}, how can I help you?")
            prompted = True
            
        # Record audio
        audio_data = receiver.record_audio(duration=5)
        
        # Recognize the question ONCE
        question_text = receiver.recognize_audio(audio_data)
        print(f"[DEBUG] Recognized in main loop: '{question_text}'")
        
        # Check for exit commands early
        if question_text and question_text.lower().strip() in ("exit", "stop", "la revedere"):
            speak_response("La revedere")
            break
        
        # Announce search for location queries
        if question_text and ("where" in question_text.lower() or 
                              "nearest" in question_text.lower() or 
                              "closest" in question_text.lower()):
            speak_response("Let me search for that location.")
        
        # Get response with conversation state
        response_text = getResponseFromDB(receiver, conn, mapper, question_text, conversation_state)
        
        if not response_text:
            response_text = "Sorry I couldn't understand the question. Please try again."
            speak_response(response_text)
        else:
            speak_response(response_text)
            
            # Only ask for another question if not waiting for announcement selection
            if not conversation_state.get('waiting_for_announcement_number', False):
                speak_response("Please ask me another question or say exit if you want to finish our conversation.")
        
        last_interaction = time.time()


def main():
    conn = sqlite3.connect("students_db.db")
    mapper = MapAssistant(start_address="Cluj-Napoca, Romania")
    receiver = None

    try:
        print("[INFO] Initializing Vosk (Romanian model)...")
        receiver = StudentReceiver()
        print("[INFO] System ready. Waiting for pipe data...")

        while True:
            cursor = conn.cursor()
            print("\n[INFO] Waiting for student identification...")
            studentName = receiver.start_listening()

            if not studentName or studentName.strip().lower() == "unknown":
                speak_response("I couldn't identify you. Please try again!")
                continue

            cursor.execute("SELECT id FROM students WHERE nume = ?", (studentName,))
            if cursor.fetchone() is None:
                speak_response(f"I couldn't find you in the database, {studentName}. Please try again!")
                continue

            print(f"[INFO] Student identificat: {studentName}")
            interactionTTS(90, receiver, studentName, conn, mapper)

    except KeyboardInterrupt:
        print("\n[INFO] Închidere aplicație...")
    finally:
        if receiver:
            receiver.cleanup()
        conn.close()
        print("[INFO] Conexiunea la baza de date a fost închisă.")


if __name__ == "__main__":
    main()