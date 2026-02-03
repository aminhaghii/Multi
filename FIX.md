🔍 گزارش تحلیل کامل پروژه Multi (Agentic Research Assistant)
📊 ساختار کلی پروژه
پروژه شما یک RAG-based Multi-Agent Research Assistant است که از معماری این‌طوری استفاده می‌کند:

LLM: Llama-3-8B-Instruct (via llama.cpp server, port 8080)

Vector DB: FAISS + Sentence Transformers (all-MiniLM-L6-v2)

Backend: FastAPI (port 8000)

Agents: Query Understanding → Hybrid Retrieval → Reasoning → Verification

Features: PDF ingestion، image extraction، multilingual (FA→EN)، caching، export

🐛 باگ‌های شناسایی شده (Critical)
1. Cache Layer غیرفعال است ⚠️
مکان: main_engine.py خطوط 178-187، 376-379

مشکل: کد caching کامل کامنت شده:

python
# cached_response = self.cache.get(user_query)
# if cached_response:
#     ...
# self.cache.set(user_query, response)
تأثیر: هر query دوباره از صفر پردازش می‌شود. response time 30-40s برای queries تکراری.

راهکار:

python
# Uncomment cache logic در خط 178 و 376
# اما اول باید bug های cache.py رو fix کنی
2. Conflict در Vector Store ⚠️
مکان: vector_store.py vs مستندات

مشکل:

کد از FAISS استفاده می‌کنه

مستندات می‌گه ChromaDB

تأثیر: FAISS ساده‌تره اما ChromaDB features بیشتری داره (metadata filtering، updates، etc.)

راهکار: اگه می‌خوای stay با FAISS، مستندات رو update کن. اگه می‌خوای ChromaDB، باید migration کنی.

3. requirements.txt ناقص است 🚨
مکان: requirements.txt

مشکل: dependencies حیاتی missing هستند:

text
❌ fastapi
❌ uvicorn
❌ pymupdf (fitz import در ingestion.py)
❌ googletrans یا deep-translator
❌ httpx (برای async health check)
❌ pdfplumber (برای table extraction - در FIX.md ذکر شده)
❌ python-multipart (برای file upload)
راهکار:

bash
pip install fastapi uvicorn pymupdf googletrans==4.0.0rc1 httpx pdfplumber python-multipart
بعدش update کن:

text
echo "fastapi==0.109.0" >> requirements.txt
echo "uvicorn==0.27.0" >> requirements.txt
echo "pymupdf==1.23.8" >> requirements.txt
echo "googletrans==4.0.0rc1" >> requirements.txt
echo "httpx==0.26.0" >> requirements.txt
echo "pdfplumber==0.10.3" >> requirements.txt
echo "python-multipart==0.0.6" >> requirements.txt
4. Translation Fallback ضعیف ⚠️
مکان: main_engine.py خطوط 102-132

مشکل: اگه googletrans fail بشه، query اصلی return می‌شه بدون translation:

python
except Exception as e:
    print(f"Translation API error: {e}")
return query, original_lang  # ← اگه فارسی بود، untranslated می‌مونه
تأثیر: queries فارسی fail می‌شن چون LLM انگلیسی‌ست.

راهکار:

python
# Add fallback به deep-translator یا hardcoded dictionary برای technical terms
from deep_translator import GoogleTranslator

if TRANSLATION_AVAILABLE and TRANSLATOR:
    try:
        result = TRANSLATOR.translate(query, dest='en')
        ...
    except:
        # Fallback 2: deep-translator
        try:
            result = GoogleTranslator(source='fa', target='en').translate(query)
            return result, original_lang
        except:
            # Fallback 3: Manual mapping of common terms
            return self._manual_translate(query), original_lang
5. LLM Client بدون Timeout/Retry 🚨
مکان: llm_client.py خطوط 90-110

مشکل: requests.post timeout=60 داره اما:

اگه LLM hang بشه، 60s wait می‌کنه

اگه connection error بشه، retry نمی‌کنه

اگه response خالی بیاد، validate نمی‌کنه

تأثیر: 25% reasoning failures (طبق FIX.md)

راهکار (طبق FIX.md):

