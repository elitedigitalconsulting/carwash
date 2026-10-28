#!/usr/bin/env python3
"""Makes the Sparqle washer training video with Google's Gemini API.

Veo generates each scene's clip, Gemini text-to-speech reads the voiceover,
and ffmpeg adds the captions and joins everything into one MP4.

Needs GEMINI_API_KEY in the environment (a key from a Google AI Studio project
with billing on; Veo isn't on the free tier). Standard library only, plus ffmpeg.

  python3 video/make_video.py models            # which Veo and TTS models the key can use
  python3 video/make_video.py estimate          # seconds of video to generate, per take
  python3 video/make_video.py clip A1           # generate one scene (good first test)
  python3 video/make_video.py clips             # generate every scene not done yet
  python3 video/make_video.py pick D3 2         # use take 2 for D3 (or "1,2" to play both)
  python3 video/make_video.py voice             # generate all voiceover lines
  python3 video/make_video.py build             # assemble out/sparqle-washer-training.mp4
  python3 video/make_video.py selftest          # build with placeholder clips and silence, no API

Everything goes in video/out/ (not committed). Re-running skips work already done.
"""
import base64, json, os, re, subprocess, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
API = "https://generativelanguage.googleapis.com/v1beta"
W, H, FPS = 1280, 720, 30
GREEN = "0x0E7C66"
NEGATIVE = ("text, captions, subtitles, watermark, logo text, garbled letters, readable number plate, "
            "extra fingers, deformed hands, scrubbing in circles, car changing shape, music")
TTS_STYLE = ("Read this as the narrator of a workplace training video: a warm, clear, friendly Australian "
             "voice, calm and unhurried, like an experienced supervisor explaining to a new starter. Text: ")

DATA = json.load(open(os.path.join(HERE, "scenes.json"), encoding="utf-8"))
SCENES = DATA["scenes"]
FIXED = DATA["fixed"]


# ---------- helpers ----------

