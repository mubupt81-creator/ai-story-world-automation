import os
import json
import urllib.request

API_KEY = os.environ["GEMINI_API_KEY"]

def generate_story():
    prompt = """
    Write an original, engaging English short story for YouTube.
    Duration: approximately 2 minutes.
    Include a catchy title, narration, and a positive ending.
    Return JSON with keys: title and story.
    """

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent?key=" + API_KEY
    )

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())

    text = result["candidates"][0]["content"]["parts"][0]["text"]
    print(text)

    with open("story.txt", "w", encoding="utf-8") as file:
        file.write(text)

if __name__ == "__main__":
    generate_story()
