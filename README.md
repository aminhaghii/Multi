# Agentic Research Assistant

یک دستیار پژوهشی عامل‌محور (Agentic) مبتنی بر RAG که از مدل محلی MiMo-VL-7B استفاده می‌کند.

## ویژگی‌ها

- معماری چندعاملی (Plan → Execute → Reflect)
- RAG با FAISS و Sentence Transformers
- پردازش و استخراج خودکار PDF
- اعتبارسنجی و محاسبه Confidence Score
- رابط کاربری Streamlit

## ساختار پروژه

```
Multi_agent/
├── agents/                 # Agentهای تخصصی
│   ├── __init__.py
│   ├── base_agent.py
│   └── specific_agents.py
├── data/                   # فایل‌های PDF ورودی
├── faiss_db/              # پایگاه داده برداری
├── extracted_images/      # تصاویر استخراج‌شده از PDF
├── models/                # فایل‌های مدل
│   └── mimo-vl/
├── tests/                 # فایل‌های تست
├── map/                   # نقشه راه و مستندات
├── app.py                 # رابط کاربری Streamlit
├── main_engine.py         # Orchestrator اصلی
├── llm_client.py          # کلاینت ارتباط با مدل
├── vector_store.py        # مدیریت FAISS
├── ingestion.py           # پردازش PDF
└── requirements.txt       # وابستگی‌ها
```

## نصب و راه‌اندازی

### 1. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 2. راه‌اندازی سرور مدل

```powershell
& "c:\Users\aminh\OneDrive\Desktop\Multi_agent\models\mimo-vl\llama\llama-server.exe" `
  --model "c:/Users/aminh/OneDrive/Desktop/Multi_agent/models/mimo-vl/MiMo-VL-7B-RL-2508.Q4_K_M.gguf" `
  -ngl 12 `
  -c 4096 `
  --host 127.0.0.1 `
  --port 8080
```

**نکته:** این ترمینال باید همیشه باز بماند.

### 3. اجرای رابط کاربری

در ترمینال جدید:

```bash
streamlit run app.py
```

## استفاده

1. **آپلود PDF**: از نوار کناری فایل PDF خود را آپلود و پردازش کنید
2. **پرسش**: سوال خود را در چت وارد کنید
3. **نتیجه**: پاسخ با Confidence Score و منابع نمایش داده می‌شود

## تنظیمات

### تنظیم VRAM و Context

در فایل دستور سرور:
- `ngl`: تعداد لایه‌های GPU (کمتر = کمتر VRAM)
- `-c`: اندازه Context (کمتر = سریع‌تر)

### تنظیم RAG

در `ingestion.py`:
- `chunk_size`: اندازه چانک‌ها (پیش‌فرض: 500)
- `chunk_overlap`: همپوشانی (پیش‌فرض: 50)

در `main_engine.py`:
- `max_refinement_iterations`: تعداد تلاش برای بهبود (پیش‌فرض: 2)
- `confidence_threshold`: حد آستانه اعتماد (پیش‌فرض: 0.7)

## تست

### تست لایه دانش
```bash
python tests/test_ingestion.py
```

### تست Agentها
```bash
python tests/test_agents.py
```

### تست سیستم کامل
```bash
python tests/test_full_system.py
```

## معماری

سیستم شامل 4 Agent اصلی است:

1. **QueryUnderstandingAgent**: تحلیل پرسش و استخراج Intent
2. **RetrievalAgent**: بازیابی از Knowledge Base
3. **ReasoningAgent**: تولید پاسخ با Chain-of-Thought
4. **VerificationAgent**: اعتبارسنجی و محاسبه Confidence

**Orchestrator** این Agentها را در چرخه Plan→Execute→Reflect مدیریت می‌کند.

## نیازمندی‌های سیستم

- Python 3.10+
- GPU با حداقل 6GB VRAM (توصیه: 14GB shared)
- 10GB فضای دیسک
- CUDA 13.1

## مشکلات رایج

### سرور مدل وصل نمی‌شود
- مطمئن شوید سرور در حال اجراست
- آدرس `http://127.0.0.1:8080` را چک کنید

### VRAM کم
- `ngl` را کاهش دهید (مثلاً 8 یا 10)
- Context size را کم کنید (مثلاً 3072)

### Vector Store خالی است
- ابتدا PDF آپلود و پردازش کنید
- یا `python tests/test_ingestion.py` را اجرا کنید
