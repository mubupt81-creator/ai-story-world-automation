import os
import json
import time
import urllib.request
import urllib.error

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.5-flash-lite"
TIMEOUT_SECONDS = 180
MAX_ATTEMPTS = 3


def generate_story():
    prompt = """
Write an original English Mystery + Monster Adventure story for YouTube Shorts.
The narration MUST contain 120 to 140 words (aim for about 130 words, suitable for 50–65 seconds when narrated).
Open with a powerful mystery or danger hook in the first sentence. No greeting, channel introduction, or slow setup.
Include one original, memorable monster with a distinctive visual appearance and personality. Keep the monster's identity and appearance consistent throughout the story.
Build suspense, clues, discovery, and a surprising but satisfying reveal. Keep it family-friendly: spooky and exciting, never graphic or gory.
Structure the story into 5 clear visual moments, with 8–11 concise sentences. End with a strong payoff that makes viewers want to watch to the end.
Use a fresh setting, monster design, and human character names each time. Avoid repeating familiar generic plots.
Include a catchy, specific title.
Return a JSON object with exactly these keys:
"title": a short video title
"story": the complete narration
Do not include Markdown fences or any text outside the JSON.
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{MODEL}:generateContent"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.8,
            "maxOutputTokens": 1200
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )

    result = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"Contacting Gemini (attempt {attempt}/{MAX_ATTEMPTS})...")
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            print(f"Gemini API returned HTTP {error.code}: {details}")
            if error.code not in (429, 500, 502, 503, 504) or attempt == MAX_ATTEMPTS:
                raise
        except (TimeoutError, urllib.error.URLError) as error:
            print(f"Network/API timeout or connection error: {error}")
            if attempt == MAX_ATTEMPTS:
                raise

        wait_seconds = 10 * attempt
        print(f"Retrying in {wait_seconds} seconds...")
        time.sleep(wait_seconds)

    if not result:
        raise RuntimeError("Gemini returned no response.")

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no story candidate: " + json.dumps(result, ensure_ascii=False))

    parts = candidates[0].get("content", {}).get("parts", [])
    story_text = "".join(part.get("text", "") for part in parts).strip()
    if not story_text:
        raise RuntimeError("Gemini returned an empty story.")

    story_data = json.loads(story_text)
    if not isinstance(story_data, dict) or not story_data.get("title") or not story_data.get("story"):
        raise RuntimeError("Gemini response is missing title or story.")

    with open("story.txt", "w", encoding="utf-8") as file:
        file.write(json.dumps(story_data, indent=2, ensure_ascii=False))

    print("SUCCESS: Story generated and saved to story.txt")
    print("Title:", story_data["title"])


if __name__ == "__main__":
    generate_story()
