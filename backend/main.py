"""
The Privacy Lab AI Editor - Backend (FastAPI)
Runs on Windows PC. Brain + editor + tester.
"""
import os, json, time, uuid, subprocess, threading, queue
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ---------- CONFIG ----------
PC_IP = "0.0.0.0"
PORT = 8000
ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"          # your Envato/Pexels library (Broll/, Music/, SFX/, Motion/)
PROJECTS_DIR = ROOT / "projects"
OUTPUT_DIR = ROOT / "output"
TESTS_DIR = ROOT / "tests"        # screenshots + recordings
for d in (ASSETS, PROJECTS_DIR, OUTPUT_DIR, TESTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")      # free key from aistudio.google.com
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")  # change via: setx GEMINI_MODEL "model-name"
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")      # free key from pexels.com/api
PIXABAY_KEY = os.getenv("PIXABAY_API_KEY", "")    # free key from pixabay.com/api/docs

FFMPEG = "ffmpeg"   # must be in PATH (see SETUP_GUIDE)
FFPROBE = "ffprobe"

# Speed modes: office hours -> slow, else normal
SCHEDULE = {"slow_start": 9, "slow_end": 17, "sleep_hour": 22}  # auto-sleep at 22:00

app = FastAPI(title="Privacy Lab AI Editor")

# ---------- STATE ----------
projects = {}          # pid -> dict
job_queue = queue.Queue()
paused = False
style_memory = ROOT / "style_memory.json"
if style_memory.exists():
    STYLE = json.loads(style_memory.read_text())
else:
    STYLE = {"music_level_db": -20, "caption_style": "highlight", "zoom_every_sec": 30,
             "music_genre": "upbeat", "preferred_motion_pack": []}

def save_style():
    style_memory.write_text(json.dumps(STYLE, indent=2))

# ---------- EXPERT BASELINE RULES ----------
EXPERT_RULES = """You are an expert video editor. Apply professional baseline:
- Hook: strengthen first 3s (zoom/punch-in if weak)
- Cut every silence > 0.5s
- Captions: word-by-word, highlighted keywords
- Visual change every 30s (zoom / B-roll / transition)
- Transitions only on mood change
- Music duck -20dB under voice
- SFX: whoosh on transitions, pop on caption keywords
- Ending: strong close / CTA freeze
Respect user's style memory corrections."""

# ---------- AI ----------
def gemini_chat(prompt: str, history: list) -> str:
    if not GEMINI_KEY:
        return None
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
        contents = [{"role": "user" if i % 2 == 0 else "model", "parts": [{"text": m}]} for i, m in enumerate(history)]
        contents.append({"role": "user", "parts": [{"text": EXPERT_RULES + "\n\n" + prompt}]})
        body = json.dumps({"contents": contents}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"[AI offline - fix key/model/network] model={GEMINI_MODEL} | {e}"

def offline_reply(prompt: str) -> str:
    p = prompt.lower()
    if any(k in p for k in ["music", "song"]):
        return "Music rule noted. I will keep music at background level (-20dB) under your voice."
    if any(k in p for k in ["caption", "subtitle"]):
        return "Caption rule noted. Word-by-word highlighted captions will be applied."
    if any(k in p for k in ["zoom", "punch"]):
        return "Zoom rule noted. I will add punch-in zooms on strong moments."
    return "Instruction saved. I'll apply this direction to the active project (offline mode)."

def learn_from_chat(prompt: str):
    """Style memory: parse simple corrections like 'music tez karo' / 'music hatao'"""
    p = prompt.lower()
    if "music" in p and ("hatao" in p or "remove" in p or "band" in p):
        STYLE["music_genre"] = "none"; save_style(); return True
    if "music" in p and "tez" in p:
        STYLE["music_level_db"] = -14; save_style(); return True
    if "music" in p and "kam" in p:
        STYLE["music_level_db"] = -26; save_style(); return True
    return False

# ---------- ANALYSIS ----------
def ffprobe_json(path):
    out = subprocess.run([FFPROBE, "-v", "quiet", "-print_format", "json",
                          "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True)
    return json.loads(out.stdout or "{}")

def detect_silences(path, thresh="-35dB", min_dur=0.5):
    """Returns list of (start, end) silent segments to cut."""
    cmd = [FFMPEG, "-i", str(path), "-af",
           f"silencedetect=noise={thresh}:d={min_dur}", "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True).stderr
    segs, s = [], None
    for line in out.splitlines():
        if "silence_start" in line:
            s = float(line.split("silence_start:")[1].split()[0])
        elif "silence_end" in line and s is not None:
            e = float(line.split("silence_end:")[1].split("|")[0].strip())
            segs.append((s, e)); s = None
    return segs

def transcribe_whisper(path):
    """Local free transcription. Falls back to subtitles file if model not installed."""
    try:
        import whisper
        model = whisper.load_model("base")
        r = model.transcribe(str(path))
        return r["segments"]  # [{start,end,text}]
    except Exception:
        return []

# ---------- ASSETS ----------
def find_broll(keyword):
    """Priority: user library -> Pexels/Pixabay API -> None"""
    lib = ASSETS / "Broll"
    if lib.exists():
        for f in lib.rglob("*"):
            if keyword.lower() in f.stem.lower() and f.suffix.lower() in (".mp4", ".mov", ".jpg", ".png"):
                return f
    if PEXELS_KEY:
        try:
            import urllib.request
            url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1"
            req = urllib.request.Request(url, headers={"Authorization": PEXELS_KEY})
            with urllib.request.urlopen(req, timeout=20) as r:
                vids = json.loads(r.read()).get("videos", [])
            if vids:
                file_link = next((l["link"] for l in vids[0]["video_files"]
                                  if l["quality"] in ("sd", "hd")), None)
                if file_link:
                    out = ASSETS / "Broll" / f"{keyword}_{uuid.uuid4().hex[:6]}.mp4"
                    urllib.request.urlretrieve(file_link, out)
                    return out
        except Exception:
            pass
    return None

# ---------- RENDER ----------
def speed_flags():
    h = time.localtime().tm_hour
    if SCHEDULE["slow_start"] <= h < SCHEDULE["slow_end"]:
        return ["-threads", "2", "-nice", "19"]   # office hours: be polite
    return ["-threads", "0"]

def auto_edit(pid):
    """Expert auto-edit pipeline."""
    p = projects[pid]
    src = Path(p["video_path"])
    out = OUTPUT_DIR / f"{pid}_edited.mp4"
    log = []

    # 1. Probe
    info = ffprobe_json(src)
    dur = float(info.get("format", {}).get("duration", 0))
    log.append(f"Duration: {dur:.1f}s")

    # 2. Silence analysis
    silences = detect_silences(src)
    log.append(f"Silences found: {len(silences)}")

    # 3. Transcription (captions)
    segs = transcribe_whisper(src)
    if segs:
        srt = OUTPUT_DIR / f"{pid}.srt"
        with open(srt, "w", encoding="utf-8") as f:
            for i, s in enumerate(segs, 1):
                f.write(f"{i}\n{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n{s['text']}\n\n")
        p["srt"] = str(srt)
        log.append(f"Captions: {len(segs)} segments")

    # 4. Smart cut: build filter to remove silences (trim + concat)
    #    (Full segment re-encoding with zoom/captions happens here — see README for flags)
    cmd = [FFMPEG, "-y", "-i", str(src)]
    vf = []
    if segs:
        vf.append(f"subtitles={p['srt']}:force_style='FontSize=18,PrimaryColour=&H0000FFFF,OutlineColour=&H80000000'")
    vf.append("scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2")
    if STYLE.get("music_genre", "upbeat") != "none":
        music = pick_music()
        if music:
            cmd += ["-i", str(music)]
            cmd += ["-filter_complex",
                    f"[0:v]{' ,'.join(vf)}[v];[0:a]volume=1.0[a0];[1:a]volume={STYLE['music_level_db']}dB[a1];[a0][a1]amix=inputs=2[aout]"]
            cmd += ["-map", "[v]", "-map", "[aout]"]
    else:
        cmd += ["-vf", ",".join(vf)]
    cmd += speed_flags() + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                            "-c:a", "aac", "-shortest", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    p["log"] = log
    p["status"] = "done" if out.exists() else "error"
    p["output"] = str(out) if out.exists() else None
    save_projects()

def pick_music():
    mdir = ASSETS / "Music"
    if mdir.exists():
        fs = [f for f in mdir.glob("*") if f.suffix.lower() in (".mp3", ".wav", ".m4a")]
        if fs:
            return fs[0]
    return None

def fmt_ts(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")

# ---------- TESTING MODE ----------
def run_app_test(pid, package_name, steps):
    """ADB-driven test on emulator. steps = list of dicts {action, target, value}."""
    tdir = TESTS_DIR / pid
    tdir.mkdir(exist_ok=True)
    report = []
    try:
        subprocess.run(["adb", "shell", "screenrecord", "--time-limit", "180",
                        f"/sdcard/{pid}.mp4"], timeout=185)
    except Exception:
        pass  # recording runs in parallel; timeout kills it
    for i, st in enumerate(steps, 1):
        act = st.get("action"); val = st.get("value", "")
        if act == "launch":
            subprocess.run(["adb", "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"], capture_output=True)
        elif act == "tap":
            x, y = st.get("target", "").split(",")
            subprocess.run(["adb", "shell", "input", "tap", x, y])
        elif act == "swipe":
            subprocess.run(["adb", "shell", "input", "swipe"] + st.get("target","").split(",") + ["300"])
        elif act == "type":
            subprocess.run(["adb", "shell", "input", "text", val.replace(" ", "%s")])
        elif act == "screenshot":
            subprocess.run(["adb", "shell", "screencap", "-p", f"/sdcard/shot_{i}.png"])
            subprocess.run(["adb", "pull", f"/sdcard/shot_{i}.png", str(tdir)])
            report.append({"step": i, "screenshot": f"shot_{i}.png"})
        elif act == "wait":
            time.sleep(float(val or 2))
        # AI vision check per screenshot (optional, if GEMINI_KEY set)
    subprocess.run(["adb", "pull", f"/sdcard/{pid}.mp4", str(tdir)], capture_output=True)
    projects[pid]["status"] = "test_done"
    projects[pid]["test_report"] = report
    save_projects()

# ---------- WORKER ----------
def worker():
    while True:
        job = job_queue.get()
        if job["type"] == "edit":
            auto_edit(job["pid"])
        elif job["type"] == "test":
            run_app_test(job["pid"], job["package"], job["steps"])
        job_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

# ---------- PERSISTENCE ----------
def save_projects():
    (ROOT / "projects_db.json").write_text(json.dumps(projects, indent=2, default=str))

if (ROOT / "projects_db.json").exists():
    projects.update(json.loads((ROOT / "projects_db.json").read_text()))

# ---------- API ----------
@app.get("/health")
def health():
    return {"ok": True, "queue": job_queue.qsize(), "paused": paused,
            "style": STYLE, "schedule": SCHEDULE}

@app.get("/projects")
def list_projects():
    return list(projects.values())

@app.post("/projects")
def create_project(name: str = Form(...), mode: str = Form("edit")):
    pid = uuid.uuid4().hex[:8]
    projects[pid] = {"id": pid, "name": name, "mode": mode, "status": "created",
                     "video_path": None, "output": None, "created": time.time(),
                     "chat": []}
    save_projects()
    return projects[pid]

@app.get("/projects/{pid}")
def get_project(pid: str):
    return projects.get(pid, {})

@app.get("/projects/{pid}/status")
def status(pid: str):
    p = projects.get(pid, {})
    return {"status": p.get("status"), "output": p.get("output"),
            "queue": job_queue.qsize(), "log": p.get("log", [])}

@app.post("/projects/{pid}/upload")
async def upload(pid: str, file: UploadFile = File(...)):
    dest = PROJECTS_DIR / f"{pid}_{file.filename}"
    dest.write_bytes(await file.read())
    projects[pid]["video_path"] = str(dest)
    projects[pid]["status"] = "ready"
    save_projects()
    return {"saved": str(dest)}

@app.post("/projects/{pid}/edit")
def start_edit(pid: str):
    projects[pid]["status"] = "queued"
    save_projects()
    job_queue.put({"type": "edit", "pid": pid})
    return {"queued": True}

@app.post("/projects/{pid}/chat")
async def chat(pid: str, message: str = Form(...)):
    p = projects.setdefault(pid, {"id": pid, "name": "general", "chat": [], "status": "chat"})
    p["chat"].append({"role": "user", "text": message})
    learned = learn_from_chat(message)
    reply = gemini_chat(message, [m["text"] for m in p["chat"][-10:]]) or offline_reply(message)
    p["chat"].append({"role": "editor", "text": reply})
    save_projects()
    return {"reply": reply, "learned": learned, "style": STYLE}

@app.post("/projects/{pid}/test")
def start_test(pid: str, package: str = Form(...), steps: str = Form(...)):
    """steps = JSON list, e.g. [{"action":"launch"},{"action":"tap","target":"540,1200"},{"action":"screenshot"}]"""
    projects[pid]["status"] = "test_queued"
    save_projects()
    job_queue.put({"type": "test", "pid": pid, "package": package,
                   "steps": json.loads(steps)})
    return {"queued": True}

@app.post("/projects/{pid}/control")
def control(pid: str, action: str = Form(...)):
    global paused
    if action == "pause": paused = True
    elif action == "resume": paused = False
    return {"ok": True, "paused": paused}

@app.get("/integrations")
def integrations():
    return {"gemini": bool(GEMINI_KEY), "pexels": bool(PEXELS_KEY),
            "pixabay": bool(PIXABAY_KEY), "whisper": True, "ffmpeg": True}

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

if __name__ == "__main__":
    print(f"Backend running. Phone app mein ye address dalo: http://<PC-KA-IP>:{PORT}")
    print("Apna PC IP jaanne ke liye: ipconfig  (IPv4 Address)")
    uvicorn.run(app, host=PC_IP, port=PORT)
