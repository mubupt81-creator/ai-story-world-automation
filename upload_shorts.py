import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def main():
    video = Path("output/ai_story_short.mp4")
    story_file = Path("story.txt")
    if not video.exists() or video.stat().st_size < 10_000:
        raise FileNotFoundError("Video file is missing or too small.")
    data = json.loads(story_file.read_text(encoding="utf-8"))
    title = str(data.get("title", "AI Story World"))[:90] + " #Shorts"
    description = (
        str(data.get("story", ""))[:4000]
        + "\n\n#Shorts #AIStory #ShortStory #StoryTime"
        + "\n\nCreated automatically by AI Story World."
    )

    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        print("SKIPPED: YouTube credentials are not configured. Story and video artifacts will still be saved.")
        return

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    credentials.refresh(Request())
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["AI Story World", "YouTube Shorts", "English Story", "Short Story", "StoryTime", "AI Story"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True),
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"YouTube upload: {int(status.progress() * 100)}%")
    print("SUCCESS: YouTube Short uploaded as PUBLIC.")
    print("Video ID:", response["id"])
    print("URL: https://www.youtube.com/watch?v=" + response["id"])


if __name__ == "__main__":
    main()
