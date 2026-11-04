import os
import json
import urllib.request
import urllib.error

API_KEY = os.environ["GEMINI_API_KEY"]

def generate_story():
    prompt = """
    Write an original, engaging English short story for YouTube.
    Duration: approximately 2 minutes.
    Include a catchy title, narration, and a positive ending.
    Return ONLY valid JSON with these keys:
    title and story.
    """

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3.8-flash:generateContent"
    )

    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        story_text = result["candidates"][0]["content"]["parts"][0]["text"]

        story_data = json.loads(story_text)

        with open("story.txt", "w", encoding="utf-8") as file:
            file.write(json.dumps(story_data, indent=2, ensure_ascii=False))

        print("SUCCESS: Story generated!")
        print("Title:", story_data["title"])

    except urllib.error.HTTPError as error:
        print("Gemini API Error:", error.code)
        print(error.read().decode("utf-8"))
        raise

    except Exception as error:
        print("Error:", str(error))
        raise

if __name__ == "__main__":
    generate_story()
