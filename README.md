# The Privacy Lab AI Editor v2.2

Phone se control karo, Windows PC expert editing karta hai.

## Architecture
- **Android app** (Kotlin/Compose): chat, projects, media picker, red/black theme
- **PC backend** (FastAPI): AI expert brain (Gemini), FFmpeg render, Whisper captions,
  Pexels B-roll, schedule modes, app testing via ADB

## Features
- Auto Edit: ek tap — silences cut, captions, zoom, music duck, 9:16 output
- General Chat + Project Chat (style memory seekhta hai)
- Production Queue + Pause/Resume
- Office-hours slow mode (9-5 half CPU), raat ko PC rest
- Test Mode: emulator mein app test, screenshots + screenrecord + report
- Asset priority: tumhari library (Envato) → Pexels/Pixabay stock

## Setup
SETUP_GUIDE.md dekho — Windows PC par Python + FFmpeg, phir `python main.py`

## API
- GET /health | /projects | /projects/{pid} | /projects/{pid}/status | /integrations
- POST /projects | /projects/{pid}/chat | /projects/{pid}/upload | /projects/{pid}/edit
- POST /projects/{pid}/test | /projects/{pid}/control