def path(*p):
    full = os.path.join(OUT, *p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        sys.exit("GEMINI_API_KEY isn't set. Add it to the environment's secrets, then start a new session.")
    return k


def call(method, url, body=None, raw=False, timeout=120):
    req = urllib.request.Request(url, method=method, headers={"x-goog-api-key": key(), "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return data if raw else json.loads(data or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"{e.code} from {url.split('?')[0]}: {detail[:800]}") from None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd) + "\n" + r.stderr[-2000:])
    return r.stdout


def duration(f):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).strip())


def scene(sid):
    for s in SCENES:
        if s["id"] == sid:
            return s
    sys.exit(f"No scene {sid}. Scenes: {', '.join(s['id'] for s in SCENES)}")


def full_prompt(s):
    parts = [FIXED["style"], FIXED["car"], FIXED["washer"]]
    if s["setting"]:
        parts.append(FIXED["setting"])
    return " ".join(parts + [s["prompt"]])


def est_vo_seconds(s):
    return len(s["vo"].split()) / 2.5  # a calm narration pace


def default_takes(s):
    # One 8-second take covers about 12 seconds of narration (slowed a little, then a short hold).
    # Longer lines get a second take played straight after, instead of a long freeze.
    return 2 if est_vo_seconds(s) > 12.5 else 1


def picks():
    try:
        return json.load(open(path("picks.json")))
    except FileNotFoundError:
        return {}


# ---------- models ----------

def list_models():
    out, token = [], ""
    while True:
        r = call("GET", f"{API}/models?pageSize=1000" + (f"&pageToken={token}" if token else ""))
        out += r.get("models", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def version_key(name):
    return [int(x) for x in re.findall(r"\d+", name)[:2]]


def pick_model(kind):
    env = os.environ.get("VEO_MODEL" if kind == "veo" else "TTS_MODEL")
    if env:
        return env if env.startswith("models/") else "models/" + env
    models = list_models()
    if kind == "veo":
        c = [m["name"] for m in models if "veo" in m["name"] and "predictLongRunning" in m.get("supportedGenerationMethods", [])]
        c.sort(key=lambda n: (version_key(n), "fast" not in n, "preview" not in n), reverse=True)
    else:
        c = [m["name"] for m in models if "tts" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
        c.sort(key=lambda n: (version_key(n), "flash" in n), reverse=True)
    if not c:
        sys.exit(f"This key can't use any {kind.upper()} model. Run 'models' to see what it can use.")
    return c[0]


def cmd_models():
    for m in list_models():
        n = m["name"]
        if "veo" in n or "tts" in n:
            print(n, "|", ", ".join(m.get("supportedGenerationMethods", [])))
    print("\nWould use:", pick_model("veo"), "and", pick_model("tts"))


def cmd_estimate():
    clips = [s for s in SCENES if s["type"] == "clip"]
    takes = sum(default_takes(s) for s in clips)
    print(f"{len(clips)} scenes, {takes} clips at about 8 seconds = about {takes * 8} seconds of video per full run.")
    print("Multiply by the per-second price of the Veo model on Google's pricing page; re-dos add to it.")


# ---------- video clips ----------

def generate_take(s, take, model):
    out = path("clips", f"{s['id']}_take{take}.mp4")
    if os.path.exists(out):
        print(f"  {s['id']} take {take}: already made")
        return out
    body = {"instances": [{"prompt": full_prompt(s)}],
            "parameters": {"aspectRatio": "16:9", "negativePrompt": NEGATIVE, "personGeneration": "allow_all"}}
    try:
        op = call("POST", f"{API}/{model}:predictLongRunning", body)
    except RuntimeError as e:
        if "400" not in str(e):
            raise
        body["parameters"] = {"aspectRatio": "16:9"}  # some models reject the optional settings
        op = call("POST", f"{API}/{model}:predictLongRunning", body)
    name, start = op["name"], time.time()
    print(f"  {s['id']} take {take}: generating", end="", flush=True)
    while not op.get("done"):
        if time.time() - start > 900:
            raise RuntimeError(f"{s['id']} take {take}: still not done after 15 minutes ({name})")
        time.sleep(10)
        print(".", end="", flush=True)
        op = call("GET", f"{API}/{name}")
    print()
    if "error" in op:
        raise RuntimeError(f"{s['id']} take {take}: {op['error']}")
    resp = op.get("response", {}).get("generateVideoResponse", {})
    samples = resp.get("generatedSamples") or []
    if not samples:
        reasons = resp.get("raiMediaFilteredReasons") or resp
        raise RuntimeError(f"{s['id']} take {take}: no video returned. Google said: {reasons}")
    open(out, "wb").write(call("GET", samples[0]["video"]["uri"], raw=True, timeout=300))
    review_frames(s["id"], take)
    return out


def review_frames(sid, take):
    clip = path("clips", f"{sid}_take{take}.mp4")
    d = duration(clip)
    for i, t in enumerate((0.15, 0.5, 0.85), 1):
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{d * t:.2f}", "-i", clip, "-frames:v", "1", "-vf", "scale=640:-2",
             path("frames", f"{sid}_take{take}_{i}.jpg")])


def cmd_clip(sid, takes=None):
    s = scene(sid)
    if s["type"] != "clip":
        sys.exit(f"{sid} is a title card; it's made in the build step.")
    model = pick_model("veo")
    for t in range(1, (takes or default_takes(s)) + 1):
        generate_take(s, t, model)
    print(f"Done. Review frames in {path('frames')}")


def cmd_clips():
    model = pick_model("veo")
    print("Using", model)
    failed = []
    for s in SCENES:
        if s["type"] != "clip":
            continue
        for t in range(1, default_takes(s) + 1):
            try:
                generate_take(s, t, model)
            except RuntimeError as e:
                print("  FAILED:", e)
                failed.append(f"{s['id']} take {t}")
    print("All scenes done." if not failed else "Failed: " + ", ".join(failed) + ". Run again to retry them.")


def cmd_pick(sid, takes):
    p = picks()
    p[sid] = [int(t) for t in takes.split(",")]
    json.dump(p, open(path("picks.json"), "w"), indent=1)
    print(f"{sid} will use take(s) {p[sid]}")


# ---------- voiceover ----------

def cmd_voice(voice="Kore"):
    model = pick_model("tts")
    print("Using", model, "voice", voice)
    for s in SCENES:
        if not s["vo"]:
            continue
        out = path("vo", f"{s['id']}.wav")
        if os.path.exists(out):
            continue
        body = {"contents": [{"parts": [{"text": TTS_STYLE + s["vo"]}]}],
                "generationConfig": {"responseModalities": ["AUDIO"],
                                     "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
        r = call("POST", f"{API}/{model}:generateContent", body, timeout=180)
        part = r["candidates"][0]["content"]["parts"][0]["inlineData"]
        rate = re.search(r"rate=(\d+)", part.get("mimeType", ""))
        pcm = path("vo", f"{s['id']}.pcm")
        open(pcm, "wb").write(base64.b64decode(part["data"]))
        run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", rate.group(1) if rate else "24000", "-ac", "1", "-i", pcm, out])
        os.remove(pcm)
        print(f"  {s['id']}: {duration(out):.1f}s")
    print("Voiceover done.")


# ---------- assembly ----------

def ass_escape(t):
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def ass_file(name, dur, lines):
    """lines: (style, text) pairs. Styles: Caption (lower third), Eyebrow (top left), Title and Sub (centred cards)."""
    end = f"0:{int(dur // 60):02d}:{dur % 60:05.2f}"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,30,&H00FFFFFF,&H00FFFFFF,&H40261710,&H40261710,1,0,0,0,100,100,0,0,3,12,0,2,90,90,42,1
Style: Eyebrow,DejaVu Sans,20,&H00FFFFFF,&H00FFFFFF,&H66667C0E,&H66667C0E,1,0,0,0,100,100,1,0,3,7,0,7,36,36,30,1
Style: Title,DejaVu Sans,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,120,120,0,1
Style: Sub,DejaVu Sans,28,&H00E3F4EF,&H00E3F4EF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,120,120,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    f = path("tmp", name + ".ass")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(head)
        for style, text in lines:
            if text:
                fh.write(f"Dialogue: 0,0:00:00.00,{end},{style},,0,0,0,,{ass_escape(text)}\n")
    return f


ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def module_parts(m):
    """'Module B: Before you touch the car (≈ 2 min)' -> ('B', 'Before you touch the car')"""
    m = re.sub(r"\s*\(.*\)$", "", m or "")
    hit = re.match(r"Module ([A-Z]): (.*)", m)
    return (hit.group(1), hit.group(2)) if hit else ("", m)


def build_card(name, title, sub, dur, vo=None):
    out = path("segments", name + ".mp4")
    ass = ass_file(name, dur, [("Title", title), ("Sub", sub)])
    audio = (["-i", vo] if vo else ["-f", "lavfi", "-t", f"{dur:.2f}", "-i", "anullsrc=r=48000:cl=stereo"])
    af = (["-af", f"adelay=400|400,apad,atrim=0:{dur:.2f}"] if vo else [])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{dur:.2f}", "-i", f"color=c={GREEN}:s={W}x{H}:r={FPS}", *audio,
         "-vf", f"subtitles={ass}", *af, "-map", "0:v", "-map", "1:a", "-t", f"{dur:.2f}", *ENC, out])
    return out


def build_clip(s, clips, vo):
    """Plays the chosen takes back to back, slows them slightly or holds the last frame if the voiceover runs longer."""
    out = path("segments", s["id"] + ".mp4")
    vo_d = duration(vo) if vo else 0
    clip_d = sum(duration(c) for c in clips)
    target = max(clip_d, vo_d + 0.9)
    slow = min(target / clip_d, 1.25)
    hold = max(0.0, target - clip_d * slow)
    inputs, chains = [], []
    for i, c in enumerate(clips):
        inputs += ["-i", c]
        chains.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v{i}]")
    joined = "".join(f"[v{i}]" for i in range(len(clips)))
    ass = ass_file(s["id"], target, [("Caption", s["caption"]), ("Eyebrow", "Module %s · %s" % module_parts(s["module"]))])
    chains.append(f"{joined}concat=n={len(clips)}:v=1:a=0,setpts={slow:.4f}*PTS,tpad=stop_mode=clone:stop_duration={hold:.2f},"
                  f"subtitles={ass}[vout]")
    n = len(clips)
    if vo:
        inputs += ["-i", vo]
        chains.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=400|400,apad,atrim=0:{target:.2f}[aout]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{target:.2f}", "-i", "anullsrc=r=48000:cl=stereo"]
        chains.append(f"[{n}:a]atrim=0:{target:.2f}[aout]")
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chains), "-map", "[vout]", "-map", "[aout]",
         "-t", f"{target:.2f}", *ENC, out])
    return out


