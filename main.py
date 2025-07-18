import os
from dotenv import load_dotenv
import datetime
import google.generativeai as genai
import speech_recognition as sr
from googleapiclient.discovery import build
import isodate

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
    raise Exception("API keys not found. Please check your .env file.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_voice_input():
    recognizer = sr.Recognizer()
    if not sr.Microphone.list_microphone_names():
        print("No microphone detected.")
        return None

    print("Listening... Please speak now.")
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=7)
            print("Recognizing...")
            query = recognizer.recognize_google(audio, language="en-IN")
            print("You said:", query)
            return query
        except sr.WaitTimeoutError:
            print("You didn't say anything in time.")
        except sr.UnknownValueError:
            print("Couldn't understand your speech. Try again.")
        except sr.RequestError as e:
            print("Speech recognition error:", e)

    return None

def get_user_query():
    choice = input("Use voice or text input? (v/t): ").strip().lower()
    if choice == 'v':
        return get_voice_input()
    return input("Enter your query: ").strip()

def search_youtube(query):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    published_after = (datetime.datetime.now() - datetime.timedelta(days=20)).isoformat("T") + "Z"
    
    search_response = youtube.search().list(
        q=query,
        part='id,snippet',
        maxResults=50,
        type='video',
        publishedAfter=published_after
    ).execute()
    
    video_ids = [item['id']['videoId'] for item in search_response['items']]
    if not video_ids:
        return []

    video_response = youtube.videos().list(
        part="contentDetails,snippet",
        id=",".join(video_ids)
    ).execute()

    def duration_in_minutes(duration):
        return isodate.parse_duration(duration).total_seconds() / 60

    filtered = []
    for item in video_response['items']:
        minutes = duration_in_minutes(item['contentDetails']['duration'])
        if 4 <= minutes <= 25:
            filtered.append({
                'title': item['snippet']['title'],
                'url': f"https://www.youtube.com/watch?v={item['id']}"
            })

    return filtered[:20]

def get_best_video(videos, user_query):
    if not videos:
        return None

    titles_text = "\n".join([f"- {v['title']}" for v in videos])
    prompt = f"""
Given the user's query: "{user_query}", evaluate the following video titles:

{titles_text}

Choose the most relevant and well-titled video based on clarity, how well it matches the intent, and how appealing the title is. Respond with the best title and your reasoning.
"""
    response = model.generate_content(prompt)
    return response.text

def main():
    query = get_user_query()
    if not query:
        print("No query was provided.")
        return

    print("Searching YouTube for videos...")
    results = search_youtube(query)

    if not results:
        print("No suitable videos found.")
        return

    print(f"Found {len(results)} relevant videos. Processing titles with Gemini...")

    gemini_response = get_best_video(results, query)
    print("\nGemini Recommendation:\n")
    print(gemini_response)

    print("\nTop Video Links:")
    for i, video in enumerate(results):
        print(f"{i+1}. {video['title']} - {video['url']}")

if __name__ == "__main__":
    main()
