import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
from PIL import Image

WIDTH, HEIGHT, FPS = 1080, 1920, 24
CLIP_COUNT = 3
CLIP_SECONDS = 10
VIGGLE_BASE = "https://apis.viggle.ai/v1"
VIGGLE_RESOLUTION = "768p"
# At 768p with enhance=false, H3 costs 1 credit per generated second.
REQUIRED_CREDITS = CLIP_COUNT * CLIP_SECONDS
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
CLOUDFLARE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
OUT = Path("output")
OUT.mkdir(exist_ok=True)


def load_story():
    data = json.loads(Path("story.txt").read_text(encoding="utf-8"))
    title, story = data.get("title"), data.get("story")
    if not title or not story:
        raise ValueError("story.txt must contain title and story")
    return title, story


def split_story(story, count=CLIP_COUNT):
    # Gemini returns the five visual beats as a JSON list; also accept plain text.
    if isinstance(story, list):
        beats = [str(beat).strip() for beat in story if str(beat).strip()]
    elif isinstance(story, str):
        beats = re.split(r"(?<=[.!?])\s+", story.strip())
        beats = [beat.strip(" \t\r\n-0123456789.)") for beat in beats if beat.strip()]
    else:
        raise ValueError(f"Story must be text or a list of beats, got {type(story).__name__}.")
    beats = [beat for beat in beats if beat]
    if not beats:
        raise ValueError("Story contains no visual action beats.")
    groups = [[] for _ in range(min(count, len(beats)))]
    for i, beat in enumerate(beats):
        groups[min(len(groups) - 1, i * len(groups) // len(beats))].append(beat)
    return [" ".join(group) for group in groups]

def viggle_headers():
    key = os.getenv("VIGGLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing VIGGLE_API_KEY GitHub Actions secret.")
    return {"Authorization": f"Bearer {key}"}


def check_viggle_credits():
    response = requests.get(f"{VIGGLE_BASE}/credits", headers=viggle_headers(), timeout=30)
    response.raise_for_status()
    balance = response.json().get("balance")
    if not isinstance(balance, (int, float)):
        raise RuntimeError("Viggle returned an unreadable credit balance; stopping safely.")
    print(f"Viggle credit balance: {balance}")
    print(f"Required maximum for this 30-second 768p Short: {REQUIRED_CREDITS} credits.")
    if balance < REQUIRED_CREDITS:
        print(
            f"SKIP: Only {balance} Viggle credits available; {REQUIRED_CREDITS} required. "
            "No video was generated and no top-up or subscription was requested."
        )
        return False
    return True


def scene_prompt(title, excerpt, index):
    return (
        "Portrait 9:16 crisp 2D stickman fight animation keyframe, clean white or simple colored background, "
        "bold black hand-drawn outlines, flat colors, expressive poses, dynamic speed lines and comic-book action framing. "
        "Show the same two original stickman characters: Hero Stickman, a white round head with a black line-art body "
        "and a small red wristband; Shadow Stickman, a black stick figure with glowing red eyes. "
        "Keep their simple 2D designs and proportions consistent. "
        "Show a clear readable fight pose with no text, letters, subtitles, logos or watermark. "
        "Non-graphic playful action only, no blood, gore or visible injury. "
        f"Episode: {title}. Action beat {index + 1}: {excerpt[:500]}"
    )


def generate_cloudflare_image(prompt, destination, index):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise RuntimeError("Cloudflare image-generation secrets are missing.")
    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{CLOUDFLARE_MODEL}"
    )
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    form = {
        "prompt": prompt,
        "width": "768",
        "height": "1344",
        "guidance": "4",
    }
    response = requests.post(
        endpoint,
        headers=headers,
        files={key: (None, value) for key, value in form.items()},
        timeout=(30, 240),
    )
    if not response.ok:
        raise RuntimeError(
            f"Cloudflare image API failed for opening frame {index + 1}: "
            f"HTTP {response.status_code}: {response.text[:400]}"
        )
    payload = response.json()
    image_b64 = (payload.get("result") or {}).get("image")
    if not image_b64:
        raise RuntimeError(f"Cloudflare returned no opening image for clip {index + 1}.")
    destination.write_bytes(base64.b64decode(image_b64, validate=True))
    with Image.open(destination) as image_file:
        image_file.verify()
    print(f"Created opening frame {index + 1}.")


def make_animation_prompt(title, excerpt, index):
    return (
        "Create a fluid 2D stickman fight animation in portrait 9:16, matching the supplied first frame exactly. "
        "Preserve the same two characters and clean hand-drawn black outlines throughout: "
        "Hero Stickman has a white round head, black line-art body and small red wristband; "
        "Shadow Stickman is a black stick figure with glowing red eyes. "
        "Use clear frame-by-frame 2D movement, squash-and-stretch, anticipation, follow-through, "
        "fast dodges, punches, kicks, blocks, jumps, flips, speed lines and dynamic camera framing. "
        "The characters must move continuously for the full shot; do not create a still image or slideshow. "
        "Silent visual action only: no speech, narration, singing, music, sound effects, captions, subtitles, "
        "logos or on-screen text. Playful non-graphic fight only, no blood, gore or injury. "
        f"Episode: {title}. Fight action beat {index + 1}: {excerpt}"
    )


def generate_viggle_clip(prompt, first_frame, destination, index):
    headers = viggle_headers()
    with first_frame.open("rb") as image_file:
        response = requests.post(
            f"{VIGGLE_BASE}/videos",
            headers=headers,
            data={
                "prompt": prompt,
                "quality": "low",
                "duration_s": str(CLIP_SECONDS),
                "resolution": VIGGLE_RESOLUTION,
                "aspect_ratio": "9:16",
                "enhance": "false",
                "watermark": "false",
            },
            files={"first_frame_image": (first_frame.name, image_file, "image/jpeg")},
            timeout=(30, 180),
        )
    if not response.ok:
        raise RuntimeError(
            f"Viggle rejected clip {index + 1}: HTTP {response.status_code}: "
            f"{response.text[:600]}"
        )
    job = response.json()
    video_id = job.get("id")
    if not video_id:
        raise RuntimeError(f"Viggle returned no video ID for clip {index + 1}: {job}")

    print(f"Viggle accepted clip {index + 1}; waiting for animation...")
    video = None
    for attempt in range(120):
        time.sleep(5)
        poll = requests.get(
            f"{VIGGLE_BASE}/videos/{video_id}",
            headers=headers,
            timeout=30,
        )
        poll.raise_for_status()
        video = poll.json()
        status = video.get("status")
        if status in ("ready", "failed", "cancelled"):
            break
        if attempt % 6 == 0:
            print(f"Clip {index + 1} status: {status or 'processing'}")
    else:
        raise TimeoutError(f"Timed out waiting for Viggle clip {index + 1} ({video_id}).")

    if video.get("status") != "ready" or not video.get("video_url"):
        raise RuntimeError(
            f"Viggle clip {index + 1} did not complete: "
            f"{json.dumps(video.get('error') or video, ensure_ascii=False)[:700]}"
        )

    download = requests.get(video["video_url"], timeout=(30, 240), stream=True)
    download.raise_for_status()
    with destination.open("wb") as output_file:
        for chunk in download.iter_content(chunk_size=1024 * 1024):
            if chunk:
                output_file.write(chunk)
    if destination.stat().st_size < 10_000:
        raise RuntimeError(f"Viggle clip {index + 1} download is unexpectedly small.")
    print(f"Downloaded animated clip {index + 1}.")


def assemble_short(clip_paths):
    video_path = OUT / "ai_story_short.mp4"
    inputs = []
    filters = []
    labels = []
    for index, clip_path in enumerate(clip_paths):
        inputs += ["-i", str(clip_path)]
        label = f"v{index}"
        filters.append(
            f"[{index}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},"
            f"format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        f"{''.join(labels)}concat=n={len(clip_paths)}:v=1:a=0,format=yuv420p[vout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-t", "30",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "22", "-an", "-movflags", "+faststart", str(video_path),
        ],
        check=True,
    )
    if not video_path.exists() or video_path.stat().st_size < 100_000:
        raise RuntimeError("Final animated Short was not created correctly.")
    print(f"SUCCESS: 30-second silent 3D-style animated Short: {video_path}")
    print("Three 10-second Viggle H3 animated clips; source audio removed.")


def make_video(title, story):
    # Check balance before any billable Viggle video-generation request.
    if not check_viggle_credits():
        return False
    scenes = split_story(story, count=CLIP_COUNT)
    if len(scenes) != CLIP_COUNT:
        raise RuntimeError(
            f"Expected {CLIP_COUNT} story sections for a 30-second Short; got {len(scenes)}."
        )

    clip_paths = []
    for index, excerpt in enumerate(scenes):
        frame_path = OUT / f"opening_frame_{index + 1:02d}.jpg"
        clip_path = OUT / f"viggle_clip_{index + 1:02d}.mp4"
        generate_cloudflare_image(scene_prompt(title, excerpt, index), frame_path, index)
        prompt = make_animation_prompt(title, excerpt, index)
        generate_viggle_clip(prompt, frame_path, clip_path, index)
        clip_paths.append(clip_path)

    assemble_short(clip_paths)
    return True


if __name__ == "__main__":
    title, story = load_story()
    make_video(title, story)
