import base64
import os
import json
import math
import re
import subprocess
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT, FPS = 1080, 1920, 24
SCENE_COUNT = 5
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
        "High-quality colorful 3D family cartoon comedy frame, vertical 9:16, polished theatrical animation, "
        "bright playful lighting, expressive faces, squash-and-stretch poses, clear readable physical comedy, "
        "rich colorful setting, crisp character silhouettes and detailed props. "
        "Always use the exact same two original characters: Bop is a plump orange cat with a cream muzzle, "
        "amber eyes and a tiny green collar; Pip is a tiny teal-blue mouse with large ears and a red scarf. "
        "Preserve their exact colors, body proportions, facial features and accessories in every image. "
        "Show the specific funny action in this scene: chase, harmless pratfall, clever trick, funny surprise, "
        "or exaggerated reaction. Each image is one clear action moment, not a collage. "
        "No photorealism, no text, letters, captions, logos, watermark, injury or violence. "
        f"Episode title: {title}. Scene {index + 1}: {excerpt[:650]}"
    )

def generate_cloudflare_image(prompt, destination, index):
    """Generate one portrait cartoon scene with safe prompt retries."""
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise RuntimeError(
            "Cloudflare setup is incomplete. Add CLOUDFLARE_ACCOUNT_ID and "
            "CLOUDFLARE_API_TOKEN to GitHub Actions secrets."
        )

    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_MODEL}"
    )
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}

    # If the story-specific prompt is blocked by the image safety filter,
    # retry with a neutral family-friendly visual prompt for that scene.
    safe_scenes = [
        "the same plump orange cartoon cat with a cream muzzle, amber eyes and tiny green collar peeking around a kitchen door while a tiny teal-blue mouse with large ears and a red scarf hides behind a cheese wedge",
        "the same orange cartoon cat tiptoeing across a bright kitchen while the tiny teal-blue mouse quietly swaps the cat's slippers for oversized roller skates",
        "the tiny teal-blue mouse proudly showing a tiny spring-loaded toy while the orange cat looks confused in a colorful living room",
        "the tiny teal-blue mouse zooming past on a toy car as the orange cat slides harmlessly across a polished kitchen floor, surprised expression",
        "the orange cat and tiny teal-blue mouse sharing a funny triumphant pose beside a toppled stack of pillows in a sunny cartoon room",
    ]
    prompts = [
        prompt,
        (
            "Family-friendly colorful 3D animated movie illustration, portrait 9:16. "
            "A consistent family-friendly cat-and-mouse cartoon comedy scene with the same plump orange cat and tiny teal-blue mouse, "
            + safe_scenes[index % len(safe_scenes)]
            + ". Warm positive mood, expressive friendly face, detailed storybook "
            "environment, polished high-quality cartoon rendering, soft cinematic "
            "lighting. No text, no letters, no logos, no watermark, no violence."
        ),
    ]

    last_error = None
    for attempt, current_prompt in enumerate(prompts, start=1):
        form = {
            "prompt": current_prompt,
            "width": "768",
            "height": "1344",
            "guidance": "4",
        }
        try:
            multipart_fields = {key: (None, value) for key, value in form.items()}
            response = requests.post(
                endpoint, headers=headers, files=multipart_fields, timeout=(30, 240)
            )
            if not response.ok:
                detail = response.text[:500]
                # Only retry a flagged prompt; other API errors need configuration fixes.
                if response.status_code == 400 and "flagged" in detail.lower() and attempt < len(prompts):
                    print(f"WARNING: Scene {index + 1} prompt was flagged; retrying with a safer prompt.")
                    last_error = RuntimeError(f"Cloudflare safety filter: {detail}")
                    time.sleep(2)
                    continue
                raise RuntimeError(
                    f"Cloudflare image API returned HTTP {response.status_code}: {detail}"
                )
            payload = response.json()
            image_b64 = (payload.get("result") or {}).get("image")
            if not image_b64:
                raise RuntimeError(
                    f"Cloudflare returned no image data: {json.dumps(payload)[:500]}"
                )
            destination.write_bytes(base64.b64decode(image_b64, validate=True))
            with Image.open(destination) as generated:
                generated.verify()
            print(f"SUCCESS: Cloudflare cartoon image generated for scene {index + 1} (attempt {attempt}).")
            return True
        except Exception as error:
            last_error = error
            if attempt >= len(prompts):
                break
            raise RuntimeError(
                f"Cloudflare image generation failed for scene {index + 1}: {error}"
            ) from error

    raise RuntimeError(
        f"AI-generated image unavailable for scene {index + 1} after safe retry; "
        "stopping instead of creating a text/gradient fallback."
    ) from last_error

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


def make_video(title, story):
    scenes = split_story(story, count=SCENE_COUNT)
    seconds_per_scene = 6.0
    image_paths = []

    for i, excerpt in enumerate(scenes):
        image_path = OUT / f"scene_{i + 1:02d}.jpg"
        prompt = scene_prompt(title, excerpt, i)
        if not generate_cloudflare_image(prompt, image_path, i):
            raise RuntimeError(f"Scene {i + 1} did not receive a real AI-generated image.")
        # Crop the generated portrait image to the final vertical Short frame.
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

    # Five story-matched silent visual scenes receive camera movement and soft fades.
    inputs = []
    filters = []
    labels = []
    for i, image_path in enumerate(image_paths):
        scene_duration = seconds_per_scene
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
        ["ffmpeg", "-y", *inputs,
         "-filter_complex", filter_complex,
         "-map", "[vout]", "-t", "30",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "22", "-an", "-movflags", "+faststart", str(video_path)],
        check=True
    )
    print(f"SUCCESS: Silent vertical 1080x1920 Short created: {video_path} (30 seconds)")
    print(f"No voice or dialogue; scenes: {len(image_paths)}; camera motion: vertical Ken Burns zoom.")


if __name__ == "__main__":
    title, story = load_story()
    make_video(title, story)
