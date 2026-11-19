import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

WIDTH, HEIGHT, FPS, DURATION = 540, 960, 20, 30
FRAME_COUNT = FPS * DURATION
OUT = Path("output")
OUT.mkdir(exist_ok=True)


def load_story():
    data = json.loads(Path("story.txt").read_text(encoding="utf-8"))
    title, story = data.get("title"), data.get("story")
    if not title or not story:
        raise ValueError("story.txt must contain title and story")
    return str(title), story


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def draw_stickman(draw, x, y, scale, color, phase, fighter, facing=1, pose="stand"):
    # Minimal hand-drawn stick figure: solid colour, thick rounded strokes.
    cx, cy = int(x), int(y)
    bob = math.sin(phase * 5 + fighter) * 8 * scale
    cx, cy = int(cx), int(cy + bob)
    head_r = int(27 * scale)
    width = max(13, int(23 * scale))

    # Character pose changes through the fight.
    move = math.sin(phase * 2.8 + fighter * math.pi)
    if pose == "fall":
        head = (cx + int(48*scale*facing), cy - int(22*scale))
        shoulder = (cx, cy)
        hip = (cx - int(45*scale*facing), cy + int(8*scale))
        arms = [(shoulder, (cx+int(20*scale*facing), cy-int(42*scale))),
                (shoulder, (cx-int(5*scale*facing), cy+int(38*scale)))]
        legs = [(hip, (cx-int(75*scale*facing), cy+int(32*scale))),
                (hip, (cx-int(15*scale*facing), cy+int(70*scale)))]
    elif pose == "kick":
        head = (cx, cy-int(115*scale))
        shoulder = (cx, cy-int(76*scale))
        hip = (cx, cy+int(12*scale))
        arms = [(shoulder, (cx-int(48*scale*facing), cy-int(40*scale))),
                (shoulder, (cx+int(42*scale*facing), cy-int(55*scale)))]
        legs = [(hip, (cx-int(35*scale*facing), cy+int(65*scale))),
                (hip, (cx+int((100+35*move)*scale*facing), cy-int(8*scale)))]
    elif pose == "punch":
        head = (cx, cy-int(115*scale))
        shoulder = (cx, cy-int(76*scale))
        hip = (cx, cy+int(12*scale))
        arms = [(shoulder, (cx-int(42*scale*facing), cy-int(28*scale))),
                (shoulder, (cx+int((88+24*move)*scale*facing), cy-int(80*scale)))]
        legs = [(hip, (cx-int(50*scale*facing), cy+int(68*scale))),
                (hip, (cx+int(45*scale*facing), cy+int(60*scale)))]
    elif pose == "jump":
        head = (cx, cy-int(140*scale))
        shoulder = (cx, cy-int(100*scale))
        hip = (cx, cy-int(5*scale))
        arms = [(shoulder, (cx-int(70*scale*facing), cy-int(150*scale))),
                (shoulder, (cx+int(70*scale*facing), cy-int(150*scale)))]
        legs = [(hip, (cx-int(70*scale*facing), cy+int(35*scale))),
                (hip, (cx+int(70*scale*facing), cy+int(35*scale)))]
    else:
        head = (cx, cy-int(115*scale))
        shoulder = (cx, cy-int(76*scale))
        hip = (cx, cy+int(12*scale))
        arms = [(shoulder, (cx-int(55*scale*facing), cy-int(28*scale))),
                (shoulder, (cx+int(55*scale*facing), cy-int(28*scale)))]
        legs = [(hip, (cx-int(48*scale*facing), cy+int(75*scale))),
                (hip, (cx+int(48*scale*facing), cy+int(75*scale)))]

    def thick_line(a, b):
        draw.line((a, b), fill=color, width=width)
        r = width // 2
        for px, py in (a, b):
            draw.ellipse((px-r, py-r, px+r, py+r), fill=color)

    # Single solid colour throughout each figure, like the supplied reference.
    draw.ellipse((head[0]-head_r, head[1]-head_r,
                  head[0]+head_r, head[1]+head_r), fill=color)
    thick_line(shoulder, hip)
    for a, b in arms + legs:
        thick_line(a, b)


