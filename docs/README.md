# 🤖 Multi-Agent Research Assistant

یک دستیار هوشمند تحقیقاتی مبتنی بر معماری چند-عامله (Multi-Agent) با قابلیت RAG (Retrieval-Augmented Generation) برای پاسخ‌دهی دقیق به سوالات بر اساس اسناد آپلود شده.

---

## ✨ ویژگی‌های اصلی

- 🧠 **معماری Multi-Agent**: QueryUnderstanding, Retrieval, Reasoning, Verification
- 📚 **RAG پیشرفته**: جستجوی هیبریدی (Vector + Keyword + Section)
- 🖼️ **پشتیبانی Multimodal**: پردازش تصاویر (BLIP) و صوت (Whisper)
- 💾 **کش هوشمند**: SQLite cache با TTL و KB state tracking
- 🎨 **رابط کاربری مدرن**: UI به سبک Manus AI با Tailwind CSS
- 🌐 **Offline-First**: تمام مدل‌ها به‌صورت local کش می‌شوند
- 📊 **Export چندگانه**: Markdown, HTML, PDF

---

## 📋 پیش‌نیازها

- Python 3.10+
- 8GB+ RAM (16GB توصیه می‌شود)
- GPU (اختیاری، برای سرعت بیشتر)

---

## 🚀 نصب و راه‌اندازی

### 1. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 2. دانلود مدل‌ها (اولین بار)

```bash
python scripts/download_models.py
```

این اسکریپت مدل‌های زیر را دانلود می‌کند:
- `sentence-transformers/all-MiniLM-L6-v2` (Embeddings)
- `Salesforce/blip-image-captioning-base` (Image Captioning)

### 3. راه‌اندازی سرور LLM

**گزینه A: llama-cpp-python (توصیه می‌شود)**
```bash
scripts/start_llama_server.bat
```

**گزینه B: Qwen2-VL**
```bash
scripts/run_qwen_server.bat
```

### 4. اجرای سرور اصلی

```bash
python api_server.py
```

سرور روی `http://127.0.0.1:8000` اجرا می‌شود.

---

## 📁 ساختار پروژه

```
Multi_agent/
├── agents/              # Multi-agent system
├── core/                # Session & capability management
├── database/            # SQLAlchemy models
├── config/              # Settings & YAML configs
├── static/              # UI (index.html + assets)
├── scripts/             # Helper scripts
├── docs/                # Documentation
├── tests/               # Test files
├── api_server.py        # FastAPI server
├── main_engine.py       # Orchestrator
├── llm_client.py        # LLM interface
├── cache.py             # Response cache
├── vector_store.py      # FAISS wrapper
├── ingestion.py         # Document processor
└── requirements.txt
```

برای جزئیات بیشتر: [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)

---

## 🎯 استفاده

1. **آپلود اسناد**: از دکمه "Upload Files" استفاده کنید
   - پشتیبانی: PDF, DOCX, MD, TXT, RTF
   - تصاویر: PNG, JPG, JPEG
   - صوت: WAV, MP3, M4A, OGG

2. **پرسش سوال**: سوال خود را در input box تایپ کنید

3. **مشاهده نتایج**: پاسخ با metadata (confidence, verification, sources) نمایش داده می‌شود

4. **Export**: گفتگو را به فرمت‌های مختلف export کنید

---

## 🔧 تنظیمات

### تنظیمات LLM
در `llm_client.py`:
- `LLM_SERVER_BASE_URL`: آدرس سرور LLM
- `max_tokens`, `temperature`: پارامترهای generation

### تنظیمات Cache
در `cache.py`:
- `DEFAULT_TTL`: مدت زمان اعتبار کش (پیش‌فرض: 7 روز)

### تنظیمات Vector Store
در `vector_store.py`:
- `model_name`: مدل embedding (پیش‌فرض: all-MiniLM-L6-v2)

---

## 🧪 تست

```bash
# اجرای تست‌های MCP
pytest tests/mcp/
```

---

## 📊 API Endpoints

### چت
- `POST /api/chat` - پاسخ ساده
- `POST /api/chat/stream` - پاسخ استریم (SSE)

### آپلود
- `POST /api/upload/document` - آپلود سند
- `POST /api/upload/image` - آپلود تصویر
- `POST /api/upload/audio` - آپلود صوت

### مدیریت
- `GET /api/stats` - آمار سیستم
- `GET /api/kb/documents` - لیست اسناد
- `DELETE /api/kb/documents/{file_hash}` - حذف سند
- `DELETE /api/kb/clear` - پاک کردن همه اسناد

### Session
- `GET /api/sessions/recent` - لیست session ها
- `POST /api/sessions` - ایجاد session جدید
- `GET /api/sessions/{session_id}` - دریافت session

---

## 🐛 عیب‌یابی

### مشکل: LLM Offline
- بررسی کنید سرور LLM روی پورت 8080 در حال اجراست
- لاگ‌ها را در `logs/` چک کنید

### مشکل: Document Count = 0
- مطمئن شوید فایل‌ها با موفقیت آپلود شده‌اند
- `faiss_db/` را بررسی کنید

### مشکل: Out of Memory
- تعداد documents را کاهش دهید
- از مدل کوچکتر استفاده کنید
- `max_tokens` را کم کنید

---

## 📝 تاریخچه تغییرات

برای مشاهده تاریخچه کامل تغییرات و bug fixes:
- [BUG_FIXES_REPORT.md](./BUG_FIXES_REPORT.md)
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

---

## 🤝 مشارکت

1. Fork کنید
2. Feature branch ایجاد کنید
3. تغییرات را commit کنید
4. Push کنید
5. Pull Request ایجاد کنید

---

## 📄 لایسنس

MIT License

---

## 👨‍💻 توسعه‌دهنده

**Amin Haghi**  
GitHub: [@aminhaghii](https://github.com/aminhaghii)

---

**نسخه:** 1.0.0  
**آخرین به‌روزرسانی:** 5 فوریه 2026
