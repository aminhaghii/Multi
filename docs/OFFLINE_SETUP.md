# 🔌 Offline Setup Guide

This project can run **100% OFFLINE** after initial model download.

## 📋 Prerequisites

- Python 3.8+
- pip
- **Internet connection ONLY for first-time setup**

---

## 🚀 First-Time Setup (Requires Internet)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Download All Models (ONE TIME ONLY)

Run this script **once** with internet to download all models:

```bash
python download_models.py
```

This will download (~500MB):
- ✅ Sentence Transformer (all-MiniLM-L6-v2) → embedding model
- ✅ BLIP Image Captioning → image understanding

Models are cached in:
- `./model_cache/` (local project cache)
- `~/.cache/huggingface/` (system cache)

### Step 3: Upload Sample Documents (Optional)

Use the web UI to upload PDF/DOCX/MD/TXT documents to populate your knowledge base.

---

## 🌐 Running Offline

After initial setup, **disconnect from internet** and run:

```bash
python api_server.py
```

Then open: **http://127.0.0.1:8000**

### ✅ What Works Offline:
- ✅ FastAPI server startup
- ✅ All UI assets (local CSS/JS/fonts)
- ✅ Document ingestion (PDF, Word, Markdown, Text, RTF)
- ✅ Vector search with FAISS
- ✅ LLM inference (if using local llama.cpp)
- ✅ Image captioning with BLIP
- ✅ Full chat and reasoning pipeline

### ❌ What Requires Internet (if not pre-downloaded):
- ❌ First-time model downloads
- ❌ CDN resources (now replaced with local files)

---

## 📦 Sharing the Project

To share this project with someone else:

1. **Zip the entire folder** including:
   - All Python files
   - `./model_cache/` folder (if you want to include models)
   - `./static/` folder
   - `requirements.txt`

2. **On the new machine**, recipient should:
   - Extract the ZIP
   - Install dependencies: `pip install -r requirements.txt`
   - If models NOT included in ZIP, run: `python download_models.py` (requires internet)
   - Start server: `python api_server.py`

---

## 🔧 Troubleshooting

### Issue: "Model not found" error on startup
**Solution:** Run `python download_models.py` with internet

### Issue: UI assets not loading
**Solution:** Check that `./static/tailwind.min.css`, `./static/fontawesome.min.css`, and `./static/d3.min.js` exist

### Issue: LLM server offline
**Solution:** Make sure llama.cpp server is running on `http://127.0.0.1:8080` or configure fallback

---

## 📁 Project Structure (Offline-Ready)

```
Multi_agent/
├── api_server.py          # FastAPI backend
├── main_engine.py         # Orchestrator
├── vector_store.py        # FAISS + embeddings
├── image_captioner.py     # BLIP captioning
├── ingestion.py           # Document processing
├── download_models.py     # One-time model downloader
├── requirements.txt       # Dependencies
├── model_cache/           # Local model cache (created on first run)
├── static/
│   ├── index.html         # Main UI
│   ├── tailwind.min.css   # Offline Tailwind
│   ├── fontawesome.min.css # Offline Font Awesome
│   └── d3.min.js          # Offline D3 (minimal)
├── faiss_db/              # Vector store persistence
├── data/                  # Uploaded documents
└── cache.db               # Query cache
```

---

## ✨ Fully Offline Operation Confirmed

- 🌐 **No CDN dependencies** (Tailwind, Font Awesome, D3 are local)
- 🤖 **No model downloads** (after first run)
- 🔒 **No internet required** for normal operation
- 📦 **Portable** - zip and share with others

---

**You can now run this project on an air-gapped machine!** 🎉
