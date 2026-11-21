import os, json, time, urllib.request, urllib.error

API_KEY=os.environ["GEMINI_API_KEY"]
MODEL="gemini-3.5-flash-lite"
PROMPT="""Create an original 30-second silent 3D stickman fight for AI Story World.
Visual style: polished cinematic 3D CGI animation, two simple but dimensional humanoid stick fighters with smooth rounded 3D heads, torsos, arms and legs. Hero is vivid ruby red; rival is electric blue. Give them glossy smooth materials, soft studio shadows, expressive body language, dynamic camera-friendly poses and clear readable action. Bright clean studio floor/background, dramatic but family-friendly lighting.
Action: immediate face-off hook, fast punch, clever dodge, powerful kick, both leap into a mid-air clash, blue rival tumbles down, funny triumphant final pose. No blood, gore, weapons, realistic injury, cruelty, voice, narration, dialogue, captions or text. Keep character colors and proportions consistent throughout.
Return only JSON with exactly keys title and story. title: catchy short title. story: five concise visual action beats, no narration."""
def main():
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload={"contents":[{"parts":[{"text":PROMPT}]}],"generationConfig":{"responseMimeType":"application/json","temperature":0.8,"maxOutputTokens":900}}
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","x-goog-api-key":API_KEY},method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req,timeout=180) as r: data=json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            detail=e.read().decode(errors="replace"); print(f"Gemini HTTP {e.code}: {detail}")
            if e.code not in (429,500,502,503,504) or attempt==4: raise
            time.sleep(min(15*2**attempt,90))
        except (TimeoutError,urllib.error.URLError):
            if attempt==4: raise
            time.sleep(min(15*2**attempt,90))
    parts=data.get("candidates",[{}])[0].get("content",{}).get("parts",[])
    raw="".join(p.get("text","") for p in parts).strip()
    story=json.loads(raw)
    if not story.get("title") or not story.get("story"): raise ValueError("Gemini story missing title/story")
    with open("story.txt","w",encoding="utf-8") as f: json.dump(story,f,ensure_ascii=False,indent=2)
    print("SUCCESS: New story:",story["title"])
if __name__=="__main__": main()
