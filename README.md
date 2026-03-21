# RecipeMart

Telegram bot that turns an Instagram Reel URL into a structured recipe. It **tries the caption first** (no video download); if the caption has enough info, it returns a recipe and tells you the video was skipped. Otherwise it downloads the reel, extracts text from audio (speech-to-text) and on-screen text (OCR) in parallel, merges with the caption, then uses OpenAI to produce **ingredients in grams/ml** and step-by-step instructions.

## Features

- **Caption-first** – Fetches caption only (no video download). If the caption contains a full recipe, the bot extracts it and replies with "Video download skipped; recipe extracted from caption." Saves time and bandwidth when creators put the recipe in the caption.
- **Full pipeline when needed** – If the caption isn't enough, the bot downloads the video, runs Whisper (STT) and OCR in parallel, then extracts the recipe and tells you "Video was downloaded for processing and then deleted."
- **Standardized ingredients** – All quantities in metric: grams (g) for solids, milliliters (ml) for liquids. Converts from cups, tbsp, “pieces”, etc. automatically.
- **Fast pipeline** – Speech-to-text and OCR run in parallel after download to reduce wait time.
- **Clean output** – Bold section headers and bullet lists in Telegram.
- **Scaling** – After a recipe is loaded, `/scale <n>` scales all numeric ingredient amounts for *n* servings (uses the model’s serving count when present, otherwise a baseline of **4**).
- **Macros** – `/macros` estimates calories, protein, carbs, and fat for the **current** batch (respecting the last `/scale`) and per serving. Values are **AI estimates only**, not lab-tested nutrition (see disclaimer in the bot reply).

## Flow

1. Send an Instagram Reel URL to the bot (e.g. `https://www.instagram.com/reel/...`).
2. Bot replies "Processing your reel…", then:
   - **Caption path:** Fetches metadata (caption only). If the caption is enough, extracts the recipe and replies with "Video download skipped; recipe extracted from caption." and the recipe.
   - **Video path:** If not, downloads the reel → runs Whisper (STT) and OCR in parallel → merges transcript, on-screen text, and caption → GPT recipe extraction → replies with "Video was downloaded for processing and then deleted." and the recipe.
3. Temp files (and any downloaded video) are deleted after each run.
4. **Commands** (after a recipe is loaded; stored in memory until the bot restarts or you send another Reel):
   - `/help` or `/start` — Short usage and command list.
   - `/scale 6` — Scale ingredients for 6 servings.
   - `/macros` — Approximate nutrition for the scaled batch and per serving.

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (for audio extraction / optional trim)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) (OCR)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed via pip)

## Setup

1. Clone or copy this repo, then create a virtualenv and install dependencies:

   ```bash
   cd RecipeMart
   python3 -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set:

   - `TELEGRAM_BOT_TOKEN` – from [@BotFather](https://t.me/BotFather)
   - `OPENAI_API_KEY` – your OpenAI API key (used for Whisper and GPT)

3. Ensure **FFmpeg** and **Tesseract** are on your PATH (or install them; on macOS: `brew install ffmpeg tesseract`).

## Run the bot

From the project root (RecipeMart):

```bash
python -m bot.main
```

The bot uses long-polling. Send any message that contains an Instagram Reel URL; the bot will reply with "Processing your reel…", then a short status line (caption-only vs video downloaded), then the extracted recipe (or an error message). Then use `/scale` and `/macros` as needed.

## Project layout

- `config.py` – env vars, `TEMP_DIR`, pipeline limits
- `bot/main.py` – Telegram app and polling
- `bot/handlers.py` – message handler: detect Reel URL, run pipeline, send status + recipe; stores last recipe in user session
- `bot/commands.py` – `/help`, `/start`, `/scale`, `/macros`
- `bot/formatting.py` – structured recipe → markdown → Telegram HTML; split long messages
- `pipeline/run.py` – caption-first then full pipeline; returns (`Recipe`, used_caption_only)
- `pipeline/recipe_schema.py` – Pydantic models for recipes and macro estimates
- `pipeline/download.py` – `fetch_caption_only` (metadata only) and `download_reel` (video + caption)
- `pipeline/speech_to_text.py` – Whisper API
- `pipeline/ocr.py` – OpenCV + Tesseract
- `pipeline/recipe_ai.py` – OpenAI structured JSON recipe extraction; macro estimation

## Optional env vars

- `INSTAGRAM_COOKIES` – if you get "requested content not available or login required" from Instagram, provide cookies. **Local:** set to the path of a Netscape-format cookies file (e.g. export with a browser extension), e.g. `INSTAGRAM_COOKIES=/path/to/cookies.txt`. **Railway/cloud:** use the **base64-encoded** cookies content: export cookies to `cookies.txt`, run `base64 -i cookies.txt` (macOS) or `base64 cookies.txt` (Linux), and paste the single line into `INSTAGRAM_COOKIES` in your project variables (do not use a file path in cloud envs; long paths can cause errors).
- `OPENAI_RECIPE_MODEL` – model for recipe extraction (default `gpt-4o-mini`)
- `OPENAI_MACROS_MODEL` – optional model for `/macros` (defaults to `OPENAI_RECIPE_MODEL`)
- `STT_MAX_DURATION_SECONDS` – cap audio length for Whisper (default 600)
- `OCR_FRAME_INTERVAL_SECONDS` – seconds between sampled frames (default 2)
- `OCR_MAX_FRAMES` – max frames to OCR (default 60)

## Hosting

Run the bot on a VPS or PaaS (e.g. Railway, Render) with Python, FFmpeg, and Tesseract installed. Temp files are deleted after each job, so disk usage stays low.