def cmd_build(placeholder=False):
    p = picks()
    segs, missing, last_module = [], [], None
    for s in SCENES:
        if s["module"] != last_module and not s["id"].startswith("A"):
            letter, name = module_parts(s["module"])
            segs.append(build_card("card_" + s["id"], name, "Module " + letter, 2.8))
        last_module = s["module"]
        vo = path("vo", f"{s['id']}.wav") if s["vo"] else None
        if vo and not os.path.exists(vo):
            if not placeholder:
                missing.append(f"voiceover {s['id']}")
                continue
            run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{est_vo_seconds(s):.1f}", "-i", "anullsrc=r=24000:cl=mono", vo])
        if s["type"] == "card":
            sub = "Scenes in this video were created with AI for training" if s["id"] == "G5" else "Sparqle washer training"
            segs.append(build_card(s["id"], s["caption"], sub, 4.0 if not vo else duration(vo) + 1.2, vo))
            continue
        takes = p.get(s["id"]) or list(range(1, default_takes(s) + 1))
        clips = [path("clips", f"{s['id']}_take{t}.mp4") for t in takes]
        if placeholder:
            for c in clips:
                if not os.path.exists(c):
                    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", "8", "-i", f"testsrc2=s=1280x720:r=24", c])
        absent = [c for c in clips if not os.path.exists(c)]
        if absent:
            missing += [os.path.basename(c) for c in absent]
            continue
        segs.append(build_clip(s, clips, vo))
        print(f"  {s['id']} ready")
    if missing:
        sys.exit("Can't build yet. Missing: " + ", ".join(missing))
    lst = path("tmp", "segments.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for f in segs))
    final = path("sparqle-washer-training" + ("-SELFTEST" if placeholder else "") + ".mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", final])
    print(f"Built {final}: {duration(final) / 60:.1f} minutes")


if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    if a[0] == "models": cmd_models()
    elif a[0] == "estimate": cmd_estimate()
    elif a[0] == "clip" and len(a) >= 2: cmd_clip(a[1], int(a[2]) if len(a) > 2 else None)
    elif a[0] == "clips": cmd_clips()
    elif a[0] == "pick" and len(a) == 3: cmd_pick(a[1], a[2])
    elif a[0] == "voice": cmd_voice(*(a[1:2] or []))
    elif a[0] == "build": cmd_build()
    elif a[0] == "selftest":
        OUT = os.path.join(HERE, "out-selftest")
        cmd_build(placeholder=True)
    else: print(__doc__)
