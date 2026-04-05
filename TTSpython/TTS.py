import os
import sqlite3
import subprocess
import time
import re
from gtts import gTTS
from fuzzywuzzy import process

from StudentReceiver import StudentReceiver
from TestMonitor import MapAssistant

from FindStudentsInfo import (
    is_schedule_query,
    is_announcement_number_query,
    open_schedule_for_student_2,
    list_announcements_verbally,
    open_announcement_by_number
)

# -------------------------
# Utilities
# -------------------------

def normalize(text):
    return re.sub(r"[^\w\s]", "", text).strip().lower()


# -------------------------
# Database Search (PERSONALIZED)
# -------------------------

def search_database(question_text, cursor, grupa, serie):
    question_lower = question_text.lower()

    if "lab" in question_lower or "laborator" in question_lower:
        cursor.execute("""
            SELECT intrebare, raspuns 
            FROM group_questions
            WHERE grupa = ?
        """, (grupa,))

    elif "series" in question_lower:
        cursor.execute("""
            SELECT intrebare, raspuns 
            FROM series_questions
            WHERE serie = ?
        """, (serie,))

    else:
        cursor.execute("SELECT intrebare, raspuns FROM general_questions")

    rows = cursor.fetchall()
    if not rows:
        return None

    norm_q = normalize(question_text)
    norm_map = {normalize(q): (q, a) for q, a in rows}

    best, score = process.extractOne(norm_q, list(norm_map.keys()))

    
    print(f"[DEBUG] Fuzzy input: {question_text}")
    print(f"[DEBUG] Best match: {best}")
    print(f"[DEBUG] Score: {score}")

    if score > 70:
        return norm_map[best][1]

    return None


# -------------------------
# Response Logic
# -------------------------

def get_response(receiver, conn, mapper, question_text, conversation_state, student_name, grupa, serie):
    cursor = conn.cursor()
    query_lower = question_text.lower().strip()
    print(f"[DEBUG] Processing question: {question_text}")

    # initialize number_str
    number_str = None

    # --- Announcement follow-up ---
    if conversation_state.get("waiting_for_announcement_number", False):
        number_str = is_announcement_number_query(question_text)
        if number_str:
            conversation_state["waiting_for_announcement_number"] = False  
            print(f"[DEBUG] Opening announcement #{number_str}")
            result = open_announcement_by_number(number_str)
            return result if result else "Couldn't open the announcement."
        else:
            # still waiting for number
            print("[DEBUG] Didn't understand the number, still waiting...")
            return "I didn't catch that number. Please say a number like one, two, or three."

    # --- Schedule ---
    if is_schedule_query(question_text):
        print(f"[DEBUG] Schedule detected for {student_name}")
        try:
            result = open_schedule_for_student_2(student_name, conn)
            return result if result else "I couldn't open your schedule."
        except Exception as e:
            print(f"[ERROR] Schedule error: {e}")
            return "There was an error opening your schedule."

    # --- Announcements ---
    if "announcement" in query_lower:
        conversation_state["waiting_for_announcement_number"] = True
        print("[DEBUG] Listing announcements")
        return list_announcements_verbally()

    # --- Map ---
    if "map" in query_lower:
        place_name = re.sub(
            r"\bmap\b|\bshow\b|\bopen\b|\bme\b|\bthe\b|\bplease\b|\bof\b|\bfor\b|\bto\b",
            "",
            query_lower
        ).strip()

        print(f"[DEBUG] Map request: {place_name}")

        if place_name:
            try:
                result = mapper.generate_map(place_name)
                if result:
                    distance, dest_name = result
                    return f"{dest_name} is approximately {distance:.2f} km away. I've opened the map."
                else:
                    return f"I couldn't find {place_name}."
            except Exception as e:
                print(f"[ERROR] Map error: {e}")
                return "Map error occurred."
        else:
            return "What place should I show?"

    # --- Database fallback (PERSONALIZED) ---
    answer = search_database(question_text, cursor, grupa, serie)
    if answer:
        print(f"[DEBUG] DB answer: {answer}")
        return answer

    print("[DEBUG] No response found")
    return "Sorry, I couldn't understand your question."


# -------------------------
# Text-to-Speech
# -------------------------

def speak_response(text):
    try:
        print(f"[DEBUG] Speaking: {text}")

        tts = gTTS(text=text, lang="en")
        tts.save("response.mp3")

        proc = subprocess.Popen(
            ["mpg123", "-q", "-a", "default", "response.mp3"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        proc.wait()

        time.sleep(1.5)

        if os.path.exists("response.mp3"):
            os.remove("response.mp3")

    except Exception as e:
        print(f"[ERROR] TTS error: {e}")


# -------------------------
# Interaction Loop
# -------------------------

def interaction_loop(MAX_IDLE, receiver, student_name, conn, mapper, grupa, serie):
    last_interaction = time.time()
    prompted = False
    conversation_state = {"waiting_for_announcement_number": False}

    while True:
        if time.time() - last_interaction > MAX_IDLE:
            speak_response("Session stopped due to inactivity")
            break

        if not prompted:
            speak_response(f"Hello, {student_name}, how can I help you?")
            prompted = True

        print("[INFO] Listening...")
        audio_data = receiver.record_audio(duration=5)

        if audio_data is None or audio_data.size == 0:
            speak_response("I didn't hear anything.")
            continue

        question_text = receiver.recognize_audio(audio_data)
        print(f"[DEBUG] Recognized: {question_text}")

        if not question_text:
            speak_response("I didn't understand.")
            continue

        if question_text.lower() in ("exit", "stop"):
            speak_response("Goodbye.")
            break

        response = get_response(
            receiver,
            conn,
            mapper,
            question_text,
            conversation_state,
            student_name,
            grupa,
            serie
        )

        if not response:
            response = "Sorry, I couldn't understand the question."

        speak_response(response)

        if not conversation_state.get("waiting_for_announcement_number", False):
            speak_response("Ask another question or say exit.")

        last_interaction = time.time()


# -------------------------
# Main
# -------------------------

def main():
    conn = sqlite3.connect("students_db.db")
    mapper = MapAssistant(start_address="Cluj-Napoca, Romania")
    receiver = None

    try:
        print("[INFO] Initializing Vosk...")
        receiver = StudentReceiver()
        print("[INFO] System ready.")

        while True:
            print("\n[INFO] Waiting for student identification...")
            student_name = receiver.start_listening()

            if not student_name or student_name.strip().lower() == "unknown":
                speak_response("I couldn't identify you. Please try again!")
                continue

            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, grupa, serie 
                FROM students 
                WHERE nume = ?
            """, (student_name,))

            result = cursor.fetchone()

            if result is None:
                speak_response(f"I couldn't find you, {student_name}.")
                continue

            student_id, grupa, serie = result

            print(f"[INFO] Student identified: {student_name}")
            print(f"[DEBUG] Group: {grupa}, Series: {serie}")

            interaction_loop(
                MAX_IDLE=90,
                receiver=receiver,
                student_name=student_name,
                conn=conn,
                mapper=mapper,
                grupa=grupa,
                serie=serie
            )

    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
    finally:
        if receiver:
            receiver.cleanup()
        conn.close()
        print("[INFO] Database connection closed.")


if __name__ == "__main__":
    main()