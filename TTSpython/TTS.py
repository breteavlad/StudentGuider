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
    open_schedule,
    list_announcements_verbally,
    open_announcement_by_number
)

# -------------------------
# Utilities
# -------------------------

def normalize(text):
    return re.sub(r"[^\w\s]", "", text).strip().lower()


def search_database(question_text, cursor):
    question_lower = question_text.lower()
    if "lab" in question_lower or "laborator" in question_lower:
        cursor.execute("SELECT intrebare, raspuns FROM group_questions")
    elif "curs" in question_lower:
        cursor.execute("SELECT intrebare, raspuns FROM series_questions")
    else:
        cursor.execute("SELECT intrebare, raspuns FROM general_questions")

    rows = cursor.fetchall()
    if not rows:
        return None

    norm_q = normalize(question_text)
    norm_map = {normalize(q): (q, a) for q, a in rows}
    best, score = process.extractOne(norm_q, list(norm_map.keys()))
    if score > 70:
        return norm_map[best][1]
    return None


def get_response(receiver, conn, mapper, question_text, conversation_state):
    cursor = conn.cursor()
    query_lower = question_text.lower().strip()

    if conversation_state.get("waiting_for_announcement_number", False):
        number_str = is_announcement_number_query(question_text)
        if number_str:
            conversation_state["waiting_for_announcement_number"] = False
            return open_announcement_by_number(number_str)
        conversation_state["waiting_for_announcement_number"] = False

    if is_schedule_query(question_text):
        return open_schedule()

    if "announcement" in query_lower or "announcements" in query_lower:
        conversation_state["waiting_for_announcement_number"] = True
        return list_announcements_verbally()

    if "map" in query_lower:
        place_name = re.sub(
            r"\bmap\b|\bshow\b|\bopen\b|\bme\b|\bthe\b|\bplease\b|\bof\b|\bfor\b|\bto\b",
            "",
            query_lower
        ).strip()
        if place_name:
            try:
                result = mapper.generate_map(place_name)
                if result:
                    distance, dest_name = result
                    return f"{dest_name} is approximately {distance:.2f} kilometers away. I've opened the map for you."
                else:
                    return f"Sorry, I couldn't find {place_name} on the map."
            except Exception as e:
                print(f"[ERROR] Map generation failed: {e}")
                return "Sorry, I had trouble opening the map."
        else:
            return "Sure! What location would you like me to show on the map?"

    return search_database(question_text, cursor)


def speak_response(text):
    try:
        print(f"[DEBUG] Speaking: '{text}'")
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


def interaction_loop(MAX_IDLE, receiver, student_name, conn, mapper):
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

        print("[INFO] Waiting for microphone input...")
        audio_data = receiver.record_audio(duration=5)

        
        if audio_data is None or audio_data.size == 0:
            print("[WARN] No audio received")
            speak_response("I didn't hear anything. Please try again.")
            continue

        question_text = receiver.recognize_audio(audio_data)
        print(f"[DEBUG] Recognized: '{question_text}'")

        if not question_text:
            speak_response("I didn't understand. Please speak clearly.")
            continue

        if question_text.lower() in ("exit", "stop", "la revedere"):
            speak_response("La revedere")
            break

        response_text = get_response(receiver, conn, mapper, question_text, conversation_state)
        if not response_text:
            response_text = "Sorry, I couldn't understand the question. Please try again."

        speak_response(response_text)

        if not conversation_state.get("waiting_for_announcement_number", False):
            speak_response("Ask another question or say exit.")

        last_interaction = time.time()


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
            cursor.execute("SELECT id FROM students WHERE nume = ?", (student_name,))
            if cursor.fetchone() is None:
                speak_response(f"I couldn't find you in the database, {student_name}. Please try again!")
                continue

            print(f"[INFO] Student identified: {student_name}")
            interaction_loop(MAX_IDLE=90, receiver=receiver, student_name=student_name, conn=conn, mapper=mapper)

    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
    finally:
        if receiver:
            receiver.cleanup()
        conn.close()
        print("[INFO] Database connection closed.")


if __name__ == "__main__":
    main()