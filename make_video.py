import asyncio
import json
import math
import os
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import edge_tts

VOICE = "en-US-AriaNeural"
WIDTH, HEIGHT = 1280, 720
OUT = Path("output")
OUT.mkdir(exist_ok=True)


def load_story():
    data = json.loads(Path("story.txt").read_text(encoding="utf-8"))
    title, story = data.get("title"), data.get("story")
    if not title or not story:
        raise ValueError("story.txt must contain title and story")
    return title, story


def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_slide(title, excerpt, index, total, path):
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()
    top = (18, 27, 54)
    bottom = (72, 40, 82)
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(top[i] * (1-t) + bottom[i] * t) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = color

    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((930, -190, 1450, 330), fill=(255, 193, 105, 28))
    draw.ellipse((-180, 500, 260, 940), fill=(120, 190, 255, 22))
    draw.rounded_rectangle((74, 70, 1206, 650), radius=34,
                           fill=(8, 12, 28, 150), outline=(255, 220, 170, 100), width=2)

    title_font = get_font(30, True)
    body_font = get_font(35)
    small_font = get_font(22)
    draw.text((120, 112), title, font=title_font, fill=(255, 220, 170, 255))
    draw.text((120, 178), f"AI STORY WORLD  •  SCENE {index + 1}/{total}",
              font=small_font, fill=(185, 205, 235, 255))

    lines = wrap_text(draw, excerpt, body_font, 1000)
    line_height = 54
    block_height = len(lines) * line_height
    y = max(260, (HEIGHT - block_height) // 2)
    for line in lines:
        draw.text((120, y), line, font=body_font, fill=(255, 255, 255, 255))
        y += line_height

    draw.rounded_rectangle((120, 590, 1160, 596), radius=3, fill=(255, 220, 170, 100))
    draw.rounded_rectangle((120, 590, 120 + int(1040 * (index + 1) / total), 596),
                           radius=3, fill=(255, 220, 170, 255))
    image.save(path, quality=95)


def split_story(story, count=7):
    sentences = re.split(r"(?<=[.!?])\s+", story.strip())
    groups = [[] for _ in range(min(count, max(1, len(sentences))))]
    for i, sentence in enumerate(sentences):
        groups[min(len(groups)-1, i * len(groups) // len(sentences))].append(sentence)
    return [" ".join(group) for group in groups if group]


async def make_voice(story):
    communicate = edge_tts.Communicate(story, VOICE, rate="+0%", volume="+0%")
    await communicate.save(str(OUT / "narration.mp3"))


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
    concat_file = OUT / "scenes.txt"

    with concat_file.open("w", encoding="utf-8") as listing:
        for i, excerpt in enumerate(scenes):
            image_path = OUT / f"scene_{i+1:02d}.jpg"
            make_slide(title, excerpt, i, len(scenes), image_path)
            listing.write(f"file '{image_path.resolve()}'\n")
            listing.write(f"duration {seconds_per_scene:.3f}\n")
        listing.write(f"file '{(OUT / f'scene_{len(scenes):02d}.jpg').resolve()}'\n")

    video_path = OUT / "ai_story_video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(audio), "-vf", "scale=1280:720,format=yuv420p",
        "-r", "24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
        str(video_path)
    ], check=True)

    print(f"SUCCESS: Video created: {video_path} ({duration:.1f}s narration)")
    print(f"Voice: {VOICE}")


if __name__ == "__main__":
    title, story = load_story()
    asyncio.run(make_voice(story))
    make_video(title, story)
