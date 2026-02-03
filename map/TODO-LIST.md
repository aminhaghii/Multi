بفرمایید، این متن کامل استخراج‌شده از فایل PDF دوم (TODO LIST) است که به صورت ساختاریافته مرتب شده است:

TODO LIST جامع پیاده‌سازی سیستم دستیار پژوهشی Agentic RAG
فاز صفر – پایه‌گذاری پروژه
0.1 تصمیمات معماری

انتخاب Backend اصلی (Python)

انتخاب Framework API (FastAPI)

انتخاب فریمورک UI

انتخاب مدل(های) مورد استفاده

تعریف الگوی ارتباط Agentها:

Orchestrator مرکزی

API async بین Agentها

تعیین اینکه سیستم لوکال/آفلاین است (عدم وابستگی به سرویس ابری)

تعیین ساختار پوشه پروژه (agents / orchestration / retrieval / kb / ui / logs)

0.2 زیرساخت عمومی

پیاده‌سازی Logger مرکزی

سیستم ثبت Error و Trace هر Agent

تعریف ساختار Step / Event برای نمایش گام‌های Agent

تعریف استاندارد خروجی هر Agent (input/output schema)

فاز اول – هسته سیستم (File + Image + Audio)
1. Orchestrator و چرخه کنترل
1.1 Planning Layer (Plan / Execute / Reflect)

پیاده‌سازی شکستن سؤال به Subtask

تعیین ترتیب اجرای Agentها

ساخت Execution Graph

پیاده‌سازی چرخه:

Draft → Review → Refine

امکان توقف، ادامه یا اجرای مجدد از یک گام

الزام: هیچ Agentی مستقیم به مدل وصل نشود؛ همه چیز از Orchestrator عبور کند.

1.2 نمایش گام‌های Agentها

ثبت زمان شروع و پایان هر Agent

ثبت توضیح کوتاه هر Step

آماده‌سازی داده برای نمایش گراف مراحل

2. Workspace پژوهشی
2.1 Research Workspace

ایجاد Workspace برای هر پروژه

مقایسه پاسخ KB با پاسخ وب (در صورت فعال شدن وب در آینده)

ذخیره:

Topic

Subtasks

منابع

خروجی‌های میانی

امکان Resume پروژه

اتصال Workspace به KB اختصاصی

3. لایه دانش (Knowledge Layer) – فاز ۱
3.1 File Ingestion

PDF

Word

Code

Excel

...

3.2 Image Ingestion
3.3 Audio Ingestion
3.4 File Tracking System

به عنوان مثال: تشخیص آخرین فایل آپلودشده

داشتن حافظه

3.5 Vector Store

تولید Embedding

ذخیره Chunkها

similarity search

top-k retrieval

ثبت score هر Chunk

و ...

4. Agentها (Phase 1)
4.1 Query Understanding Agent

تشخیص نیت کاربر

استخراج مفاهیم کلیدی

تشخیص نوع سؤال:

Research

Analytical

Descriptive

تولید Query Plan

4.2 Retrieval Agent (Agentic RAG)
4.3 Reasoning Agent

ترکیب داده‌های بازیابی‌شد

Chain-of-Thought داخلی

استنتاج چندمرحله‌ای

تولید Draft اولیه مبتنی بر شواهد

4.4 Verification Agent

Fact Checking بین منبعی:

Text ↔ Image ↔ Audio

Cross Verification

محاسبه Confidence Score

علامت‌گذاری ادعاهای مشکوک

4.5 Response Generation Agent

تولید پاسخ نهایی روان

ساختاردهی پاسخ (Section-based)

ارجاع‌دهی به منابع

تنظیم لحن پاسخ

5. شفافیت و RAG Scoring
5.1 RAG Grader

محاسبه score هر Chunk

انتخاب Context نهایی

نمایش دلیل انتخاب (Transparency)

5.2 خروجی قابل حسابرسی

نمایش:

منابع

score

اینکه پاسخ از KB بوده یا دانش مدل

6. خروجی‌ها (Phase 1)

پاسخ متنی مستند

پاسخ مبتنی بر تصویر

پاسخ مبتنی بر صوت

Export - قابل دانلود:

PDF

Word

Excel

نام‌گذاری فایل با تاریخ

7. بهینه‌سازی‌های فاز ۱
7.1 Performance

Caching پاسخ‌ها

Parallel Query Processing

حذف مسیرهای اشتباه RAG

7.2 Quality & Safety

نشانگر کیفیت پاسخ (۳ سطح)

دکمه بررسی مجدد

فاز دوم – افزودن ویدیو
8. Video Ingestion
8.1 پردازش ویدیو
8.2 Video Chunking
8.3 Video Retrieval

اضافه شدن Video به Multi-Source Retriever

Cross-modal Retrieval:

Video ↔ Text ↔ Image

8.4 Verification ویدیو

تطبیق ادعاها با ویدیو

ارجاع به Timestamp مشخص

9. تکمیل قابلیت‌های پیشرفته
9.1 UI/UX Agent Flow

نمایش گراف Agentها

امکان کلیک روی هر Step

امکان اجرای مجدد از این مرحله