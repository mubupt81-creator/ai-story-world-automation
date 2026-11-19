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


def draw_stickman(draw, x, y, scale, color, phase, fighter, facing=1):
    # A deliberately simple, consistent 2D stick-figure design.
    head_r = int(25 * scale)
    line_w = max(5, int(9 * scale))
    t = phase
    bob = math.sin(t * 8 + fighter) * 7 * scale
    cx, cy = int(x), int(y + bob)
    head_y = cy - int(112 * scale)
    draw.ellipse((cx-head_r, head_y-head_r, cx+head_r, head_y+head_r),
                 fill="#ffffff" if fighter == 0 else "#171923",
                 outline=color, width=max(4, int(6*scale)))
    if fighter == 1:
        eye_y = head_y - 1
        draw.ellipse((cx-11*scale, eye_y-3*scale, cx-4*scale, eye_y+4*scale), fill="#ff3b4f")
        draw.ellipse((cx+4*scale, eye_y-3*scale, cx+11*scale, eye_y+4*scale), fill="#ff3b4f")

    shoulder = (cx, cy-int(80*scale))
    hip = (cx-int(2*scale), cy+int(28*scale))
    # Six readable action poses, cycling through a short choreographed fight.
    action = int((t % (2*math.pi)) / (2*math.pi) * 6)
    arm_a = [
        (-42,-48, 42,-48), (-60,-70, 65,-12), (-55,-12, 75,-68),
        (-65,-65, 72,-70), (-48,-8, 75,-78), (-62,-65, 62,-65)
    ][action]
    leg_a = [
        (-42,65, 42,65), (-60,65, 60,25), (-75,15, 85,75),
        (-65,65, 70,15), (-65,70, 90,-15), (-45,65, 45,65)
    ][action]
    punch = math.sin(t*2.5 + fighter*math.pi)
    arm_a = (arm_a[0], arm_a[1], arm_a[2] + punch*18, arm_a[3])
    def pt(dx, dy):
        return (int(cx + dx*scale*facing), int(cy + dy*scale))
    draw.line((shoulder, pt(*arm_a[:2])), fill=color, width=line_w)
    draw.line((shoulder, pt(*arm_a[2:])), fill=color, width=line_w)
    draw.line((hip, pt(*leg_a[:2])), fill=color, width=line_w)
    draw.line((hip, pt(*leg_a[2:])), fill=color, width=line_w)
    draw.line((shoulder, hip), fill=color, width=line_w)
    # Red wristband identifies the hero.
    if fighter == 0:
        wx, wy = pt(*arm_a[2:])
        draw.ellipse((wx-7*scale, wy-7*scale, wx+7*scale, wy+7*scale), fill="#ff4757")


def make_frame(frame_index):
    t = frame_index / FPS
    phase = (t % 30) / 30
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f5f7ff")
    draw = ImageDraw.Draw(image)

    # Simple changing 2D comic backgrounds; no external image service required.
    for y in range(0, HEIGHT, 4):
        mix = y / HEIGHT
        c1, c2 = (246, 249, 255), (220, 231, 255)
        color = tuple(int(c1[i]*(1-mix)+c2[i]*mix) for i in range(3))
        draw.rectangle((0, y, WIDTH, y+4), fill=color)
    draw.ellipse((30, 100, 180, 250), fill="#ffffff", outline="#e3eaff", width=3)
    draw.ellipse((390, 170, 510, 290), fill="#ffffff", outline="#e3eaff", width=3)
    floor_y = 800
    draw.line((0, floor_y, WIDTH, floor_y), fill="#64748b", width=5)
    for x in range(20, WIDTH, 65):
        draw.line((x, floor_y+8, x+25, floor_y+8), fill="#aab6ca", width=3)

    # Five 6-second beats: stare-down, dodge, kick, spin, comic finish.
    segment = min(4, int(t // 6))
    local = (t - segment*6) / 6
    beat = [0.0, 1.0, 2.0, 3.0, 4.0][segment]
    wobble = math.sin(local*math.pi*2)
    hero_x = 160 + (segment*13) + math.sin(local*math.pi*2)*22
    rival_x = 380 - (segment*11) - math.sin(local*math.pi*2)*22
    if segment == 1:
        hero_x += 55*smoothstep(local)
        rival_x -= 30*smoothstep(local)
    elif segment == 2:
        hero_x += 70*math.sin(local*math.pi)
        rival_x -= 55*math.sin(local*math.pi)
    elif segment == 3:
        hero_x += 35*math.sin(local*math.pi*3)
        rival_x -= 35*math.sin(local*math.pi*3)
    elif segment == 4:
        hero_x = 210 + 12*math.sin(local*math.pi*2)
        rival_x = 340 + 18*math.sin(local*math.pi*2)

    # Comic impact rays appear briefly around the middle of each action beat.
    if segment in (1, 2, 3) and 0.35 < local < 0.72:
        ix = int((hero_x+rival_x)/2)
        iy = 610
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            draw.line((ix+math.cos(rad)*22, iy+math.sin(rad)*22,
                       ix+math.cos(rad)*65, iy+math.sin(rad)*65),
                      fill="#ffb703", width=5)

    hero_phase = t*2.2 + beat
    rival_phase = t*2.0 + beat + math.pi
    draw_stickman(draw, hero_x, 715, 1.35, "#202938", hero_phase, 0, 1)
    draw_stickman(draw, rival_x, 715, 1.35, "#202938", rival_phase, 1, -1)

    # A harmless comic twist: the shadow fighter slips and sits down at the end.
    if segment == 4 and local > 0.58:
        sx = int(rival_x)
        draw.ellipse((sx-35, 770, sx+35, 790), fill="#aab6ca")
        draw.arc((sx-26, 665, sx+26, 715), 0, 180, fill="#202938", width=6)
        for k in range(3):
            draw.line((sx+35+k*9, 650-k*10, sx+48+k*9, 638-k*10), fill="#ff4757", width=4)

    # Small progress marker; no words or captions.
    draw.rounded_rectangle((35, 45, WIDTH-35, 56), radius=6, fill="#d5deef")
    draw.rounded_rectangle((35, 45, 35+(WIDTH-70)*(frame_index/FRAME_COUNT), 56),
                           radius=6, fill="#ff4757")
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
