import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def make_hashtags(title, story):
    import re
    stop = {"about", "after", "again", "could", "every", "first", "found", "their",
            "there", "these", "thing", "through", "under", "until", "where", "which",
            "while", "would", "young", "story", "stories", "with", "from", "that",
            "this", "then", "them", "they", "when", "what", "were", "have", "into"}
    words = re.findall(r"[A-Za-z]{4,}", f"{title} {story}".lower())
    chosen = []
    for word in words:
        if word not in stop and word not in chosen:
            chosen.append(word)
        if len(chosen) == 4:
            break
    tags = ["#Shorts", "#AIStory", "#StoryTime", "#ShortStory"]
    tags.extend("#" + word.title().replace(" ", "") for word in chosen)
    return " ".join(tags[:8])


def main():
    video = Path("output/ai_story_short.mp4")
    story_file = Path("story.txt")
    if not video.exists() or video.stat().st_size < 10_000:
        raise FileNotFoundError("Video file is missing or too small.")
    data = json.loads(story_file.read_text(encoding="utf-8"))
    title = str(data.get("title", "AI Story World"))[:90] + " #Shorts"
    story = str(data.get("story", ""))
    hashtags = make_hashtags(title, story)
    description = (
        f"{title.replace(' #Shorts', '')} | Mystery & Monster Adventure\n\n"
        "A strange mystery. A creature no one expected. One adventure with a twist! "
        "Watch until the end to discover what really happened.\n\n"
        + story[:3500]
        + "\n\nWhat would YOU do if you met this monster? Tell us in the comments!\n\n"
        "Subscribe to AI Story World for more original mystery, monster and fantasy adventures.\n\n"
        + hashtags
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
                "tags": ["AI Story World", "YouTube Shorts", "English Story", "Short Story", "StoryTime", "AI Story"] + [tag.lstrip("#") for tag in hashtags.split() if tag != "#Shorts"],
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