python
def generate(self, prompt: str, max_tokens=400, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{self.base_url}/completion",
                json={...},
                timeout=30  # کاهش از 60 به 30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("content", "").strip()
                
                # Validate response
                if not text or len(text) < 20:
                    raise ValueError("Empty or too short response")
                
                return {"success": True, "text": text}
            
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return {"success": False, "error": f"Max retries exceeded: {e}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
6. ReasoningAgent Fallback ناقص ⚠️
مکان: agents/specific_agents.py خطوط 174-280

مشکل: fallback mechanism هست اما:

_simplified_reasoning context رو truncate می‌کنه به 2000 chars اما token count check نمی‌کنه

_direct_extraction sentence matching ساده‌س، technical queries رو handle نمی‌کنه

Log file در logs/reasoning_failures.log save می‌شه اما این directory ممکن است exist نکنه

راهکار:

python
# Add در __init__:
os.makedirs('logs', exist_ok=True)

# Add token estimation:
def _estimate_tokens(self, text: str) -> int:
    return int(len(text.split()) * 1.3)  # Rough estimation

def _simplified_reasoning(self, query: str, context_text: str):
    max_tokens = 2048 - 200 - 100 - 500  # system + query + response
    while self._estimate_tokens(context_text) > max_tokens:
        context_text = context_text[:int(len(context_text) * 0.8)]
    
    # Rest of code...
7. Image Captioner Import Error Silent Fail ⚠️
مکان: api_server.py خطوط 82-87

مشکل: اگه BLIP model load نشه، image captioning disable می‌شه اما:

User متوجه نمی‌شه

Images بدون caption index می‌شن → retrieval ضعیف

راهکار:

python
# Add health status endpoint
@app.get("/api/health/detailed")
async def detailed_health():
    return {
        "llm_status": llm_client.health_check(),
        "multimodal_status": llm_client.multimodal_health_check(),
        "image_captioner": image_captioner is not None,  # ← Add this
        "vector_db_count": vector_store.get_collection_count()
    }
و در frontend نشون بده که image captioning off است.

8. Session Endpoints Without SESSION_SUPPORT ⚠️
مکان: api_server.py خطوط 399-446

مشکل: session endpoints همیشه exist هستند اما:

python
if not SESSION_SUPPORT:
    return {"id": f"temp_{id(title)}", ...}  # Temp fallback
تأثیر: Frontend فکر می‌کنه session کار می‌کنه اما data persist نمی‌شه.

راهکار: یا session support رو fully implement کن یا endpoints رو conditional register کن:

python
if SESSION_SUPPORT:
    @app.post("/api/sessions")
    async def create_session(...):
        ...
9. HybridRetrievalAgent Crash با Empty DB 🚨
مکان: agents/hybrid_retrieval.py خطوط 176-179

مشکل:

python
all_docs = getattr(self.vs, 'documents', [])
all_metas = getattr(self.vs, 'metadatas', [])
اگه vector store empty باشه و documents attribute نداشته باشه، getattr empty list return می‌کنه. اما اگه vector_store.search() call بشه قبلش و exception بده، handle نمی‌شه.

راهکار:

python
def _keyword_search(self, query: str, k: int) -> List[SearchResult]:
    results = []
    
    try:
        all_docs = getattr(self.vs, 'documents', [])
        all_metas = getattr(self.vs, 'metadatas', [])
        
        if not all_docs:
            logger.warning("Vector store is empty")
            return results
        
        # Rest of code...
    
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return results
📉 نقاط ضعف کیفیت (Quality Issues)
1. Chunk Size کوچک ⚠️
مکان: ingestion.py خط 25، api_server.py خط 84

python
processor = DocumentProcessor(vector_store, chunk_size=500, chunk_overlap=50)
مشکل:

500 words برای technical documents کمه

Context window 2048 tokens → می‌تونیم chunks بزرگ‌تر داشته باشیم

Overlap 50 خیلی کمه (10%)

پیشنهاد:

python
chunk_size=800  # 20% افزایش
chunk_overlap=160  # 20% overlap
2. Top-K کم در Retrieval ⚠️
مکان: main_engine.py خط 250، agents/specific_agents.py خط 117

python
k = context.get("top_k", 10)  # Default 10
مشکل: برای queries پیچیده که نیاز به context زیاد دارن، 10 chunks کمه.

پیشنهاد:

python
# Dynamic top-k based on query complexity
query_words = len(query.split())
k = 15 if query_words > 10 else 10
3. Verification Agent ضعیف ⚠️
مکان: agents/specific_agents.py خطوط 641-707

مشکل: verification فقط از LLM استفاده می‌کنه، هیچ heuristic یا fact-checking ندارد:

python
# Just asks LLM "is this correct?"
confidence = float(conf_str)  # Could be anything
پیشنهاد: Add heuristics:

python
def _calculate_confidence(self, answer, context, llm_confidence):
    # Heuristic 1: Answer length
    if len(answer) < 50:
        llm_confidence *= 0.8
    
    # Heuristic 2: Source overlap
    answer_words = set(answer.lower().split())
    context_words = set(' '.join(context).lower().split())
    overlap = len(answer_words & context_words) / len(answer_words)
    overlap_score = min(overlap, 1.0)
    
    # Heuristic 3: Citation presence
    has_citations = "source:" in answer.lower() or "page" in answer.lower()
    citation_bonus = 1.1 if has_citations else 1.0
    
    # Combine
    final_confidence = llm_confidence * overlap_score * citation_bonus
    return min(final_confidence, 1.0)
4. No Reranking ⚠️
مکان: agents/hybrid_retrieval.py خطوط 232-282

مشکل: بعد از merge، فقط sort by weighted score می‌شه. هیچ cross-encoder reranking نیست.

پیشنهاد: Add reranking stage:

python
from sentence_transformers import CrossEncoder

class HybridRetrievalAgent:
    def __init__(self, vector_store, config=None):
        self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    
    def _rerank(self, query: str, results: List[SearchResult], top_k: int):
        # Score each result
        pairs = [(query, r.document) for r in results]
        scores = self.reranker.predict(pairs)
        
        # Combine with original scores
        for result, score in zip(results, scores):
            result.score = (result.score + score) / 2
        
        # Re-sort
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
نکته: این یک dependency جدید می‌خواهد:

bash
pip install sentence-transformers
5. Image Retrieval فقط Caption-Based ⚠️
مکان: ingestion.py خطوط 265-297

مشکل: images فقط based on text caption search می‌شن. اگه caption ضعیف باشه، image پیدا نمی‌شه.

پیشنهاد: Add visual similarity search با CLIP:

python
from sentence_transformers import util
import torch
from PIL import Image

class VisualSearchEngine:
    def __init__(self):
        from transformers import CLIPProcessor, CLIPModel
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.image_embeddings = {}
    
    def index_image(self, image_path: str):
        image = Image.open(image_path)
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.no_grad():
            embedding = self.model.get_image_features(**inputs)
        self.image_embeddings[image_path] = embedding
    
    def search_by_text(self, query: str, top_k=5):
        inputs = self.processor(text=[query], return_tensors="pt")
        with torch.no_grad():
            text_embedding = self.model.get_text_features(**inputs)
        
        scores = {}
        for path, img_emb in self.image_embeddings.items():
            similarity = util.cos_sim(text_embedding, img_emb).item()
            scores[path] = similarity
        
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
6. No Query Expansion ⚠️
مکان: main_engine.py - orchestrator flow

مشکل: اگه query ambiguous باشه یا synonyms داشته باشه، retrieval weak می‌شه.

پیشنهاد: Add query expansion:

python
def _expand_query(self, query: str) -> List[str]:
    """Generate alternative query formulations."""
    expansions = [query]
    
    # Add synonyms
    synonyms = {
        'worst case': ['pessimistic scenario', 'maximum deviation'],
        'sensitivity': ['parametric variation', 'robustness'],
        # Add more domain-specific synonyms
    }
    
    query_lower = query.lower()
    for term, alternatives in synonyms.items():
        if term in query_lower:
            for alt in alternatives:
                expansions.append(query_lower.replace(term, alt))
    
    # Add question reformulation
    if query.startswith('what is'):
        expansions.append(query.replace('what is', 'define'))
    
    return expansions[:3]  # Max 3 variants

# Use in retrieval:
expanded_queries = self._expand_query(user_query)
all_results = []
for q in expanded_queries:
    results = self.retrieval_agent.execute({"user_query": q, "top_k": 5})
    all_results.extend(results['documents'])

# Deduplicate and merge
...
7. Citation System ساده ⚠️
مکان: agents/specific_agents.py خطوط 554-569

مشکل: citations فقط در footer append می‌شن:

python
answer += "\n\n**Sources:**\n" + "\n".join(citation_list)
بهتر بود inline citations داشته باشیم مثل: "AOCS stands for Attitude and Orbit Control System."
​

پیشنهاد:

python
def _add_inline_citations(self, answer: str, metadatas: List[Dict]) -> str:
    """Add inline citations to answer."""
    # Build citation map
    citations = {}
    for i, meta in enumerate(metadatas[:5], 1):
        filename = meta.get('filename', 'unknown')
        page = meta.get('page', 0) + 1
        citations[i] = f"{filename} (Page {page})"
    
    # Find sentences that need citation
    sentences = answer.split('. ')
    cited_answer = []
    
    for sentence in sentences:
        # Heuristic: if sentence has technical info, add citation
        if any(keyword in sentence.lower() for keyword in ['is defined', 'consists of', 'includes', 'section']):
            # Find most relevant source
            best_cite = 1  # Simple: use first source
            cited_answer.append(f"{sentence} [{best_cite}]")
        else:
            cited_answer.append(sentence)
    
    result = '. '.join(cited_answer)
    
    # Add footer
    result += "\n\n**References:**\n"
    for i, cite in citations.items():
        result += f"[{i}] {cite}\n"
    
    return result
⚡ بهبودهای پرفورمنس
1. Parallel Agent Execution 🚀
مکان: main_engine.py - sequential execution

مشکل: همه agents به صورت serial run می‌شن → response time 30-40s

پیشنهاد (طبق FIX.md):

python
import asyncio

async def run_query_async(self, user_query: str):
    loop = asyncio.get_event_loop()
    
    # Stage 1: Query understanding (fast)
    query_result = await loop.run_in_executor(None, self.query_agent.execute, ...)
    
    # Stage 2: Retrieval (parallel with other prep)
    retrieval_task = loop.run_in_executor(None, self.retrieval_agent.execute, ...)
    # Do other work here...
    retrieval_result = await retrieval_task
    
    # Stage 3: Reasoning
    reasoning_task = loop.run_in_executor(None, self.reasoning_agent.execute, ...)
    answer_result = await reasoning_task
    
    # Stage 4: Verification + Artifact (parallel)
    verify_task = loop.run_in_executor(None, self.verification_agent.execute, ...)
    artifact_task = loop.run_in_executor(None, self._detect_artifact_need, ...)
    
    verify, artifact = await asyncio.gather(verify_task, artifact_task)
    
    return {...}
Expected speedup: 30-40% reduction (30s → 20s)

2. Enable Caching 🚀
مکان: main_engine.py uncomment خطوط 178-187، 376-379

مشکل: cache layer وجود داره اما disabled است.

راهکار: Uncomment + fix bugs:

python
# In run_query():
cached_response = self.cache.get(user_query)
if cached_response:
    print(f"✅ CACHE HIT: Returning cached response")
    cached_response['from_cache'] = True
    return cached_response

# ... normal processing ...

# Cache successful responses
if response['success'] and response['confidence'] >= 0.7:
    self.cache.set(user_query, response)
    print(f"💾 CACHE: Response cached")
Expected speedup: Cached queries < 1s (vs 30s)

3. Streaming Response 🚀
مکان: api_server.py - add new endpoint

پیشنهاد (طبق FIX.md):

python
from fastapi.responses import StreamingResponse
import json

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        # Send status updates as query processes
        yield json.dumps({"type": "status", "stage": "understanding"}) + "\n"
        
        # ... process query ...
        
        yield json.dumps({"type": "status", "stage": "retrieval", "chunks": 10}) + "\n"
        
        # ... reasoning ...
        
        yield json.dumps({"type": "status", "stage": "reasoning"}) + "\n"
        
        # Stream answer word by word
        words = answer.split()
        for i in range(0, len(words), 5):
            chunk = ' '.join(words[i:i+5])
            yield json.dumps({"type": "content", "data": chunk}) + "\n"
            await asyncio.sleep(0.05)
        
        yield json.dumps({"type": "complete", "metadata": {...}}) + "\n"
    
    return StreamingResponse(generate(), media_type="application/x-ndjson")
Frontend باید EventSource یا fetch with streaming handle کنه.

Expected improvement: Perceived latency کاهش (user content رو زودتر می‌بینه)

🎯 بهبودهای کیفیت پاسخ
1. Add Context Window Management 📊
python
def _manage_context_window(self, chunks: List[str], max_tokens=1500):
    """Intelligently select chunks within token budget."""
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    
    selected = []
    total_tokens = 0
    
    for chunk in chunks:
        tokens = len(tokenizer.encode(chunk))
        if total_tokens + tokens > max_tokens:
            break
        selected.append(chunk)
        total_tokens += tokens
    
    return selected, total_tokens
2. Add Confidence Calibration 📊
python
def _calibrate_confidence(self, raw_confidence: float, metadata: Dict) -> float:
    """Adjust confidence based on metadata."""
    calibrated = raw_confidence
    
    # Reduce confidence if:
    # - Low retrieval scores
    if metadata.get('best_distance', 0) > 0.8:
        calibrated *= 0.9
    
    # - Few sources
    if metadata.get('num_sources', 0) < 3:
        calibrated *= 0.95
    
    # - Short answer
    if len(metadata.get('answer', '')) < 100:
        calibrated *= 0.9
    
    # Increase confidence if:
    # - Multiple agents agree
    if metadata.get('verification_passed', False):
        calibrated *= 1.05
    
    return min(calibrated, 1.0)
3. Add Answer Post-Processing 📊
python
def _postprocess_answer(self, answer: str) -> str:
    """Clean and enhance answer."""
    # Remove repetition
    sentences = answer.split('. ')
    seen = set()
    unique = []
    for s in sentences:
        if s.strip() and s.strip() not in seen:
            seen.add(s.strip())
            unique.append(s)
    answer = '. '.join(unique)
    
    # Fix formatting
    answer = re.sub(r'\n{3,}', '\n\n', answer)  # Max 2 newlines
    answer = re.sub(r' +', ' ', answer)  # Remove extra spaces
    
    # Add structure
    if len(answer) > 500 and '##' not in answer:
        # Add section headers if missing
        paragraphs = answer.split('\n\n')
        if len(paragraphs) > 2:
            structured = f"## Overview\n\n{paragraphs[0]}\n\n## Details\n\n"
            structured += '\n\n'.join(paragraphs[1:])
            answer = structured
    
    return answer
🏗️ پیشنهادات معماری
1. Add Health Monitoring Dashboard
python
# utils/health_monitor.py
class HealthMonitor:
    def get_system_metrics(self):
        return {
            "llm_latency_ms": self.measure_llm_latency(),
            "vector_db_size": self.vs.get_collection_count(),
            "cache_hit_rate": self.cache.get_stats()['reuse_rate'],
            "avg_response_time": self.avg_response_time,
            "error_rate_24h": self.error_rate
        }
در frontend نشون بده:

xml
<div class="health-dashboard">
  LLM: 🟢 125ms | DB: 1,234 docs | Cache: 45% hit rate
</div>
2. Add Evaluation Suite
python
# tests/eval_suite.py
test_queries = [
    {"query": "What is AOCS?", "expected_keywords": ["attitude", "orbit", "control"]},
    {"query": "فاز آرامش چیست؟", "expected_keywords": ["tranquilization", "phase"]},
    {"query": "Show me figures about AOCS", "expected_type": "image_retrieval"},
    # Add 20-30 test queries
]

def run_evaluation():
    results = []
    for test in test_queries:
        response = orchestrator.run_query(test['query'])
        
        # Check if expected keywords present
        score = sum(1 for kw in test['expected_keywords'] 
                   if kw.lower() in response['answer'].lower())
        
        results.append({
            "query": test['query'],
            "score": score / len(test['expected_keywords']),
            "confidence": response['confidence'],
            "time_seconds": response['execution_time']
        })
    
    # Report
    avg_score = sum(r['score'] for r in results) / len(results)
    print(f"Evaluation Score: {avg_score:.2%}")
    return results
3. Add Logging & Observability
python
# utils/logger.py
import logging
from datetime import datetime

class StructuredLogger:
    def __init__(self):
        logging.basicConfig(
            filename=f'logs/app_{datetime.now().strftime("%Y%m%d")}.log',
            level=logging.INFO,
            format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        self.logger = logging.getLogger("RAG_System")
    
    def log_query(self, query, result):
        self.logger.info(json.dumps({
            "event": "query_processed",
            "query": query[:100],
            "success": result['success'],
            "confidence": result.get('confidence'),
            "latency_ms": result.get('latency_ms'),
            "sources_used": result.get('num_sources'),
            "from_cache": result.get('from_cache', False)
        }))
📝 خلاصه اقدامات پیشنهادی
🔴 Priority 1 (Critical - امروز):
Fix requirements.txt → Add missing deps

Uncomment caching → Enable cache layer

Fix LLM timeout → Add retry + validation

Fix translation fallback → Add deep-translator

🟠 Priority 2 (High - این هفته):
Increase chunk size → 500→800 + overlap 50→160

Add reranking → CrossEncoder after retrieval

Improve verification → Add heuristics

Add health monitoring → Dashboard endpoint

🟡 Priority 3 (Medium - هفته بعد):
Add query expansion → Synonyms + reformulation

Implement streaming → Better UX

Add inline citations → در متن پاسخ
​

Parallel execution → Async orchestrator

🟢 Priority 4 (Nice to have):
CLIP visual search → Image similarity

Evaluation suite → Automated testing

Structured logging → Observability

Table extraction → pdfplumber (اگه NFPA document داری)

🎯 انتظارات بعد از Fix:
✅ Response time: 30-40s → 15-20s (با caching → <1s)

✅ Success rate: 75% → 85-90%

✅ Confidence accuracy: ±15% → ±10%

✅ Zero crashes با empty DB یا translation failure