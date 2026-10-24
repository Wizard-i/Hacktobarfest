# 🚌 কুমিরা বাস বন্ধু

> **IIUC (International Islamic University Chittagong) ছাত্রছাত্রীদের জন্য বাংলা ভয়েস-ফার্স্ট বাস সহকারী।**  
> মাইক্রোফোনে বাংলায় বলুন অথবা টাইপ করুন — Gemma বলবে পরের বাস কখন, কোথায় যাবে, ভাড়া কত।

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-4.x-orange?logo=gradio)](https://gradio.app)
[![Model: Gemma](https://img.shields.io/badge/Model-Gemma%203%2027B-green?logo=google)](https://ai.google.dev/gemma)
[![STT: Whisper](https://img.shields.io/badge/STT-Whisper%20small-purple)](https://github.com/openai/whisper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📌 The Problem

**Who has it:** Every student at IIUC Kumira campus runs into the same problem every week — they don't know when the next university bus leaves, which bus goes to their area, or whether buses even run on a given day. Bus schedule information is scattered across physical notice boards and informal WhatsApp groups. There's no centralized, always-available tool that a student can query in Bengali from their phone.

**How they deal with it today:** They ask friends, check WhatsApp groups, or just show up early and hope a bus comes. If they miss it, they pay extra for a CNG auto-rickshaw.

---

## 💡 The Solution

**কুমিরা বাস বন্ধু** is a Bangla-first voice + text chatbot that answers any question about IIUC bus schedules. A student can ask (by voice or text):

- *"নিউমার্কেটের পরের বাস কখন?"* (When's the next bus to Newmarket?)
- *"শুক্রবার কি ফেনীর বাস আছে?"* (Is there a bus to Feni on Friday?)
- *"অক্সিজেন থেকে কোন বাস ধরব?"* (Which bus from Oxygen area?)

The app answers instantly using **Gemma** (via Gemini API) with full awareness of the current Bangladesh time, day, and all 12 bus routes. A **3-tab interface** covers chat, a live schedule board, and a visual route explorer.

---

## ⚙️ How It Works

### Model(s) Used
| Layer | Model | Link |
|-------|-------|------|
| LLM | **Gemma 3 27B-IT** via Gemini API | [Google AI Studio](https://aistudio.google.com) |
| STT | **OpenAI Whisper** (`small`) — local inference | [github.com/openai/whisper](https://github.com/openai/whisper) |

### Tech Stack
| Component | Technology |
|-----------|-----------|
| Frontend + Backend | **Gradio 4.x** (Python) |
| LLM Client | `google-genai` SDK |
| Speech-to-Text | `openai-whisper` (runs locally, no API key) |
| Data | `data/buses.json` — 12 routes, 40+ trips |
| Timezone | `pytz` — Bangladesh (Asia/Dhaka, GMT+6) |
| Prompt engineering | Custom system prompt with real-time time injection |

### Architecture

```
User (Voice / Text)
       │
       ▼
 Gradio UI (app.py)
       │
   ┌───┴───────────────────┐
   │                       │
   ▼                       ▼
Whisper STT            Text Input
(stt.py)                   │
   │                       │
   └──────────┬────────────┘
              ▼
      prompts.py
  ┌───────────────────────┐
  │  build_system_prompt()│
  │  • Current BD time    │
  │  • Day-aware schedule │
  │  • 12 bus routes      │
  │  • Next bus calc      │
  └──────────┬────────────┘
             ▼
         llm.py
  ┌─────────────────────┐
  │  ask_gemma()        │
  │  • Gemma 3 27B-IT   │
  │  • Multi-turn chat  │
  │  • Gemini API       │
  └──────────┬──────────┘
             ▼
       Answer → User
```

### Datasets
- `data/buses.json` — **Realistic sample data** (made-up, not scraped from real students). 12 routes covering: Newmarket, Agrabad, Hathazari, Feni, Noakhali, Mirsarai, Patengga. Includes fares, distances, pickup points, and special notes.

---

## 🚀 How to Run It

### Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (for Whisper voice input)
- [Google AI Studio API Key](https://aistudio.google.com) (free, for Gemma)

```powershell
# Install FFmpeg (Windows)
winget install FFmpeg
# OR
choco install ffmpeg
```

### 1. Clone the repo
```powershell
git clone https://github.com/<your-username>/kumirabus-bondhu.git
cd kumirabus-bondhu
```

### 2. Install requirements
```powershell
python -m venv venv
venv\Scripts\activate        # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

> ⚠️ First run downloads the Whisper `small` model (~460 MB). This is a one-time download.

### 3. Configure your API key
```powershell
copy .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_api_key_here
GEMMA_MODEL=gemma-3-27b-it
WHISPER_SIZE=small
WHISPER_LANGUAGE=bn
```

### 4. Run the app
```powershell
python app.py
```

The browser opens at **http://localhost:7860** automatically.

### 5. Run tests (optional)
```powershell
pytest tests/ -v
```

---

## 🖥️ Interface

The app has **3 tabs**:

| Tab | What it does |
|-----|-------------|
| 💬 **বাস চ্যাটবট** | Voice + text chatbot with Gemma. Multi-turn conversation, examples panel |
| 📋 **আজকের শিডিউল** | Real-time "next buses" table + full route schedule by dropdown |
| 🗺️ **রুট তথ্য** | Animated route cards (all 12 routes), special notes, contact info |

---

## 📸 Screenshots / Demo

<!-- Add 2-3 screenshots after first run -->
| Chat Tab | Schedule Tab | Route Explorer |
|----------|-------------|----------------|
| ![chat](docs/screenshots/app_main.png) | ![schedule](docs/screenshots/schedule.png) | ![routes](docs/screenshots/routes.png) |

> 📹 **Demo video:** _[Add link after recording]_

---

## 🗂️ Project Structure

```
kumirabus-bondhu/
├── app.py                   # Gradio UI: 3-tab interface
├── src/
│   ├── __init__.py
│   ├── llm.py               # Gemma (Gemini API) — multi-turn chat support
│   ├── prompts.py           # System prompt builder: time + bus data + rules
│   └── stt.py               # Whisper voice → Bangla text
├── data/
│   └── buses.json           # 12 routes, 40+ trips (realistic sample data)
├── tests/
│   ├── __init__.py
│   └── test_prompt.py       # 40+ pytest tests
├── docs/
│   └── screenshots/         # README screenshots
├── requirements.txt
├── .env.example             # API key template
├── .gitignore               # .env, venv, __pycache__, model weights excluded
└── README.md
```

---

## 🗺️ Bus Routes Covered (12 routes)

| Route ID | Route |
|----------|-------|
| R01 | ভার্সিটি → নিউমার্কেট (সিটি রুট) |
| R02 | নিউমার্কেট → ভার্সিটি (ফিরতি) |
| R03 | ভার্সিটি → আগ্রাবাদ → পতেঙ্গা |
| R04 | পতেঙ্গা → ভার্সিটি (ফিরতি) |
| R05 | ভার্সিটি → হাটহাজারী |
| R06 | হাটহাজারী → ভার্সিটি (ফিরতি) |
| R07 | ভার্সিটি → ফেনী (আন্তঃজেলা) |
| R08 | ফেনী → ভার্সিটি (ফিরতি) |
| R09 | ভার্সিটি → নোয়াখালী (বিশেষ) |
| R10 | নোয়াখালী → ভার্সিটি (ফিরতি) |
| R11 | ভার্সিটি → মিরসরাই |
| R12 | মিরসরাই → ভার্সিটি (ফিরতি) |

> **Note:** `data/buses.json` uses realistic but made-up schedules. Real IIUC transport data (when available) can be dropped in with no code changes.

---

## 🛠️ Customization

### Change the LLM model
```env
# In .env
GEMMA_MODEL=gemma-3-12b-it   # lighter, faster
GEMMA_MODEL=gemma-3-27b-it   # stronger (default)
```

### Improve Bangla voice accuracy
```env
WHISPER_SIZE=medium    # better Bangla accuracy (~1.5 GB)
WHISPER_SIZE=large-v3  # best accuracy, slower (~3 GB)
```

### Add real bus routes
Edit `data/buses.json` — follow the existing schema. No code changes needed.

---

## ⚠️ What's Not Done Yet

- **Real IIUC data:** Current schedules are realistic sample/made-up data. The actual IIUC transport office schedule should replace `data/buses.json`.
- **Push notifications:** No live alerts for bus delays or cancellations.
- **Mobile app:** Currently web-only (Gradio). A Telegram bot would reach more students.
- **Whisper accuracy on noisy audio:** Performance degrades with background noise; a denoising step would help.
- **Multi-language:** English questions work but interface labels are Bangla-only.

---

## 📄 Credits

| Library / Resource | Use |
|--------------------|-----|
| [Gradio](https://gradio.app) | Web UI framework |
| [google-genai](https://pypi.org/project/google-genai/) | Gemini API client (Gemma LLM) |
| [openai-whisper](https://github.com/openai/whisper) | Local Bangla speech-to-text |
| [pytz](https://pypi.org/project/pytz/) | Bangladesh timezone (Asia/Dhaka) |
| [Hind Siliguri](https://fonts.google.com/specimen/Hind+Siliguri) | Bangla-compatible Google Font |
| [MLH Hacktoberfest Hack Day Chittagong](https://mlh.io) | Hackathon organizer |
| [pytest](https://pytest.org) | Test framework |

---

## 🏆 Hackathon Checklist

- [x] Repo is public
- [x] `.env` is in `.gitignore` (never committed)
- [x] `requirements.txt` works with `pip install`
- [x] `python app.py` launches the app
- [x] Voice input works (Whisper STT)
- [x] Bangla questions get correct answers
- [x] Open-source models named and linked (Gemma + Whisper)
- [x] Sample data — no real student personal data
- [x] README explains problem, solution, how to run
- [ ] Screenshots added after first run
- [ ] Final commit before deadline
- [ ] Submitted on MLH event page

---

## 📄 License

MIT License — Hackathon project, freely use and adapt.

---

<div align="center">

Made with ❤️ for IIUC students  
**Hacktoberfest Hack Day Chittagong × IEEE Computer Society IIUC SBC**  
Powered by **Gemma** (via Gemini API) + **Whisper** STT

</div>
