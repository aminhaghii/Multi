from agents import QueryUnderstandingAgent, RetrievalAgent, ReasoningAgent, VerificationAgent
from llm_client import LLMClient
from vector_store import VectorStore
from cache import get_cache
from typing import Dict, Any, Optional, Callable
import html
import time
import re
import threading

# Translation support
try:
    from googletrans import Translator
    TRANSLATOR = Translator()
    TRANSLATION_AVAILABLE = True
except Exception as e:
    TRANSLATOR = None
    TRANSLATION_AVAILABLE = False
    print(f"Warning: Translation not available: {e}")

# Enhanced imports for hybrid retrieval
try:
    from agents.hybrid_retrieval import HybridRetrievalAgent
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False
    print("Warning: HybridRetrievalAgent not available, using standard retrieval")

class Orchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        vector_store: VectorStore,
        image_captioner=None,
        max_refinement_iterations: int = 2,
        confidence_threshold: float = 0.7
    ):
        self.llm_client = llm_client
        self.vector_store = vector_store
        self.max_refinement_iterations = max_refinement_iterations
        self.confidence_threshold = confidence_threshold
        self.relevance_threshold = 0.5
        
        self.query_agent = QueryUnderstandingAgent(llm_client)
        
        # Use hybrid retrieval if available
        if HYBRID_AVAILABLE:
            self.retrieval_agent = HybridRetrievalAgent(vector_store)
            print("✅ Using HybridRetrievalAgent for improved retrieval")
        else:
            self.retrieval_agent = RetrievalAgent(vector_store)
            print("⚠️ Using standard RetrievalAgent")
        
        self.reasoning_agent = ReasoningAgent(llm_client, image_captioner)
        self.verification_agent = VerificationAgent(llm_client)
        
        self._log_lock = threading.Lock()
        self.cache = get_cache()
    
    def update_vector_store(self, new_vector_store: VectorStore):
        """Update vector store reference after KB clear/rebuild"""
        self.vector_store = new_vector_store
        if HYBRID_AVAILABLE:
            self.retrieval_agent = HybridRetrievalAgent(new_vector_store)
        else:
            self.retrieval_agent = RetrievalAgent(new_vector_store)
        print("🔄 Orchestrator vector store updated")
    
    def log_step(self, step: str, details: Dict[str, Any]):
        """Legacy log_step - prefer local execution_log in run_query."""
        log_entry = {
            "step": step,
            "timestamp": time.time(),
            "details": details
        }
        with self._log_lock:
            print(f"[Orchestrator] {step}: {list(details.keys())}")
    
    def _is_non_english(self, text: str) -> bool:
        """Detect if text contains non-English characters (Persian, Arabic, etc.)"""
        # Check for Persian/Arabic Unicode ranges
        persian_arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')
        # Check for other non-Latin scripts
        non_latin_pattern = re.compile(r'[^\x00-\x7F]')
        
        if persian_arabic_pattern.search(text):
            return True
        # If more than 30% non-ASCII, likely non-English
        non_ascii_count = len(non_latin_pattern.findall(text))
        if non_ascii_count > len(text) * 0.3:
            return True
        return False
    
    def _translate_query(self, query: str, target_lang: str = 'en') -> tuple:
        """Translate query to English. Returns (translated_query, original_lang)"""
        # Common Persian/Farsi technical term mappings for fallback
        persian_mappings = {
            'فاز آرامش': 'Tranquilization Phase',
            'آرامش': 'Tranquilization',
            'چیست': 'what is',
            'تحلیل حساسیت': 'sensitivity analysis',
            'تحلیل بدترین حالت': 'worst case analysis',
            'کنترل موقعیت': 'attitude control',
            'سیستم کنترل': 'control system',
            'ماهواره': 'satellite',
            'مدار': 'orbit',
        }
        
        # Try direct mapping first (more reliable)
        translated = query
        original_lang = 'fa' if self._is_non_english(query) else 'en'
        
        for persian, english in persian_mappings.items():
            if persian in query:
                translated = translated.replace(persian, english)
        
        # Clean up Persian question marks and structure
        translated = translated.replace('؟', '?')
        
        # If we made substitutions, the query is partially translated
        if translated != query:
            print(f"🌐 TRANSLATION (mapping): '{query}' -> '{translated}'")
            return translated, original_lang
        
        # Try googletrans as fallback
        if TRANSLATION_AVAILABLE and TRANSLATOR:
            try:
                result = TRANSLATOR.translate(query, dest='en')
                if result and result.text:
                    print(f"🌐 TRANSLATION (googletrans): '{query}' -> '{result.text}'")
                    return result.text, original_lang
            except Exception as e:
                print(f"⚠️ Googletrans error: {e}, trying deep-translator...")
        
        # Fallback 2: deep-translator
        try:
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(source='auto', target='en').translate(query)
            if result:
                print(f"🌐 TRANSLATION (deep-translator): '{query}' -> '{result}'")
                return result, original_lang
        except Exception as e:
            print(f"⚠️ Deep-translator error: {e}")
        
        # Last resort: if query is non-English, warn user
        if original_lang != 'en':
            print(f"❌ TRANSLATION FAILED: Unable to translate '{query}'. Query may fail.")
        
        return query, original_lang
    
    def _detect_query_type(self, user_query: str) -> str:
        """Detect if query is casual/general or requires specialized knowledge from RAG"""
        # Treat anything that clearly looks like a question as specialized even if it starts with a greeting
        question_markers = ['?', '؟']
        question_keywords = [
            'چی', 'چه', 'چرا', 'کجا', 'کدام', 'چگونه', 'چطوری', 'می شود', 'میشه', 'تحلیل',
            'explain', 'why', 'how', 'what', 'analysis', 'analyze', 'report'
        ]
        for marker in question_markers:
            if marker in user_query:
                return 'specialized'
        lower_query = user_query.lower()
        if any(keyword in user_query or keyword in lower_query for keyword in question_keywords):
            return 'specialized'

        casual_patterns = [
            'hello', 'hi', 'hey', 'salam', 'how are you', 'what\'s up', 
            'good morning', 'good evening', 'thanks', 'thank you',
            'bye', 'goodbye', 'see you', 'khobi', 'halet chetore', 'mersi',
            'سلام', 'خوبی', 'چطوری', 'ممنون', 'تشکر', 'خداحافظ', 'چه خبر'
        ]
        
        query_lower = user_query.lower().strip()
        words = query_lower.split()
        
        # Only classify as casual if it MATCHES a casual pattern
        for pattern in casual_patterns:
            if query_lower == pattern or query_lower.startswith(pattern + ' ') or query_lower.endswith(' ' + pattern):
                if len(words) <= 5:
                    return 'casual'
        
        # Very short single-word greetings only
        if len(words) == 1 and words[0] in ['hi', 'hello', 'hey', 'salam', 'سلام', 'bye', 'thanks', 'mersi', 'ممنون']:
            return 'casual'
        
        return 'specialized'
    
    def _handle_casual_query(self, user_query: str) -> Dict[str, Any]:
        """Handle casual/general queries - redirect to document-based questions"""
        answer = (
            "I am a specialized research assistant focused on analyzing uploaded documents. "
            "Your question appears to be outside the scope of the knowledge base. "
            "Please upload documents (PDF, images, or audio) and ask questions related to their content. "
            "I can help you with:\n"
            "• Extracting information from documents\n"
            "• Answering questions about uploaded content\n"
            "• Creating reports and summaries\n"
            "• Analyzing data from your files"
        )
        
        return {
            "success": True,
            "query": user_query,
            "answer": answer,
            "confidence": 1.0,
            "verified": True,
            "num_iterations": 0,
            "num_sources": 0,
            "query_type": "casual",
            "image_paths": [],
            "artifact": None,
            "from_cache": False,
            "execution_log": [{
                "step": "casual_query_redirect",
                "timestamp": time.time(),
                "details": {"type": "casual", "redirected_to_kb_focus": True}
            }]
        }
    
    def run_query(
        self,
        user_query: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("ORCHESTRATOR: Starting query processing")
        print("=" * 70 + "\n")
        
        # Use a local execution log to avoid cross-request contamination in concurrent scenarios
        execution_log = []
        original_query = user_query
        original_lang = 'en'
        
        def log_step_local(step: str, details: Dict[str, Any]):
            execution_log.append({
                "step": step,
                "timestamp": time.time(),
                "details": details
            })
        
        def emit(event: Dict[str, Any]):
            if progress_callback:
                progress_callback(event)

        # Detect casual queries BEFORE translation to avoid unnecessary latency
        query_type = self._detect_query_type(user_query)
        print(f"QUERY TYPE: {query_type}")
        print("-" * 70)
        
        if query_type == 'casual':
            emit({"type": "phase_start", "phase": "query_understanding", "message": "Classifying query"})
            emit({"type": "phase_text", "phase": "query_understanding", "text": "Detected casual query. No retrieval needed."})
            emit({"type": "phase_end", "phase": "query_understanding"})
            print("Handling as casual query (no RAG needed)")
            return self._handle_casual_query(user_query)
        
        # Translation layer for non-English queries (after casual check to avoid unnecessary latency)
        if self._is_non_english(user_query):
            print(f" Detected non-English query: {user_query}")
            user_query, original_lang = self._translate_query(user_query)
            log_step_local("translation", {
                "original_query": original_query,
                "translated_query": user_query,
                "original_lang": original_lang
            })
        
        # Try cache for specialized queries
        cached_response = self.cache.get(user_query) if use_cache else None
        if cached_response:
            print(f"💾 CACHE HIT: Returning cached response")
            emit({"type": "phase_start", "phase": "query_understanding", "message": "Cache hit: quick path"})
            emit({"type": "phase_text", "phase": "query_understanding", "text": "Using cached analysis."})
            emit({"type": "phase_end", "phase": "query_understanding"})
            emit({"type": "phase_start", "phase": "retrieval", "message": "Cache hit: reuse retrieval"})
            emit({"type": "phase_text", "phase": "retrieval", "text": "Using cached retrieval results."})
            emit({"type": "phase_end", "phase": "retrieval"})
            emit({"type": "phase_start", "phase": "reasoning", "message": "Cache hit: reuse reasoning"})
            cached_answer = cached_response.get('answer', '')
            for chunk_start in range(0, len(cached_answer), 160):
                emit({
                    "type": "phase_text",
                    "phase": "reasoning",
                    "text": cached_answer[chunk_start:chunk_start + 160],
                    "append": True
                })
                time.sleep(0.01)
            emit({"type": "phase_end", "phase": "reasoning"})
            emit({"type": "phase_start", "phase": "verification", "message": "Cache hit: reuse verification"})
            emit({"type": "phase_text", "phase": "verification", "text": "Using cached confidence/verification."})
            emit({"type": "phase_end", "phase": "verification"})
            cached_response['from_cache'] = True
            cached_response['execution_log'] = [{
                "step": "cache_hit",
                "timestamp": time.time(),
                "details": {"cached": True, "original_cache_time": cached_response.get('created_at')}
            }]
            return cached_response
        
        print("🔍 CACHE MISS: Processing query normally")
        context = {"user_query": user_query, "original_query": original_query, "original_lang": original_lang}
        
        emit({"type": "phase_start", "phase": "query_understanding", "message": "Analyzing intent and keywords"})
        print("PHASE 1: Query Understanding")
        print("-" * 70)
        query_result = self.query_agent.execute(context)
        log_step_local("query_understanding", query_result)
        emit({
            "type": "phase_text",
            "phase": "query_understanding",
            "text": f"Intent: {query_result.get('intent', 'n/a')}. Keywords: {', '.join(query_result.get('keywords', [])[:5])}"
        })
        emit({"type": "phase_end", "phase": "query_understanding"})
        
        if not query_result['success']:
            return self._build_error_response("Query understanding failed", query_result, execution_log)
        
        context.update(query_result)
        print(f"Intent: {query_result['intent']}")
        print(f"Keywords: {query_result['keywords'][:5]}")
        print()
        
        emit({"type": "phase_start", "phase": "retrieval", "message": "Searching knowledge base"})
        print("PHASE 2: Knowledge Retrieval")
        print("-" * 70)
        retrieval_result = self.retrieval_agent.execute(context)
        log_step_local("retrieval", retrieval_result)
        emit({
            "type": "phase_text",
            "phase": "retrieval",
            "text": f"Retrieved {retrieval_result.get('num_results', 0)} chunks using hybrid search." 
        })
        emit({"type": "phase_end", "phase": "retrieval"})
        
        if not retrieval_result['success']:
            return self._build_error_response("Retrieval failed", retrieval_result, execution_log)
        
        context.update(retrieval_result)
        num_results = retrieval_result['num_results']
        print(f"Retrieved {num_results} documents")
        
        if num_results == 0:
            # Check if vector store actually has documents - if so, do direct search fallback
            kb_count = self.vector_store.get_collection_count()
            if kb_count > 0:
                print(f"⚠ Hybrid search returned 0 but KB has {kb_count} docs. Trying direct vector search...")
                direct_results = self.vector_store.search(user_query, k=5)
                direct_docs = direct_results.get('documents', [])
                if direct_docs:
                    print(f"✓ Direct search found {len(direct_docs)} documents")
                    # Convert cosine similarity scores (higher=better) to distances (lower=better)
                    # to match the format used by HybridRetrievalAgent
                    raw_scores = direct_results.get('distances', [])
                    converted_distances = [1.0 - max(0.0, min(1.0, s)) for s in raw_scores]
                    retrieval_result = {
                        "success": True,
                        "documents": direct_docs,
                        "metadatas": direct_results.get('metadatas', []),
                        "retrieved_docs": direct_docs,
                        "retrieved_metadata": direct_results.get('metadatas', []),
                        "distances": converted_distances,
                        "num_results": len(direct_docs),
                        "retrieval_method": "direct_fallback"
                    }
                    context.update(retrieval_result)
                    num_results = len(direct_docs)
            
            if num_results == 0:
                print("⚠ No relevant documents found in knowledge base")
                emit({"type": "phase_start", "phase": "reasoning", "message": "No documents to reason over"})
                emit({"type": "phase_text", "phase": "reasoning", "text": "No relevant documents found."})
                emit({"type": "phase_end", "phase": "reasoning"})
                emit({"type": "phase_start", "phase": "verification", "message": "Skipping verification"})
                emit({"type": "phase_text", "phase": "verification", "text": "No answer to verify."})
                emit({"type": "phase_end", "phase": "verification"})
                return {
                    "success": True,
                    "query": user_query,
                    "answer": "I don't have relevant information in my knowledge base to answer this specialized question. Please upload related documents first.",
                    "confidence": 0.0,
                    "verified": False,
                    "num_iterations": 0,
                    "num_sources": 0,
                    "query_type": "specialized_no_docs",
                    "image_paths": [],
                    "artifact": None,
                    "from_cache": False,
                    "execution_log": execution_log
                }
        
        distances = retrieval_result.get('distances', [])
        best_distance = distances[0] if distances and len(distances) > 0 else 1.0
        low_relevance = best_distance > self.relevance_threshold
        if low_relevance:
            print(f"⚠ Retrieved documents have limited relevance (distance: {best_distance:.3f}). Proceeding anyway with warning.")
        else:
            print(f"✓ Found relevant documents (best distance: {best_distance:.3f})")
        print()
        context['low_relevance'] = low_relevance
        
        iteration = 0
        final_answer = None
        final_confidence = 0.0
        reasoning_result = None
        
        while iteration < self.max_refinement_iterations:
            iteration += 1
            
            emit({"type": "phase_start", "phase": "reasoning", "message": f"Generating answer (iteration {iteration})"})
            print(f"PHASE 3: Reasoning (Iteration {iteration})")
            print("-" * 70)
            
            reasoning_result = self.reasoning_agent.execute(context)
            log_step_local(f"reasoning_iter_{iteration}", reasoning_result)
            
            if not reasoning_result['success']:
                # On reasoning failure, use best answer so far if available
                if final_answer:
                    print(f"⚠ Reasoning failed on iteration {iteration}, using previous best answer")
                    break
                return self._build_error_response("Reasoning failed", reasoning_result, execution_log)
            
            answer = reasoning_result['answer']
            for chunk_start in range(0, len(answer), 160):
                emit({
                    "type": "phase_text",
                    "phase": "reasoning",
                    "text": answer[chunk_start:chunk_start + 160],
                    "append": True
                })
                time.sleep(0.02)
            emit({"type": "phase_end", "phase": "reasoning"})
            context['answer'] = answer
            
            print(f"Answer generated ({len(answer)} characters)")
            print(f"Preview: {answer[:200]}...")
            print()
            
            emit({"type": "phase_start", "phase": "verification", "message": f"Verifying answer (iteration {iteration})"})
            print(f"PHASE 4: Verification (Iteration {iteration})")
            print("-" * 70)
            
            verification_result = self.verification_agent.execute(context)
            log_step_local(f"verification_iter_{iteration}", verification_result)
            
            if not verification_result['success']:
                # Verification failure is non-fatal: accept the answer with default confidence
                print(f"⚠ Verification failed on iteration {iteration}, accepting answer with default confidence")
                final_answer = answer
                final_confidence = 0.5
                break
            
            confidence = verification_result['confidence']
            verified = verification_result['verified']
            issues = verification_result.get('issues', [])
            
            emit({
                "type": "phase_text",
                "phase": "verification",
                "text": f"Confidence: {confidence:.2f}. Verified: {verified}." 
            })
            emit({"type": "phase_end", "phase": "verification"})
            print(f"Confidence: {confidence:.2f}")
            print(f"Verified: {verified}")
            if issues:
                print(f"Issues: {issues}")
            print()
            
            final_answer = answer
            final_confidence = confidence
            
            if confidence >= self.confidence_threshold:
                print(f"✓ Confidence threshold met ({confidence:.2f} >= {self.confidence_threshold})")
                break
            
            if iteration < self.max_refinement_iterations:
                print(f"⚠ Confidence below threshold. Refining... (Iteration {iteration + 1})")
                # Propagate previous answer and issues so ReasoningAgent can improve
                context['previous_answer'] = answer
                context['verification_issues'] = issues
                context['refinement_request'] = f"Previous answer had issues: {issues}. Please refine and address these concerns."
        
        print("=" * 70)
        print("ORCHESTRATOR: Query processing complete")
        print("=" * 70 + "\n")
        
        final_text = final_answer
        if context.get('low_relevance') and final_answer:
            final_text = (
                f"{final_answer}\n\nNote: Retrieved documents had limited relevance. "
                "For higher accuracy, consider uploading more specific or related materials."
            )
        
        # Extract image_paths from reasoning result
        image_paths = reasoning_result.get('image_paths', []) if reasoning_result else []
        
        # Detect if response should trigger Canvas/Artifact panel
        artifact = self._detect_artifact_need(user_query, final_text, query_result.get('intent', ''))
        
        response = {
            "success": True,
            "query": user_query,
            "answer": final_text,
            "confidence": final_confidence,
            "verified": final_confidence >= self.confidence_threshold,
            "num_iterations": iteration,
            "num_sources": retrieval_result['num_results'],
            "execution_log": execution_log,
            "from_cache": False,
            "image_paths": image_paths,
            "artifact": artifact
        }
        
        # Cache successful responses with high confidence
        if response['success'] and response.get('confidence', 0) >= 0.7:
            self.cache.set(user_query, response)
            print("💾 CACHE: Response cached for future use")
        
        return response
    
    def _detect_artifact_need(self, query: str, answer: str, intent: str) -> Dict[str, Any]:
        """Detect if the response should open Canvas/Artifact panel"""
        # Keywords that suggest artifact creation
        artifact_keywords = [
            'report', 'summary', 'table', 'chart', 'visualization', 'analysis',
            'create', 'generate', 'build', 'compile', 'format', 'structure',
            'list all', 'show all', 'extract all', 'compare', 'contrast'
        ]
        
        query_lower = query.lower()
        answer_lower = answer.lower()
        
        # Check if query asks for structured output
        for keyword in artifact_keywords:
            if keyword in query_lower:
                # Determine artifact type based on content
                if 'table' in query_lower or '|' in answer:
                    return {"title": "Table Report", "type": "table", "content": answer}
                elif 'code' in query_lower or '```' in answer:
                    return {"title": "Code Output", "type": "code", "content": answer}
                elif len(answer) > 1000:  # Long response = report
                    return {"title": "Analysis Report", "type": "report", "content": self._format_as_html_report(answer, query)}
                else:
                    return {"title": "Summary", "type": "markdown", "content": answer}
        
        # Check if answer is very long (>1500 chars) - auto-generate report
        if len(answer) > 1500:
            return {"title": "Detailed Report", "type": "report", "content": self._format_as_html_report(answer, query)}
        
        return None
    
    def _format_as_html_report(self, content: str, query: str) -> str:
        """Format answer as HTML report for Canvas"""
        html_report = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: system-ui, -apple-system, sans-serif; padding: 2rem; max-width: 900px; margin: 0 auto; line-height: 1.6; }}
                h1 {{ color: #1e293b; border-bottom: 3px solid #3b82f6; padding-bottom: 0.5rem; }}
                h2 {{ color: #334155; margin-top: 2rem; }}
                p {{ color: #475569; margin: 1rem 0; }}
                .metadata {{ background: #f1f5f9; padding: 1rem; border-radius: 0.5rem; margin: 1.5rem 0; }}
                .sources {{ margin-top: 2rem; padding-top: 1rem; border-top: 2px solid #e2e8f0; }}
                strong {{ color: #1e293b; }}
            </style>
        </head>
        <body>
            <h1>Research Report</h1>
            <div class="metadata">
                <strong>Query:</strong> {html.escape(query)}
            </div>
            <div class="content">
                {self._convert_to_html_paragraphs(content)}
            </div>
        </body>
        </html>
        """
        return html_report
    
    def _convert_to_html_paragraphs(self, text: str) -> str:
        """Convert plain text to HTML paragraphs"""
        paragraphs = text.split('\n\n')
        html_parts = []
        for p in paragraphs:
            if p.strip():
                # Escape HTML entities first to prevent XSS
                p_escaped = html.escape(p.strip())
                # Check if it's a heading
                if p_escaped.startswith('##'):
                    html_parts.append(f'<h2>{p_escaped.replace("##", "").strip()}</h2>')
                else:
                    # Convert **bold** to <strong>bold</strong> using regex
                    p_html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', p_escaped)
                    html_parts.append(f'<p>{p_html}</p>')
        return '\n'.join(html_parts)
    
    def _build_error_response(self, message: str, details: Dict[str, Any], execution_log: list = None) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
            "details": details,
            "execution_log": execution_log or []
        }
    
    def print_result(self, result: Dict[str, Any]):
        print("\n" + "=" * 70)
        print("FINAL RESULT")
        print("=" * 70)
        
        if result['success']:
            print(f"\nQuery: {result['query']}")
            print(f"\nAnswer:\n{result['answer']}")
            print(f"\nConfidence: {result['confidence']:.2f}")
            print(f"Verified: {result['verified']}")
            print(f"Iterations: {result['num_iterations']}")
            print(f"Sources Used: {result['num_sources']}")
        else:
            print(f"\n Error: {result['error']}")
            if 'details' in result:
                print(f"Details: {result['details']}")
        
        print("\n" + "=" * 70)
