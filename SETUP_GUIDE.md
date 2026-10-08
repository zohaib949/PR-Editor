# THE PRIVACY LAB AI EDITOR — SETUP GUIDE (Windows PC + Phone)
Sab kuch FREE. Step-by-step, 30 minute mein complete.

---

## STEP 1: PC par Python install karo
1. python.org se Python 3.11+ download → install karte waqt **"Add Python to PATH"** tick karna mat bhoolna
2. Check: Command Prompt kholo, likho `python --version` — version dikhna chahiye

## STEP 2: FFmpeg install karo
1. ffmpeg.org/download.html → Windows builds (gyan.dev ya BtbN wala)
2. ZIP kholkar `C:\ffmpeg` mein rakho
3. Environment Variables → Path mein `C:\ffmpeg\bin` add karo
4. Check: nayi CMD kholo → `ffmpeg -version` dikhna chahiye

## STEP 3: Backend chalao
1. `backend` folder khol lo CMD mein
2. `pip install fastapi uvicorn python-multipart`
3. `python main.py` — backend chal gaya ✅
4. Test: browser mein `http://localhost:8000/health` kholo → JSON dikhe

### FREE API keys (optional lekin recommended):
- **Gemini** (asli AI chat): aistudio.google.com → "Get API Key" → free
  - CMD mein: `setx GEMINI_API_KEY "tumhara_key"` phir CMD restart
- **Pexels** (B-roll stock): pexels.com/api → free key → `setx PEXELS_API_KEY "key"`
- Key na ho to bhi app chalegi — offline smart replies + tumhari local library use karegi

### Whisper (captions) — optional:
`pip install openai-whisper` (pehli baar model download hoga, ~150MB)

## STEP 4: PC ka IP pata karo
CMD mein: `ipconfig` → **IPv4 Address** likho (jaise `192.168.1.10`)

## STEP 5: Phone par APK
1. Ye project GitHub repo mein daalo (root mein `android/` folder + workflow)
2. GitHub → Actions → "Build APK" → Run
3. Artifacts se APK download → phone mein install
4. App kholo → PC ka IP dalo → Refresh

## STEP 6: Tumhari Asset Library banao
```
D: ya C: par:
backend/assets/
  Broll/    ← Envato/Pexels clips yahan
  Music/    ← tumhara music
  SFX/      ← sound effects
  Motion/   ← subscribe buttons, lower thirds (Phase 2)
```

## Test Mode (App testing):
1. Android Studio install karo (free)
2. Device Manager → emulator banao (Pixel 6, 2-3GB RAM kaafi)
3. Emulator kholo + `adb` Path mein hona chahiye (Android SDK platform-tools)
4. App mein Test project banao → PC se test steps trigger karo

## Roz ka routine:
- Subah: phone se orders do
- Din: office kaam + editor slow mode (9am-5pm auto)
- Raat 10 baje: PC rest — `shutdown /s /t 0` ya auto (Windows Task Scheduler)
