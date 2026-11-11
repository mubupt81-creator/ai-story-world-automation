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
Write an original English cartoon comedy episode for a YouTube video featuring the same two original recurring characters: Bop, a plump orange cat with a cream muzzle, amber eyes and a tiny green collar; and Pip, a tiny clever teal-blue mouse with large ears and a red scarf. Keep their colors, proportions, faces and accessories identical throughout.
The narration MUST contain 230 to 260 words (aim for about 245 words, suitable for approximately 2 minutes of natural narration).
Start with an immediate funny visual mishap or chase. No greeting or channel introduction. Build a clear comic setup, escalating harmless slapstick, clever mouse tricks, ridiculous cat reactions, playful physical comedy, silly props and visual gags, ending in a surprising laugh.
Plan exactly 10 distinct visual story moments. Each scene must show one clear action that can be understood visually. Use a fresh location and comic situation each episode, but never change Bop or Pip's character designs.
Keep it cheerful and family-friendly: no graphic injury or cruelty. Include a catchy, specific title.
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
            "maxOutputTokens": 2500
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
