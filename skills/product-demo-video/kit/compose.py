# Usage: $VENV/bin/python compose.py <name> <layout: phone|desktop> <title> <subtitle> [outro tagline]
# Env: DEMO_BRAND (brand name on slides + outro card, default "Demo"). Run from the project dir (reads out/<name>/).
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
name, layout, TITLE, SUB = sys.argv[1:5]
BRAND = os.environ.get("DEMO_BRAND", "Demo")
D = f"out/{name}"; W, H = 1920, 1080
script = json.load(open(f"{D}/script.json")); beats = json.load(open(f"{D}/beats.json"))
durs = json.load(open(f"{D}/audio/durations.json"))
INK, TEAL, MUTED, CREAM = (24, 38, 52), (14, 116, 112), (84, 96, 108), (247, 243, 236)
SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
SANS = "/System/Library/Fonts/HelveticaNeue.ttc"
def font(path, size, idx=0): return ImageFont.truetype(path, size, index=idx)
def run(cmd): subprocess.run(cmd, check=True)

# ---- 1. timeline: keep everything from first beat; compress fast segments to FF seconds
FF = 3.0
cap = json.load(open(f"{D}/capture.json")); off = cap["firstFrameAt"]
# never start before the first captured frame (fast-loading pages begin the first beat earlier)
start0 = max(off, beats[0]["start"] - 0.3); end0 = beats[-1]["end"] + 0.4
segs = []  # (src_a, src_b, speed)
cur = start0
for b in beats:
    if b.get("fast"):
        if b["start"] > cur: segs.append((cur, b["start"], 1.0))
        a = max(b["start"], cur)  # never before the first frame or the previous segment
        if b["end"] > a: segs.append((a, b["end"], (b["end"] - a) / FF))
        cur = max(cur, b["end"])
if end0 > cur: segs.append((cur, end0, 1.0))
def out_t(src):
    t = 0.0
    for a, b, sp in segs:
        if src <= b: return t + (max(src, a) - a) / sp
        t += (b - a) / sp
    return t
body_len = out_t(end0)
INTRO, OUTRO = 3.5, 4.5

# ---- 2. phone/desktop footage, re-timed
# Early frames can arrive at a transient (even odd) size before the viewport settles;
# scale every frame to the settled size of the last frame so the encoder gets one even size.
last = sorted(f for f in os.listdir(f"{D}/frames-raw") if f.endswith(".jpg"))[-1]
SW, SH = (v // 2 * 2 for v in Image.open(f"{D}/frames-raw/{last}").size)
parts = []
for i, (a, b, sp) in enumerate(segs):
    p = f"{D}/seg{i}.mp4"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-i", f"{D}/frames-raw/list.ffconcat",
         "-vf", f"scale={SW}:{SH}:flags=lanczos,fps=30,trim={a-off:.3f}:{b-off:.3f},setpts=(PTS-STARTPTS)/{sp:.4f},fps=30,format=yuv420p",
         "-an", "-c:v", "libx264", "-crf", "16", p])
    parts.append(p)
open(f"{D}/segs.txt", "w").write("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-i", f"{D}/segs.txt", "-c", "copy", f"{D}/footage.mp4"])

# ---- 3. caption windows (sentence chunks timed by length within each narration)
labels = {s["id"]: s for s in script}
order = [b for b in beats if b["id"]]
windows = []  # (t0, t1, step_idx, label, caption)
for k, b in enumerate(order):
    s = labels[b["id"]]; t0 = INTRO + out_t(b["start"]); dur = durs[b["id"]]
    t_end = INTRO + (out_t(order[k+1]["start"]) if k + 1 < len(order) else body_len)
    txt = s.get("caption") or s["say"]  # optional on-screen text when the spoken form differs
    sents = re.findall(r"(?:[^.!?]|[.!?](?!\s|$))+[.!?](?=\s|$)", txt) or [txt]
    chunks, buf = [], ""
    for x in sents:
        x = x.strip()
        if buf and len(buf) + len(x) > 120: chunks.append(buf); buf = x
        else: buf = (buf + " " + x).strip()
    if buf: chunks.append(buf)
    total = sum(len(c) for c in chunks); t = t0
    for j, c in enumerate(chunks):
        t1 = t + dur * len(c) / total
        windows.append((t, t_end if j == len(chunks) - 1 else t1, k, s["label"], c)); t = t1
