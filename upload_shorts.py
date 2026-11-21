import json, os, re
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def main():
    video=Path("output/ai_story_short.mp4")
    story_file=Path("story.txt")
    if not video.exists() or video.stat().st_size<10000: raise FileNotFoundError("New 3D MP4 missing or too small")
    data=json.loads(story_file.read_text(encoding="utf-8"))
    title=str(data.get("title","AI Story World 3D Fight"))[:85]
    story=str(data.get("story",""))
    tags=["Shorts","3DAnimation","3DStickman","StickmanFight","CGIAnimation","AIStoryWorld"]
    desc=(title+" | Silent 3D Stickman Fight Animation\n\n"
          "A brand-new 30-second 3D CGI stickman fight with punches, dodges, kicks and a surprise finish. "
          "No voice or narration — just animated action.\n\n"
          "Who won the fight? Tell us in the comments!\n\n"
          "Subscribe to AI Story World for more original 3D animated shorts.\n\n"
          "#Shorts #3DAnimation #3DStickman #StickmanFight #CGIAnimation #AIStoryWorld")
    cid=os.environ.get("YOUTUBE_CLIENT_ID"); secret=os.environ.get("YOUTUBE_CLIENT_SECRET"); token=os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if not all([cid,secret,token]): raise RuntimeError("YouTube OAuth secrets are missing")
    credentials=Credentials(None,refresh_token=token,token_uri="https://oauth2.googleapis.com/token",client_id=cid,client_secret=secret,scopes=["https://www.googleapis.com/auth/youtube.upload"])
    credentials.refresh(Request())
    youtube=build("youtube","v3",credentials=credentials,cache_discovery=False)
    request=youtube.videos().insert(part="snippet,status",body={
        "snippet":{"title":title+" #Shorts","description":desc,"tags":tags,"categoryId":"22"},
        "status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}
    },media_body=MediaFileUpload(str(video),chunksize=-1,resumable=True))
    response=None
    while response is None:
        status,response=request.next_chunk()
        if status: print(f"YouTube upload: {int(status.progress()*100)}%")
    print("SUCCESS: NEW 3D Short uploaded PUBLIC:",response["id"])
    print("https://www.youtube.com/watch?v="+response["id"])
if __name__=="__main__": main()
