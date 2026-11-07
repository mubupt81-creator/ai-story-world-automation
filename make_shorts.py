import asyncio
import json
import math
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import edge_tts

VOICE = "en-US-AriaNeural"
WIDTH, HEIGHT, FPS = 1080, 1920, 24
SCENE_COUNT = 4
HORDE_API = "https://aihorde.net/api/v2"
HORDE_KEY = "0000000000"  # AI Horde anonymous, volunteer-powered free access
OUT = Path("output")
OUT.mkdir(exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({
    "apikey": HORDE_KEY,
    "Client-Agent": "AIStoryWorld:1.0:GitHubActions"
})


def load_story():
    data = json.loads(Path("story.txt").read_text(encoding="utf-8"))
    title, story = data.get("title"), data.get("story")
    if not title or not story:
        raise ValueError("story.txt must contain title and story")
    return title, story


def get_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default()


def split_story(story, count=SCENE_COUNT):
    sentences = re.split(r"(?<=[.!?])\s+", story.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    groups = [[] for _ in range(min(count, max(1, len(sentences))))]
    for i, sentence in enumerate(sentences):
        groups[min(len(groups) - 1, i * len(groups) // len(sentences))].append(sentence)
    return [" ".join(group) for group in groups if group]


def scene_prompt(title, excerpt, index):
    return (
        "High-quality colorful 3D cartoon story illustration, vertical portrait 9:16 composition, "
        "family-friendly animated movie look, expressive appealing characters, detailed storybook environments, "
        "bright rich colors, soft cinematic lighting, polished smooth 3D animation style. "
        "Create one clear visual scene matching this exact story moment. Each scene must show a different action, "
        "pose, camera angle, and setting detail while keeping the same main characters, clothing, colors, and appearance "
        "consistent across all scenes. No photorealism, no text, no letters, no captions, no logos, no watermark, no collage. "
        f"Story title: {title}. Scene {index + 1}: {excerpt[:650]}"
    )

def generate_horde_image(prompt, destination, index):
    """Try the free volunteer AI Horde. If unavailable, local visuals keep the run alive."""
    try:
        response = SESSION.post(
            f"{HORDE_API}/generate/async",
            json={
                "prompt": prompt,
                "params": {
                    "width": 512,
                    "height": 768,
                    "steps": 20,
                    "n": 1,
                    "cfg_scale": 7,
                    "sampler_name": "k_euler",
                    "karras": True
                },
                "nsfw": False,
                "censor_nsfw": True,
                "models": ["stable_diffusion"]
            },
            timeout=30
        )
        response.raise_for_status()
        request_id = response.json().get("id")
        if not request_id:
            raise RuntimeError("AI Horde did not return a generation ID.")

        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(5)
            check = SESSION.get(f"{HORDE_API}/generate/check/{request_id}", timeout=30)
            check.raise_for_status()
            status = check.json()
            if status.get("faulted"):
                raise RuntimeError("AI Horde generation was faulted.")
            if status.get("done"):
                result = SESSION.get(f"{HORDE_API}/generate/status/{request_id}", timeout=30)
                result.raise_for_status()
                generations = result.json().get("generations", [])
                if not generations or not generations[0].get("img"):
                    raise RuntimeError("AI Horde returned no image.")
                image_response = requests.get(generations[0]["img"], timeout=60)
                image_response.raise_for_status()
                destination.write_bytes(image_response.content)
                with Image.open(destination) as check_image:
                    check_image.verify()
                print(f"SUCCESS: AI cinematic image generated for scene {index + 1}.")
                return True
        raise TimeoutError("AI Horde image request timed out after 25 seconds.")
    except Exception as error:
        raise RuntimeError(
            f"Real AI-generated image unavailable for scene {index + 1}; "
            "stopping instead of creating a text/gradient fallback."
        ) from error


def make_fallback_image(title, excerpt, index, path):
    # Offline fallback: cinematic atmospheric artwork, not an AI-generated image.
    top = (10 + index * 5, 18 + index * 3, 35 + index * 7)
    bottom = (62 + index * 7, 35 + index * 4, 65 + index * 5)
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(top[c] * (1 - t) + bottom[c] * t) for c in range(3))
        draw.line((0, y, WIDTH, y), fill=color)
    draw.ellipse((780, 65, 1230, 515), fill=(255, 190, 115, 32))
    draw.ellipse((850, 135, 1160, 445), fill=(255, 220, 165, 24))
    # distant cinematic skyline / landscape silhouette
    for x in range(0, WIDTH, 95):
        h = 100 + ((x * 17 + index * 53) % 170)
        draw.rectangle((x, HEIGHT - h, x + 65, HEIGHT), fill=(4, 8, 20, 175))
    draw.rectangle((0, 600, WIDTH, HEIGHT), fill=(3, 7, 18, 180))
    # Keep fallback artwork image-led: no story paragraphs or text-only screens.
    # Add atmospheric foreground shapes so the fallback remains a visual scene.
    draw.ellipse((120, 1040, 520, 1510), fill=(18, 24, 38, 210))
    draw.ellipse((300, 900, 610, 1320), fill=(28, 35, 52, 225))
    draw.polygon([(0, 1500), (250, 1120), (520, 1500)], fill=(8, 13, 25, 230))
    image = image.filter(ImageFilter.GaussianBlur(0.25))
    image.save(path, quality=92)


async def make_voice(story):
    audio = OUT / "narration.mp3"
    communicate = edge_tts.Communicate(
        text=story, voice=VOICE, rate="-8%", volume="+0%"
    )
    await communicate.save(str(audio))
    if not audio.exists() or audio.stat().st_size < 1000:
        raise RuntimeError("Neural text-to-speech did not create a valid audio file.")
    print(f"SUCCESS: Natural English neural voice-over created with {VOICE}.")


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True
    )
    return float(result.stdout.strip())


def make_video(title, story):
    audio = OUT / "narration.mp3"
    duration = audio_duration(audio)
    scenes = split_story(story)
    seconds_per_scene = duration / len(scenes)
    image_paths = []

    for i, excerpt in enumerate(scenes):
        image_path = OUT / f"scene_{i + 1:02d}.jpg"
        prompt = scene_prompt(title, excerpt, i)
        if not generate_horde_image(prompt, image_path, i):
            raise RuntimeError(f"Scene {i + 1} did not receive a real AI-generated image.")
        # AI Horde returns square images; crop to a cinematic 16:9 frame.
        with Image.open(image_path) as source:
            source = source.convert("RGB")
            sw, sh = source.size
            target_ratio = WIDTH / HEIGHT
            if sw / sh > target_ratio:
                new_w = int(sh * target_ratio)
                left = (sw - new_w) // 2
                source = source.crop((left, 0, left + new_w, sh))
            else:
                new_h = int(sw / target_ratio)
                top = (sh - new_h) // 2
                source = source.crop((0, top, sw, top + new_h))
            source = source.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            source.save(image_path, quality=94)
        image_paths.append(image_path)

    # Four story-matched stills receive slow cinematic Ken Burns movement and soft fades.
    inputs = []
    filters = []
    labels = []
    for i, image_path in enumerate(image_paths):
        scene_duration = seconds_per_scene + (0.15 if i == len(image_paths) - 1 else 0)
        frames = max(1, int(scene_duration * FPS))
        inputs += ["-i", str(image_path)]
        zoom = "min(zoom+0.00065,1.10)" if i % 2 == 0 else "max(zoom-0.00045,1.0)"
        if i % 2:
            zoom = "if(eq(on,1),1.10,max(zoom-0.00065,1.0))"
        fade_out_start = max(0, scene_duration - 0.45)
        label = f"v{i}"
        filters.append(
            f"[{i}:v]scale=1215:2160:force_original_aspect_ratio=increase,"
            f"crop=1215:2160,zoompan=z='{zoom}':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
            f"setsar=1,fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={fade_out_start:.3f}:d=0.4[{label}]"
        )
        labels.append(f"[{label}]")

    concat_inputs = "".join(labels)
    filters.append(f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0,format=yuv420p[vout]")
    filter_complex = ";".join(filters)
    video_path = OUT / "ai_story_short.mp4"
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-i", str(audio),
         "-filter_complex", filter_complex,
         "-map", "[vout]", "-map", f"{len(image_paths)}:a",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "22", "-c:a", "aac", "-b:a", "160k",
         "-shortest", "-movflags", "+faststart", str(video_path)],
        check=True
    )
    print(f"SUCCESS: Vertical 1080x1920 Short created: {video_path} ({duration:.1f}s)")
    print(f"Voice: {VOICE}; scenes: {len(image_paths)}; camera motion: vertical Ken Burns zoom.")


if __name__ == "__main__":
    title, story = load_story()
    asyncio.run(make_voice(story))
    make_video(title, story)
