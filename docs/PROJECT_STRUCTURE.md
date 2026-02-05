# 📁 ساختار پروژه - Multi-Agent Research Assistant

## 🎯 ساختار پیشنهادی (بعد از مرتب‌سازی)

```
Multi_agent/
├── 📂 src/                          # کد اصلی برنامه
│   ├── agents/                      # Agent های مختلف
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── specific_agents.py       # QueryUnderstanding, Reasoning, Verification
│   │   └── hybrid_retrieval.py      # Retrieval Agent
│   ├── core/                        # هسته سیستم
│   │   ├── __init__.py
│   │   ├── capability_registry.py
│   │   └── session_manager.py
│   ├── database/                    # مدیریت دیتابیس
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── models.py
│   ├── api_server.py               # FastAPI server
│   ├── main_engine.py              # Orchestrator اصلی
│   ├── llm_client.py               # کلاینت LLM
│   ├── cache.py                    # سیستم کش
│   ├── vector_store.py             # FAISS vector store
│   ├── ingestion.py                # پردازش اسناد
│   ├── image_captioner.py          # کپشن تصاویر
│   ├── voice_transcriber.py        # رونویسی صوت
│   └── export_utils.py             # ابزار export
│
├── 📂 static/                       # فایل‌های استاتیک UI
│   ├── index.html                   # رابط کاربری اصلی
│   ├── tailwind.min.css
│   ├── fontawesome.min.css
│   └── d3.min.js
│
├── 📂 config/                       # تنظیمات
│   ├── settings.py
│   ├── agent_rules.yaml
│   └── capabilities.yaml
│
├── 📂 scripts/                      # اسکریپت‌های کمکی
│   ├── download_models.py
│   ├── run_qwen_server.bat
│   └── start_llama_server.bat
│
├── 📂 tests/                        # تست‌ها
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── 📂 docs/                         # مستندات
│   ├── README.md                    # راهنمای اصلی
│   ├── PROJECT_STRUCTURE.md         # این فایل
│   ├── SETUP.md                     # راهنمای نصب
│   ├── API_DOCS.md                  # مستندات API
│   └── CHANGELOG.md                 # تاریخچه تغییرات
│
├── 📂 data/                         # داده‌های runtime (gitignored)
│   ├── faiss_db/                    # پایگاه وکتور
│   ├── cache/                       # کش پاسخ‌ها
│   ├── exports/                     # فایل‌های export شده
│   └── extracted_images/            # تصاویر استخراج شده
│
├── 📂 logs/                         # لاگ‌ها (gitignored)
│
├── .gitignore
├── requirements.txt
└── app.py                          # Entry point (اختیاری)
```

---

## 🗑️ فایل‌های قابل حذف

### 1. **فایل‌های تکراری و قدیمی**
- ❌ `static/index_new_backup.html` - بکاپ قدیمی
- ❌ `run_qwen_server - Copy.bat` - کپی تکراری
- ❌ `app.py` - اگر فقط `api_server.py` استفاده می‌شود
- ❌ `model_server_vl.py` - اگر استفاده نمی‌شود
- ❌ `cudart64_12.dll` - باید در محیط سیستم باشد نه در پروژه

### 2. **فولدرهای خالی**
- ❌ `agents/base/`, `agents/meta/`, `agents/specialized/`
- ❌ `api/middleware/`, `api/websocket/`, `api/routes/` (اگر خالی هستند)
- ❌ `config/prompts/`
- ❌ `database/migrations/`
- ❌ `frontend/` (همه فایل‌ها 0 بایت - غیرفعال)
- ❌ `rag/`, `scripts/`, `models/`
- ❌ `tests/unit/`, `tests/integration/`, `tests/e2e/` (اگر خالی)
- ❌ `agent_workspace/`, `.cache/`

### 3. **گزارش‌های تکراری در root**
این فایل‌ها باید به `docs/` منتقل شوند:
- 📄 `BUG_FIXES_REPORT.md`
- 📄 `COMPREHENSIVE_TEST_REPORT.md`
- 📄 `FIX.md`
- 📄 `IMPLEMENTATION_SUMMARY.md`
- 📄 `OFFLINE_CHANGES_SUMMARY.md`
- 📄 `OFFLINE_SETUP.md`
- 📄 `PROJECT.md`
- 📄 `TEST_REPORT.md`
- 📄 `UI_TEST_REPORT.md`

### 4. **فایل‌های لاگ موقت**
- ❌ `app.log` - باید در `logs/` باشد
- ❌ `map.md` (82KB) - اگر قدیمی است

---

## 📦 فولدرهای Runtime (در .gitignore)

این فولدرها در زمان اجرا ایجاد می‌شوند:
```
data/
├── faiss_db/          # FAISS index
├── cache/             # SQLite cache
├── exports/           # Exported chats
└── extracted_images/  # PDF images

logs/                  # Application logs
model_cache/           # Hugging Face models
agent_workspace/       # Agent temp files
```

---

## 🔧 فایل‌های اصلی پروژه

### Backend Core
- `api_server.py` - سرور FastAPI
- `main_engine.py` - Orchestrator
- `llm_client.py` - LLM interface
- `cache.py` - Response cache
- `vector_store.py` - FAISS wrapper
- `ingestion.py` - Document processor

### Agents
- `agents/specific_agents.py` - تمام agent ها
- `agents/hybrid_retrieval.py` - Retrieval logic

### Database
- `database/models.py` - SQLAlchemy models
- `database/connection.py` - DB connection

### UI
- `static/index.html` - Single-page app
- `static/*.css`, `static/*.js` - Assets

---

## 🚀 نقاط ورودی

1. **API Server**: `python api_server.py`
2. **Download Models**: `python scripts/download_models.py`
3. **LLM Server**: `scripts/start_llama_server.bat`

---

## 📝 توصیه‌ها

1. ✅ همه کدهای Python را در `src/` قرار بده
2. ✅ مستندات را در `docs/` جمع کن
3. ✅ اسکریپت‌های اجرایی را در `scripts/` بگذار
4. ✅ فولدرهای خالی را حذف کن
5. ✅ فایل‌های تکراری/بکاپ را پاک کن
6. ✅ `.gitignore` را به‌روز کن برای `data/`, `logs/`

---

**تاریخ ایجاد:** 5 فوریه 2026  
**نسخه:** 1.0
