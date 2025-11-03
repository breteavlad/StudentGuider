import subprocess
import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import process
from gtts import gTTS
from datetime import datetime
import os
import re

# Optional translation (comment out if you prefer Romanian titles)
try:
    from googletrans import Translator
    translator = Translator()
    TRANSLATE_TO_ENGLISH = True
except Exception as e:
    print(f"[WARN] googletrans not available ({e}). Titles will remain in Romanian.")
    TRANSLATE_TO_ENGLISH = False

# Direct URLs
SCHEDULE_URL = "https://docs.google.com/spreadsheets/d/1yCFgf5cqWthT9ckSHwLiSsKxBq1yChmIpLneviGpuoY/edit?gid=1829921421#gid=1829921421"
ANNOUNCEMENTS_URL = "https://ac.utcluj.ro/anunturi.html"

# Cache announcements to avoid repeated fetching
_announcements_cache = None


def get_announcements():
    """Fetch and parse announcements from the university site."""
    global _announcements_cache

    if _announcements_cache is not None:
        return _announcements_cache

    try:
        response = requests.get(ANNOUNCEMENTS_URL, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Cannot access announcements page: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    announcements = []

    # Regex to find date followed by text
    date_pattern = r'(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2})\s*\n\s*(.+?)(?=\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}|\Z)'
    content = soup.get_text()
    matches = re.findall(date_pattern, content, re.DOTALL)

    for date_str, title in matches:
        title = re.sub(r'\s+', ' ', title.strip())
        if len(title) < 5:
            continue

        # Optional translation to English
        translated_title = title
        if TRANSLATE_TO_ENGLISH:
            try:
                translated_title = translator.translate(title, src='ro', dest='en').text
            except Exception as e:
                print(f"[WARN] Translation failed for '{title}': {e}")

        # Try to find a related link
        announcement_url = ANNOUNCEMENTS_URL
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            if link_text and title[:20].lower() in link_text.lower():
                href = link['href']
                if href.startswith('/'):
                    announcement_url = "https://ac.utcluj.ro" + href
                elif href.startswith('http'):
                    announcement_url = href
                else:
                    announcement_url = "https://ac.utcluj.ro/" + href
                break

        announcements.append({
            "date": date_str,
            "title_ro": title,
            "title_en": translated_title,
            "url": announcement_url
        })

    # Sort by date (newest first)
    for ann in announcements:
        try:
            ann["parsed_date"] = datetime.strptime(ann["date"].split()[0], "%d-%m-%Y")
        except ValueError:
            ann["parsed_date"] = datetime.min

    announcements.sort(key=lambda a: a["parsed_date"], reverse=True)

    print(f"[DEBUG] Found {len(announcements)} announcements (sorted by date).")
    _announcements_cache = announcements
    return announcements


def open_in_browser(url):
    """Open a URL in Chromium (non-blocking)."""
    try:
        subprocess.Popen(
            ['chromium-browser', '--new-window', url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        print(f"[INFO] Opened in Chromium: {url}")
        return True
    except FileNotFoundError:
        try:
            subprocess.Popen(
                ['chromium', '--new-window', url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            print(f"[INFO] Opened in Chromium (alt command).")
            return True
        except Exception as e:
            print(f"[WARN] Could not open browser: {e}")
            return False


def open_schedule():
    """Open the class schedule (Google Sheets)."""
    print(f"[INFO] Opening schedule: {SCHEDULE_URL}")

    if open_in_browser(SCHEDULE_URL):
        return "I've opened the class schedule for you."
    else:
        return "Sorry, I couldn't open the schedule on your device."


def list_announcements_verbally():
    """Generate a spoken summary of announcements."""
    announcements = get_announcements()

    if not announcements:
        return "Sorry, I couldn't find any announcements right now."

    limited = announcements[:5]
    response = f"I found {len(announcements)} announcements. Here are the most recent {len(limited)}: "

    for idx, ann in enumerate(limited, 1):
        date_str = ann['date'].split()[0]
        title = ann['title_en'] if TRANSLATE_TO_ENGLISH else ann['title_ro']
        response += f"Number {idx}, from {date_str}: {title}. "

    response += "Which number would you like me to open?"
    return response


def open_announcement_by_number(number_str):
    """Open an announcement by its list number."""
    try:
        number = int(number_str)
    except (ValueError, TypeError):
        return "Sorry, I didn't understand that number. Please say a number like one, two, or three."

    announcements = get_announcements()

    if not announcements:
        return "Sorry, I couldn't find any announcements."

    if number < 1 or number > len(announcements):
        return f"Sorry, please choose a number between 1 and {min(5, len(announcements))}."

    ann = announcements[number - 1]
    title = ann['title_en'] if TRANSLATE_TO_ENGLISH else ann['title_ro']

    if open_in_browser(ann['url']):
        return f"I've opened announcement number {number}: {title}"
    else:
        return "Sorry, I couldn't open the announcement."


def open_announcement_by_keyword(query):
    """Open an announcement based on a fuzzy keyword match."""
    announcements = get_announcements()

    if not announcements:
        return "Sorry, I couldn't find any announcements."

    # Normalize the query (remove spaces for compound words like "deep mind" -> "deepmind")
    normalized_query = query.lower().replace(" ", "")
    
    # Use English titles for matching if translated
    titles = [a['title_en'] if TRANSLATE_TO_ENGLISH else a['title_ro'] for a in announcements]
    
    # Try exact word matching first (more reliable for specific topics)
    best_score = 0
    best_idx = -1
    
    for idx, title in enumerate(titles):
        title_lower = title.lower()
        normalized_title = title_lower.replace(" ", "")
        
        # Check if any word from query appears in title
        query_words = query.lower().split()
        matches = sum(1 for word in query_words if len(word) > 2 and word in title_lower)
        
        # Also check normalized version (for compound words)
        if normalized_query in normalized_title:
            matches += 3
        
        if matches > best_score:
            best_score = matches
            best_idx = idx
    
    print(f"[DEBUG] Word-based match score: {best_score}")
    
    # If word matching found something good, use it
    if best_score >= 2 and best_idx >= 0:
        ann = announcements[best_idx]
        title = ann['title_en'] if TRANSLATE_TO_ENGLISH else ann['title_ro']
        print(f"[DEBUG] Selected announcement by word match: '{title}'")
        
        if open_in_browser(ann['url']):
            return f"I've opened the announcement: {title}"
        else:
            return "Sorry, I couldn't open the announcement."
    
    # Fallback to fuzzy matching
    best_match, score = process.extractOne(query.lower(), [t.lower() for t in titles])
    print(f"[DEBUG] Fuzzy match for '{query}': '{best_match}' (score={score})")

    if score > 60:
        matched_idx = [t.lower() for t in titles].index(best_match)
        ann = announcements[matched_idx]
        title = ann['title_en'] if TRANSLATE_TO_ENGLISH else ann['title_ro']

        if open_in_browser(ann['url']):
            return f"I've opened the announcement: {title}"
        else:
            return "Sorry, I couldn't open the announcement."
    else:
        return "I couldn't find a specific match. Here are the latest announcements: " + list_announcements_verbally()


def is_schedule_query(question_text):
    """Check if the user asked for the schedule."""
    schedule_keywords = [
        "schedule", "timetable", "orar", "class schedule",
        "my schedule", "today's schedule", "classes today",
        "what classes", "when is my class", "when do i have"
    ]

    q = question_text.lower()
    return any(k in q for k in schedule_keywords)


def is_announcement_query(question_text):
    """Detect if the user is referring to announcements or specific topics from announcements."""
    # Normalize text (remove extra spaces for better matching)
    q = question_text.lower()
    q_normalized = re.sub(r'\s+', '', q)  # Remove all spaces for compound word matching
    
    announcement_keywords = [
        # general
        "announcement", "anunt", "news", "notice", "update", "notifications", "anunturi",
        # common announcement topics (with space variants)
        "deepmind", "deep mind", "results", "result", "bursa", "scholarship", 
        "volunteer", "grant", "esc", "course", "best", "registration", 
        "enrollment", "chestionar"
    ]
    
    # Check both normal and normalized versions
    for keyword in announcement_keywords:
        if keyword in q:
            print(f"[DEBUG] Detected announcement keyword: '{keyword}'")
            return True
        # Also check without spaces
        keyword_normalized = keyword.replace(" ", "")
        if keyword_normalized in q_normalized:
            print(f"[DEBUG] Detected announcement keyword (normalized): '{keyword}'")
            return True
    
    return False


def is_announcement_number_query(question_text):
    """Check if the user said a number for announcement selection."""
    number_words = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5
    }

    q = question_text.lower().strip()
    for word, num in number_words.items():
        if word in q:
            return str(num)

    match = re.search(r'\b(\d+)\b', q)
    if match:
        return match.group(1)
    return None