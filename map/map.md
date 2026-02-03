بسیار عالی. این یک نقشه راه جامع و گام‌به‌گام (Step-by-Step) است که دقیقاً برای Windsurf (یا دستیارهای کدنویسی مشابه مثل Cursor) طراحی شده است.

از آنجا که Windsurf قابلیت اجرای دستورات ترمینال، ویرایش فایل‌ها و درک کانتکست پروژه را دارد، من این راهنما را به صورت Promptهای پشت سر هم (Sequential Prompts) نوشتم. شما می‌توانید این پرامپت‌ها را یکی‌یکی به Windsurf بدهید تا پروژه را طبق معماری PDF و با مدل MiMo-VL-7B-RL-2508 برایتان بسازد.

پیش‌نیازها (قبل از شروع در Windsurf)

پایتون: مطمئن شوید Python 3.10 یا بالاتر نصب است.

GPU: مطمئن شوید درایورهای CUDA نصب هستند (چون مدل 7B نیاز به GPU دارد).

HuggingFace Token: اگر مدل نیاز به دسترسی دارد، توکن خود را آماده داشته باشید.

فاز ۱: راه‌اندازی زیرساخت و سرور مدل (Model Serving)

هدف: بالا آوردن مدل MiMo به عنوان یک API لوکال که تمام Agentها بتوانند به آن درخواست بفرستند (جایگزین OpenAI API).

پرامپت ۱ برای Windsurf:
(این متن را کپی و در Windsurf پیست کنید)

code
Markdown
download
content_copy
expand_less
I want to start a new project called "AgenticResearchAssistant" based on a local LLM architecture.
The core model will be "XiaomiMiMo/MiMo-VL-7B-RL-2508" from Hugging Face.

Step 1: Project Setup & Dependencies
1. Create a `requirements.txt` file with:
   - torch, torchvision, torchaudio (CUDA version)
   - transformers, accelerate, bitsandbytes (for quantization)
   - fastapi, uvicorn (for the API server)
   - python-multipart, pydantic
   - sentence-transformers (for embeddings)
   - chromadb (vector database)
   - pypdf, pillow (for pdf and image processing)
2. Create a virtual environment (`venv`) and install these requirements.

