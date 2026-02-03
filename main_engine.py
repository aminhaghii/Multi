from agents import QueryUnderstandingAgent, RetrievalAgent, ReasoningAgent, VerificationAgent
from llm_client import LLMClient
from vector_store import VectorStore
from cache import get_cache
from typing import Dict, Any
import time
import re

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
        self.relevance_threshold = 0.85
        
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
        
        self.execution_log = []
        self.cache = get_cache()
    
    def log_step(self, step: str, details: Dict[str, Any]):
        log_entry = {
            "step": step,
            "timestamp": time.time(),
            "details": details
        }
        self.execution_log.append(log_entry)
    
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
                    print(f"🌐 TRANSLATION (API): '{query}' -> '{result.text}'")
                    return result.text, original_lang
            except Exception as e:
                print(f"Translation API error: {e}")
        
        # Last resort: return original
        print(f"🌐 TRANSLATION: No translation available for '{query}'")
        return query, original_lang
    
    def _detect_query_type(self, user_query: str) -> str:
        """Detect if query is casual/general or requires specialized knowledge from RAG"""
        casual_patterns = [
            'hello', 'hi', 'hey', 'salam', 'how are you', 'what\'s up', 
            'good morning', 'good evening', 'thanks', 'thank you',
            'bye', 'goodbye', 'see you', 'khobi', 'halet chetore', 'mersi',
            'سلام', 'خوبی', 'چطوری', 'ممنون', 'تشکر', 'خداحافظ', 'چه خبر'
        ]
        
        query_lower = user_query.lower()
        
        # Check for exact matches or very short queries
        words = query_lower.split()
        if len(words) <= 2:
            return 'casual'
            
        for pattern in casual_patterns:
            if pattern in query_lower:
                # If it's a long query containing "salam", it might still be specialized
                # but if it's just the pattern or the pattern plus a few words, it's casual
                if len(words) <= 5:
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
            "sources": [],
            "image_paths": [],
            "execution_log": [{
                "step": "casual_query_redirect",
                "timestamp": time.time(),
                "details": {"type": "casual", "redirected_to_kb_focus": True}
            }]
        }
    
    def run_query(self, user_query: str) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("ORCHESTRATOR: Starting query processing")
        print("=" * 70 + "\n")
        
        self.execution_log = []
        original_query = user_query
        original_lang = 'en'
        
        # FIX 4: Translation layer for non-English queries
        if self._is_non_english(user_query):
            print(f" Detected non-English query: {user_query}")
            user_query, original_lang = self._translate_query(user_query)
            self.log_step("translation", {
                "original_query": original_query,
                "translated_query": user_query,
                "original_lang": original_lang
            })
        
        # Check cache first for specialized queries
        query_type = self._detect_query_type(user_query)
        print(f"QUERY TYPE: {query_type}")
        print("-" * 70)
        
        if query_type == 'casual':
            print("Handling as casual query (no RAG needed)")
            return self._handle_casual_query(user_query)
        
        # Cache disabled to prevent stale responses
        # cached_response = self.cache.get(user_query)
        # if cached_response:
        #     print(f" CACHE HIT: Returning cached response")
        #     cached_response['from_cache'] = True
        #     cached_response['execution_log'] = [{
        #         "step": "cache_hit",
        #         "timestamp": time.time(),
        #         "details": {"cached": True, "original_cache_time": cached_response.get('created_at')}
        #     }]
        #     return cached_response
        
        print(" CACHE DISABLED: Processing query normally")
        context = {"user_query": user_query, "original_query": original_query, "original_lang": original_lang}
        
        print("PHASE 1: Query Understanding")
        print("-" * 70)
        query_result = self.query_agent.execute(context)
        self.log_step("query_understanding", query_result)
        
        if not query_result['success']:
            return self._build_error_response("Query understanding failed", query_result)
        
        context.update(query_result)
        print(f"Intent: {query_result['intent']}")
        print(f"Keywords: {query_result['keywords'][:5]}")
        print()
        
        print("PHASE 2: Knowledge Retrieval")
        print("-" * 70)
        retrieval_result = self.retrieval_agent.execute(context)
        self.log_step("retrieval", retrieval_result)
        
        if not retrieval_result['success']:
            return self._build_error_response("Retrieval failed", retrieval_result)
        
        context.update(retrieval_result)
        num_results = retrieval_result['num_results']
        print(f"Retrieved {num_results} documents")
        
        if num_results == 0:
            print("⚠ No relevant documents found in knowledge base")
            return {
                "success": True,
                "query": user_query,
                "answer": "I don't have relevant information in my knowledge base to answer this specialized question. Please upload related documents first.",
                "confidence": 0.0,
                "verified": False,
                "num_iterations": 0,
                "num_sources": 0,
                "query_type": "specialized_no_docs",
                "execution_log": self.execution_log
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
        
        while iteration < self.max_refinement_iterations:
            iteration += 1
            
            print(f"PHASE 3: Reasoning (Iteration {iteration})")
            print("-" * 70)
            
            reasoning_result = self.reasoning_agent.execute(context)
            self.log_step(f"reasoning_iter_{iteration}", reasoning_result)
            
            if not reasoning_result['success']:
                return self._build_error_response("Reasoning failed", reasoning_result)
            
            answer = reasoning_result['answer']
            context['answer'] = answer
            
            print(f"Answer generated ({len(answer)} characters)")
            print(f"Preview: {answer[:200]}...")
            print()
            
            print(f"PHASE 4: Verification (Iteration {iteration})")
            print("-" * 70)
            
            verification_result = self.verification_agent.execute(context)
            self.log_step(f"verification_iter_{iteration}", verification_result)
            
            if not verification_result['success']:
                return self._build_error_response("Verification failed", verification_result)
            
            confidence = verification_result['confidence']
            verified = verification_result['verified']
            issues = verification_result.get('issues', [])
            
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
                context['refinement_request'] = f"Previous answer had issues: {issues}. Please refine."
        
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
            "execution_log": self.execution_log,
            "from_cache": False,
            "image_paths": image_paths,
            "artifact": artifact
        }
        
        # Cache disabled to prevent stale responses
        # if response['success']:
        #     self.cache.set(user_query, response)
        #     print(" CACHE: Response cached for future use")
        
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
        html = f"""
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
                <strong>Query:</strong> {query}
            </div>
            <div class="content">
                {self._convert_to_html_paragraphs(content)}
            </div>
        </body>
        </html>
        """
        return html
    
    def _convert_to_html_paragraphs(self, text: str) -> str:
        """Convert plain text to HTML paragraphs"""
        paragraphs = text.split('\n\n')
        html_parts = []
        for p in paragraphs:
            if p.strip():
                # Check if it's a heading
                if p.startswith('##'):
                    html_parts.append(f'<h2>{p.replace("##", "").strip()}</h2>')
                elif p.startswith('**') or '**' in p:
                    # Bold text
                    p_html = p.replace('**', '<strong>').replace('**', '</strong>')
                    html_parts.append(f'<p>{p_html}</p>')
                else:
                    html_parts.append(f'<p>{p}</p>')
        return '\n'.join(html_parts)
    
    def _build_error_response(self, message: str, details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
            "details": details,
            "execution_log": self.execution_log
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
