#!/usr/bin/env python3
"""Builds a PROTOTYPE of the training video with no AI clips: one illustrated
storyboard panel per scene (camera position and the part of the car in play),
a placeholder computer voice for the narration, and the real captions.

  python3 video/storyboard.py        # writes video/out-prototype/sparqle-washer-training-PROTOTYPE.mp4

Needs espeak-ng (placeholder voice) and Playwright's Chromium (frame rendering).
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out-prototype")
SCENES = json.load(open(os.path.join(HERE, "scenes.json"), encoding="utf-8"))["scenes"]

# Per scene: which part of the car is in play, and where the camera is.
# Camera: 1-8 = the walkaround positions, "orbit" = moving round the car,
# "top" = overhead, "close" = close-up on the zone, "none" = no car in shot.
VIEW = {
    "A1": ("whole", "orbit"), "A2": ("whole", 2),
    "B1": ("whole", 1), "B2": ("whole", 1), "B3": ("whole", "orbit"), "B4": ("wheel", "close"),
    "B5": ("wheel", "close"), "B6": ("bonnet", "close"), "B7": ("door", "close"), "B8": ("door", "close"),
    "B9": ("whole", 7), "B10": ("sill", "close"),
    "C1": ("none", "top"), "C2": ("bonnet", "close"),
    "D1": ("none", "close"), "D2": ("roof", 7), "D3": ("roof", "close"), "D4": ("roof", "close"),
    "D5": ("bonnet", 8), "D6": ("boot", 5), "D7": ("door", 7), "D8": ("mirror", "close"),
    "D9": ("sill", 3), "D10": ("none", 7),
    "E1": ("wheel", "close"), "E2": ("wheel", "close"), "E3": ("windscreen", 2), "E4": ("windscreen", "close"),
    "F1": ("sill", "close"), "F2": ("whole", 7), "F3": ("whole", 7), "F4": ("none", "close"),
    "G1": ("whole", "orbit"), "G2": ("door", 3), "G3": ("whole", 1), "G4": ("whole", "orbit"),
}
ZONE_LABEL = {"whole": "Whole car", "wheel": "Wheel, close up", "bonnet": "Bonnet", "door": "Doors and side panels",
              "sill": "Lower panels and sills", "roof": "Roof", "boot": "Boot and rear", "mirror": "Side mirror",
              "windscreen": "Windscreen", "none": "No car in shot"}
CAM_POS = {1: (160, 35), 2: (75, 83), 3: (40, 200), 4: (75, 317), 5: (160, 365), 6: (245, 317), 7: (280, 200), 8: (245, 83)}
ZONE_SHAPES = {
    "roof": '<rect x="128" y="184" width="64" height="60" rx="8"/>',
    "bonnet": '<path d="M110,100 Q160,86 210,100 L206,150 Q160,136 114,150 Z"/>',
    "boot": '<path d="M114,258 Q160,270 206,258 L210,306 Q160,320 110,306 Z"/>',
    "door": '<rect x="106" y="150" width="20" height="120" rx="6"/><rect x="194" y="150" width="20" height="120" rx="6"/>',
    "sill": '<rect x="104" y="170" width="8" height="110" rx="3"/><rect x="208" y="170" width="8" height="110" rx="3"/>',
    "wheel": '<rect x="98" y="126" width="16" height="42" rx="5"/>',
    "mirror": '<ellipse cx="103" cy="160" rx="10" ry="8"/><ellipse cx="217" cy="160" rx="10" ry="8"/>',
    "windscreen": '<path d="M120,152 Q160,138 200,152 L194,178 Q160,170 126,178 Z"/>',
    "whole": '<rect x="100" y="86" width="120" height="234" rx="42"/>',
}
CAR = """
<ellipse class="path" cx="160" cy="200" rx="120" ry="165" style="opacity:{orbit}"/>
<rect class="wheel" x="100" y="128" width="12" height="38" rx="4"/><rect class="wheel" x="208" y="128" width="12" height="38" rx="4"/>
<rect class="wheel" x="100" y="244" width="12" height="38" rx="4"/><rect class="wheel" x="208" y="244" width="12" height="38" rx="4"/>
<ellipse class="body" cx="103" cy="160" rx="7" ry="5"/><ellipse class="body" cx="217" cy="160" rx="7" ry="5"/>
<rect class="body" x="106" y="92" width="108" height="222" rx="38"/>
<path class="glass" d="M120,152 Q160,138 200,152 L194,178 Q160,170 126,178 Z"/>
<rect class="glass" x="128" y="184" width="64" height="60" rx="8"/>
<path class="glass" d="M126,256 Q160,262 194,256 L200,276 Q160,286 120,276 Z"/>
<text class="lbl" x="160" y="118" text-anchor="middle">FRONT</text><text class="lbl" x="160" y="300" text-anchor="middle">REAR</text>
<g class="zone">{zone}</g>
{camera}
"""
PAGE = """<!doctype html><meta charset="utf-8"><style>
body{{margin:0;width:1280px;height:720px;overflow:hidden;background:#F2F5FA;font-family:"DejaVu Sans",Arial,sans-serif;color:#0E1726;position:relative}}
.panel{{position:absolute;left:60px;top:48px;width:400px;height:520px;background:#fff;border-radius:18px;box-shadow:0 2px 18px rgba(14,23,38,.08)}}
.panel svg{{width:400px;height:500px;margin-top:10px}}
.body{{fill:#F2F5FA;stroke:#3A4557;stroke-width:2}} .glass{{fill:#D5DBE5;stroke:#3A4557;stroke-width:1.5}} .wheel{{fill:#0E1726}}
.lbl{{fill:#3A4557;font:700 11px "DejaVu Sans";letter-spacing:.12em}} .path{{fill:none;stroke:#0E7C66;stroke-width:2;stroke-dasharray:5 6}}
.zone{{fill:#0E7C66;fill-opacity:.35;stroke:#0E7C66;stroke-width:3}}
.cam circle{{fill:#0E1726}} .cam text{{fill:#fff;font:800 13px "DejaVu Sans";text-anchor:middle;dominant-baseline:central}}
.card{{position:absolute;left:520px;top:48px;width:700px;height:520px}}
.eyebrow{{font-size:18px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#0E7C66;margin:0 0 6px}}
h1{{font-size:44px;line-height:1.05;margin:0 0 22px;letter-spacing:-.01em}}
.row{{display:grid;grid-template-columns:150px 1fr;gap:10px 18px;font-size:21px;line-height:1.4;margin-bottom:12px}}
.row b{{color:#3A4557;font-weight:700;font-size:16px;letter-spacing:.08em;text-transform:uppercase;padding-top:5px}}
.shot{{color:#0E1726}}
.tag{{position:absolute;right:60px;top:590px;background:#FFF4DC;color:#8A5A00;font-weight:700;font-size:17px;padding:8px 14px;border-radius:999px}}
.id{{position:absolute;left:60px;top:594px;font-size:17px;color:#3A4557;font-weight:700}}
</style><body>
<div class="panel"><svg viewBox="0 0 320 400">{car}</svg></div>
<div class="card"><p class="eyebrow">{module}</p><h1>{title}</h1>
<div class="row"><b>Shot</b><span class="shot">{shot}</span></div>
<div class="row"><b>Camera</b><span>{camera}</span></div>
<div class="row"><b>Focus</b><span>{zone}</span></div>
<div class="row"><b>Narration</b><span>{vo}</span></div></div>
<div class="id">Scene {sid} of 36</div><div class="tag">PROTOTYPE · the AI-generated clip replaces this panel</div>
</body>"""


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("Command failed: " + " ".join(cmd) + "\n" + r.stderr[-1500:])


def camera_svg(cam):
    if cam == "orbit":
        return ('<path d="M139,37.5 A120,165 0 0 0 95.5,60.9" fill="none" stroke="#0E7C66" stroke-width="3"/>'
                '<g class="cam"><circle cx="160" cy="35" r="15"/><text x="160" y="35">&#9679;</text></g>')
    if cam == "top":
        return '<g class="cam"><circle cx="160" cy="200" r="16"/><text x="160" y="200">&#8593;</text></g>'
    if cam in CAM_POS:
        x, y = CAM_POS[cam]
        return f'<g class="cam"><circle cx="{x}" cy="{y}" r="15"/><text x="{x}" y="{y}">{cam}</text></g>'
    return ""


def camera_label(cam):
    return {"orbit": "Moving slowly all the way round the car", "top": "Looking straight down", "close": "Close up",
            "none": "No car in shot"}.get(cam) or f"Walkaround position {cam}"


def first_sentence(text):
    return re.split(r"(?<=[.!?])\s+", text.strip())[0]


def frames():
    boards = os.path.join(OUT, "boards")
    os.makedirs(boards, exist_ok=True)
    for s in SCENES:
        if s["type"] != "clip":
            continue
        zone, cam = VIEW[s["id"]]
        car = "" if zone == "none" and cam != "top" else CAR.format(
            orbit=1 if cam == "orbit" else 0, zone=ZONE_SHAPES.get(zone, ""), camera=camera_svg(cam))
        module = re.sub(r"\s*\(.*\)$", "", s["module"])
        html = PAGE.format(car=car, module=module, title=s["title"], shot=first_sentence(s["prompt"]),
                           camera=camera_label(cam), zone=ZONE_LABEL[zone], vo=s["vo"], sid=s["id"])
        open(os.path.join(boards, s["id"] + ".html"), "w", encoding="utf-8").write(html)
    run(["node", os.path.join(HERE, "render_boards.js"), boards])


def clips_and_voice():
    os.makedirs(os.path.join(OUT, "clips"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "vo"), exist_ok=True)
    from concurrent.futures import ThreadPoolExecutor

    def one(s):
        if s["vo"]:
            run(["espeak-ng", "-v", "en-gb+f3", "-s", "150", "-p", "45", "-w", os.path.join(OUT, "vo", s["id"] + ".wav"), s["vo"]])
        if s["type"] != "clip":
            return
        clip = os.path.join(OUT, "clips", s["id"] + "_take1.mp4")
        if os.path.exists(clip):
            return
        board = os.path.join(OUT, "boards", s["id"] + ".png")
        # A slow push-in on the still panel, 8 seconds, like a real clip's length.
        # One still frame in; zoompan turns it into 240 frames, which is 8 seconds at 30 fps.
        run(["ffmpeg", "-y", "-v", "error", "-i", board, "-vf",
             "zoompan=z='1+0.03*on/240':d=240:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=30,format=yuv420p",
             "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage", "-crf", "23", clip])

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        list(pool.map(one, SCENES))
    json.dump({s["id"]: [1] for s in SCENES if s["type"] == "clip"}, open(os.path.join(OUT, "picks.json"), "w"))


if __name__ == "__main__":
    frames()
    clips_and_voice()
    env = dict(os.environ, VIDEO_OUT=OUT)
    r = subprocess.run([sys.executable, os.path.join(HERE, "make_video.py"), "build"], env=env, capture_output=True, text=True)
    print(r.stdout[-600:], r.stderr[-600:])
    if r.returncode:
        sys.exit(1)
    built = os.path.join(OUT, "sparqle-washer-training.mp4")
    final = os.path.join(OUT, "sparqle-washer-training-PROTOTYPE.mp4")
    os.replace(built, final)
    print("Prototype:", final)