fast_windows = [(INTRO + out_t(b["start"]), INTRO + out_t(b["end"])) for b in beats if b.get("fast")]

def wrap(d, text, f, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if d.textlength(test, font=f) <= width: line = test
        else: lines.append(line); line = w
    if line: lines.append(line)
    return lines

def background():
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    for y in range(H):  # gentle vertical gradient
        a = y / H; d.line([(0, y), (W, y)], fill=tuple(int(CREAM[i] * (1 - a * .06) + TEAL[i] * a * .06) for i in range(3)))
    return im

def frame(label=None, caption=None, step=None, card=None, fast=False):
    im = background(); d = ImageDraw.Draw(im)
    if card:
        t, s = card
        f1, f2 = font(SERIF, 92), font(SANS, 40)
        d.text((W/2, H/2 - 40), t, font=f1, fill=INK, anchor="mm")
        d.text((W/2, H/2 + 60), s, font=f2, fill=MUTED, anchor="mm")
        d.rounded_rectangle([W/2 - 40, H/2 - 140, W/2 + 40, H/2 - 134], 3, fill=TEAL)
        return im
    if layout == "phone":
        x0, wid = 900, 880
        d.text((x0, 150), BRAND, font=font(SANS, 30, 1), fill=TEAL)
        if step is not None:
            d.text((x0, 230), f"{step+1:02d} / {len(order):02d}", font=font(SANS, 28), fill=MUTED)
        y = 280
        for ln in wrap(d, label or "", font(SERIF, 62), wid):
            d.text((x0, y), ln, font=font(SERIF, 62), fill=INK); y += 78
        y += 30
        d.rounded_rectangle([x0, y, x0 + 70, y + 6], 3, fill=TEAL); y += 44
        for ln in wrap(d, caption or "", font(SANS, 38), wid):
            d.text((x0, y), ln, font=font(SANS, 38), fill=MUTED); y += 54
    else:
        d.text((184, 44), label or "", font=font(SERIF, 38), fill=INK, anchor="lm")
        if step is not None:
            d.text((W - 184, 44), f"{step+1:02d} / {len(order):02d}", font=font(SANS, 26), fill=MUTED, anchor="rm")
        lines = wrap(d, caption or "", font(SANS, 30), 1560)[:2]
        for i, ln in enumerate(lines):
            d.text((W/2, (1020 if len(lines) == 1 else 1002 + i * 40)), ln, font=font(SANS, 30), fill=INK, anchor="mm")
    return im

# Phone placement / desktop placement
if layout == "phone":
    PH_H = 940; PH_W = round(PH_H * 780 / 1688 / 2) * 2; PX, PY = 300, (H - PH_H) // 2
else:
    PH_W, PH_H, PX, PY = 1552, 873, 184, 84

def add_shadow(im):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    r = 56 if layout == "phone" else 18; pad = 14 if layout == "phone" else 0
    d.rounded_rectangle([PX - pad, PY - pad + 18, PX + PH_W + pad, PY + PH_H + pad + 18], r, fill=(20, 30, 40, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(28)); im = im.convert("RGBA"); im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    if layout == "phone":
        d.rounded_rectangle([PX - pad, PY - pad, PX + PH_W + pad, PY + PH_H + pad], r, fill=(22, 26, 30, 255))
    else:
        d.rounded_rectangle([PX - 2, PY - 2, PX + PH_W + 2, PY + PH_H + 2], r, fill=(210, 205, 196, 255))
    return im.convert("RGB")

# ---- 4. slide sequence (background + text), as concat list with durations
sd = f"{D}/slides"; os.makedirs(sd, exist_ok=True)
slides = [(frame(card=(TITLE, SUB)), INTRO)]
t = INTRO
for (a, b, k, lab, cap_) in windows:
    if a > t: slides.append((add_shadow(frame(label=lab, step=k)), a - t))
    slides.append((add_shadow(frame(label=lab, caption=cap_, step=k)), b - a)); t = b
if INTRO + body_len > t: slides.append((add_shadow(frame(label=windows[-1][3], step=windows[-1][2])), INTRO + body_len - t))
slides.append((frame(card=(BRAND, sys.argv[5] if len(sys.argv) > 5 else "")), OUTRO))
lst = "ffconcat version 1.0\n"
for i, (im, du) in enumerate(slides):
    im.save(f"{sd}/{i:03d}.png"); lst += f"file '{i:03d}.png'\nduration {max(du, 0.04):.3f}\n"
lst += f"file '{len(slides)-1:03d}.png'\n"
open(f"{sd}/list.ffconcat", "w").write(lst)

# rounded mask for footage
m = Image.new("L", (PH_W, PH_H), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, PH_W - 1, PH_H - 1], 44 if layout == "phone" else 14, fill=255); m.save(f"{D}/mask.png")
# fast-forward chip
chip = Image.new("RGBA", (300, 64), (0, 0, 0, 0)); cd = ImageDraw.Draw(chip)
cd.rounded_rectangle([0, 0, 299, 63], 32, fill=(24, 38, 52, 225)); cd.text((150, 32), "▶▶  fast-forward", font=font(SANS, 28, 1), fill=(255, 255, 255), anchor="mm"); chip.save(f"{D}/chip.png")

# ---- 5. audio track
inputs, filt = [], []
for k, b in enumerate(order):
    inputs += ["-i", f"{D}/audio/{b['id']}.wav"]
    ms = int((INTRO + out_t(b["start"]) + 0.15) * 1000)
    filt.append(f"[{k}:a]adelay={ms}|{ms}[a{k}]")
filt.append("".join(f"[a{k}]" for k in range(len(order))) + f"amix=inputs={len(order)}:normalize=0,apad,atrim=0:{INTRO + body_len + OUTRO:.3f}[aout]")
run(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[aout]", "-ar", "48000", f"{D}/voice.wav"])

# ---- 6. final composite (each layer rendered at a fixed 30 fps first, so timing is exact)
total = INTRO + body_len + OUTRO
run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-i", f"{sd}/list.ffconcat",
     "-vf", "fps=30,format=yuv420p", "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "14", f"{D}/slides.mp4"])
# Bezel ring drawn over the footage's square corners (no alpha video needed).
ring = Image.new("RGBA", (W, H), (0, 0, 0, 0)); rd = ImageDraw.Draw(ring)
if layout == "phone":
    rd.rounded_rectangle([PX - 14, PY - 14, PX + PH_W + 14, PY + PH_H + 14], 56, fill=(22, 26, 30, 255))
else:
    rd.rounded_rectangle([PX - 2, PY - 2, PX + PH_W + 2, PY + PH_H + 2], 16, fill=(210, 205, 196, 255))
hole = Image.new("L", (W, H), 0); ImageDraw.Draw(hole).rounded_rectangle([PX, PY, PX + PH_W - 1, PY + PH_H - 1], 44 if layout == "phone" else 14, fill=255)
ring.putalpha(Image.composite(Image.new("L", (W, H), 0), ring.getchannel("A"), hole)); ring.save(f"{D}/ring.png")
enable_ff = "+".join(f"between(t,{a_:.2f},{b_:.2f})" for a_, b_ in fast_windows) or "0"
body = f"between(t,{INTRO:.2f},{INTRO + body_len:.2f})"
fc = (f"[1:v]fps=30,scale={PH_W}:{PH_H}:flags=lanczos,setpts=PTS-STARTPTS+{INTRO}/TB[ph];"
      f"[0:v][ph]overlay={PX}:{PY}:eof_action=pass:enable='{body}'[v1];"
      f"[v1][2:v]overlay=0:0:enable='{body}'[v2];"
      f"[v2][3:v]overlay={PX + PH_W//2 - 150}:{PY + PH_H - 110}:enable='{enable_ff}',format=yuv420p[v]")
run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f"{D}/slides.mp4", "-i", f"{D}/footage.mp4",
     "-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", f"{D}/ring.png",
     "-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", f"{D}/chip.png", "-i", f"{D}/voice.wav",
     "-filter_complex", fc, "-map", "[v]", "-map", "4:a", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
     "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", f"{D}/{name}-demo.mp4"])
print("wrote", f"{D}/{name}-demo.mp4", round(total, 1), "s")