def make_frame(frame_index):
    t = frame_index / FPS
    image = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)

    # Plain white stage and a strong black floor line, matching the reference.
    floor_y = 755
    draw.rectangle((0, floor_y, WIDTH, HEIGHT), fill="#ffffff")
    draw.line((0, floor_y, WIDTH, floor_y), fill="#050505", width=5)

    segment = min(5, int(t // 5))
    local = (t - segment * 5) / 5
    pulse = math.sin(local * math.pi * 2)
    hero_x = 150 + 18 * math.sin(t * 1.7)
    rival_x = 390 - 18 * math.sin(t * 1.7)
    hero_y = floor_y - 18
    rival_y = floor_y - 18

    # A clear six-beat fight: face-off, punch, dodge, kick, jump clash, knockdown.
    hero_pose = "stand"
    rival_pose = "stand"
    if segment == 1:
        hero_pose, rival_pose = "punch", "stand"
        hero_x += 48 * smoothstep(local)
        rival_x -= 18 * smoothstep(local)
    elif segment == 2:
        hero_pose, rival_pose = "stand", "fall"
        hero_x += 30 * math.sin(local * math.pi)
        rival_x -= 55 * smoothstep(local)
        rival_y += 45 * smoothstep(local)
    elif segment == 3:
        hero_pose, rival_pose = "kick", "stand"
        hero_x += 30 * smoothstep(local)
        rival_x -= 25 * smoothstep(local)
    elif segment == 4:
        hero_pose, rival_pose = "jump", "jump"
        hero_y -= 80 * abs(pulse)
        rival_y -= 65 * abs(pulse)
        hero_x += 55 * math.sin(local * math.pi)
        rival_x -= 55 * math.sin(local * math.pi)
    elif segment == 5:
        hero_pose, rival_pose = "stand", "fall"
        rival_x -= 35
        rival_y += 65 * smoothstep(local)

    # Brief hand-drawn impact burst at the point of contact.
    if segment in (1, 3, 4) and 0.38 < local < 0.68:
        ix = int((hero_x + rival_x) / 2)
        iy = int(floor_y - 160)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            draw.line((ix + math.cos(rad)*12, iy + math.sin(rad)*12,
                       ix + math.cos(rad)*46, iy + math.sin(rad)*46),
                      fill="#111111", width=5)

    draw_stickman(draw, hero_x, hero_y, 1.28, "#d21f16", t*2.5, 0, 1, hero_pose)
    draw_stickman(draw, rival_x, rival_y, 1.28, "#3048b5", t*2.3, 1, -1, rival_pose)

    return image


def make_video(title, story):
    video_path = OUT / "ai_story_short.mp4"
    command = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-t", str(DURATION), "-movflags", "+faststart",
        str(video_path)
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame_index in range(FRAME_COUNT):
            frame = make_frame(frame_index)
            process.stdin.write(frame.tobytes())
            if frame_index % (FPS*5) == 0:
                print(f"Rendering 2D stickman fight: {frame_index}/{FRAME_COUNT} frames")
        process.stdin.close()
        result = process.wait()
        if result != 0:
            raise RuntimeError(f"FFmpeg exited with code {result}")
    except Exception:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        process.kill()
        process.wait()
        raise

    if not video_path.exists() or video_path.stat().st_size < 10_000:
        raise RuntimeError("Final 2D stickman Short was not created correctly.")
    print(f"SUCCESS: Created {DURATION}-second 2D Stick Man Fight Short: {video_path}")
    print("No Viggle, Cloudflare, paid video credits, voice, or external image API used.")


if __name__ == "__main__":
    title, story = load_story()
    make_video(title, story)