Step 2: Model Inference Server
Create a file `model_server.py` to serve "XiaomiMiMo/MiMo-VL-7B-RL-2508".
- Use FastAPI.
- Load the model using `transformers` (AutoModelForCausalLM, AutoProcessor). Use 4-bit quantization (load_in_4bit=True) to save memory if needed.
- Create an endpoint `/generate` that accepts:
  - `prompt` (string)
  - `images` (optional list of base64 strings, since it's a VL model)
  - `max_tokens`, `temperature`.
- The endpoint should return the generated text.
- Ensure the prompt structure follows the chat template suitable for this model.

Please write the code for `requirements.txt` and `model_server.py`.
فاز ۲: ساخت لایه دانش (RAG & Ingestion)

هدف: تبدیل PDFها به متن و تصویر (چون مدل Multimodal است) و ذخیره در ChromaDB.

پرامپت ۲ برای Windsurf:

code
Markdown
download
content_copy
expand_less
Great. Now let's implement the "Knowledge Layer" (Layer 5 in architecture).

Step 1: Document Processing (`ingestion.py`)
Create a script that processes PDF files from a `./data` directory.
Since our model (MiMo-VL) is multimodal, we need a hybrid approach:
1. Extract text chunks from the PDF.
2. Extract images/charts from the PDF pages.
3. Save text chunks and image paths metadata into a Vector Database.

Step 2: Vector Store (`vector_store.py`)
- Initialize a persistent ChromaDB client in `./chroma_db`.
- Use `sentence-transformers/all-MiniLM-L6-v2` for embedding the text chunks.
- Create a function `add_document(file_path)` that orchestrates the ingestion.
- Create a function `search(query, k=5)` that returns the most relevant text chunks and their associated image paths.

Write the code for `ingestion.py` and `vector_store.py`.
فاز ۳: معماری Agentها و Orchestrator

هدف: پیاده‌سازی کلاس‌های پایه و مغز متفکر سیستم که در PDF به عنوان لایه ۳ و ۴ تعریف شده است.

پرامپت ۳ برای Windsurf:

code
Markdown
download
content_copy
expand_less
Now we build the core logic. Based on the architecture:
"Orchestrator -> Planning -> Execution -> Reflection"

Step 1: LLM Client (`llm_client.py`)
Create a wrapper class that sends requests to our running `model_server.py` (localhost:8000/generate). It should handle creating the payload (text + base64 images).

Step 2: Define Agent Interface
Create `agents/base_agent.py`. Every agent must have:
- `name`: str
- `description`: str
- `execute(context: dict) -> dict`: The main method.

Step 3: Implement The Agents (File: `agents/specific_agents.py`)
Implement these classes using the `llm_client`:
1. **QueryUnderstandingAgent**: Analyzes the user input, extracts keywords, and determines if it's Research/Analytical.
2. **RetrievalAgent**: Uses `vector_store.py` to fetch data. It should format the retrieved text AND images for the LLM.
3. **ReasoningAgent**: The brain. It takes the retrieved context (text + images) and the user query to generate an answer. It should use Chain-of-Thought prompting.
4. **VerificationAgent**: A separate call to the LLM to verify if the generated answer is supported by the retrieved context chunks. Output a confidence score.

Write the code for `llm_client.py`, `agents/base_agent.py`, and `agents/specific_agents.py`.
فاز ۴: پیاده‌سازی Orchestrator (چرخه اصلی)

هدف: اتصال همه اجزا به هم طبق فلوچارت صفحه ۱ PDF.

پرامپت ۴ برای Windsurf:

code
Markdown
download
content_copy
expand_less
Now, implement the **Orchestrator** (Layer 3) in a file named `main_engine.py`.

The Orchestrator should follow this flow:
1. Receive `user_query`.
2. Call **QueryUnderstandingAgent** to parse the intent.
3. Call **RetrievalAgent** to get context (docs + images).
4. **Planning Loop**:
   - Call **ReasoningAgent** to generate a draft answer.
   - Call **VerificationAgent** to check the draft.
   - If confidence is low (< 0.7), trigger a "Refinement" loop (maybe search again or ask ReasoningAgent to fix hallucination).
5. **ResponseGeneration**: Format the final output cleanly.

Create a `run_query(query: str)` function in `main_engine.py` that ties all these agents together and prints the progress logs.
فاز ۵: رابط کاربری (اختیاری ولی توصیه شده)

هدف: یک UI ساده برای تست سیستم.

پرامپت ۵ برای Windsurf:

code
Markdown
download
content_copy
expand_less
Finally, create a simple UI to test the system.
Create `app.py` using Streamlit.
- It should have a file uploader to upload PDFs (calls `ingestion.py`).
- A chat interface to ask questions.
- When the user asks a question, run `main_engine.run_query` and display:
  1. The thinking process (Agent logs).
  2. The retrieved images (if any).
  3. The final answer.

Ensure the `model_server.py` is expected to be running in a separate terminal.
نکات کلیدی برای شما (به عنوان توسعه‌دهنده):

نحوه اجرا:

ابتدا باید سرور مدل را اجرا کنید: python model_server.py (این ترمینال باید همیشه باز بماند).

سپس UI را اجرا کنید: streamlit run app.py.

نکته درباره MiMo-VL:

این مدل تصویری است. در کد ReasoningAgent، بسیار مهم است که اگر RetrievalAgent تصویری (مثلاً نمودار از PDF) پیدا کرد، آن تصویر را به فرمت Base64 تبدیل کرده و همراه با پرامپت متنی به سرور بفرستید. در پرامپت ۲ و ۳ این موضوع لحاظ شده است.

مدیریت حافظه (VRAM):

اگر کارت گرافیک ۲۴ گیگ (مثل 3090/4090) دارید، مدل را کامل لود کنید.

اگر کمتر دارید (مثلاً ۱۲ یا ۱۶ گیگ)، در پرامپت ۱ حتماً روی load_in_4bit=True تاکید کنید (که نوشته‌ام).

این دستورالعمل را به ترتیب به Windsurf بدهید تا کدهای تمیز و ماژولار تحویل بگیرید. موفق باشید!