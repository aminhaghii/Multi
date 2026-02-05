from .base_agent import BaseAgent
from typing import Dict, Any, List, Optional
import json
import os
import re
import traceback
import time
from datetime import datetime

class QueryUnderstandingAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__(
            name="QueryUnderstandingAgent",
            description="Analyzes user query to extract intent, keywords, and query type"
        )
        self.llm_client = llm_client
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        user_query = context.get("user_query", "")
        
        if not user_query:
            return {
                "success": False,
                "error": "No user query provided"
            }
        
        self.log(f"Analyzing query: {user_query[:100]}...")
        
        prompt = f"""Analyze this query and extract:
1. Intent (research/analytical/descriptive/comparison)
2. Key concepts (list main topics)
3. Expected answer type (factual/explanatory/listing)
4. Expanded query terms (synonyms, related concepts)

Query: {user_query}

Respond in this exact format:
Intent: [intent]
Keywords: [keyword1, keyword2, keyword3]
Answer Type: [type]
Expanded Terms: [term1, term2, term3]"""

        result = self.llm_client.generate(
            prompt=prompt,
            max_tokens=200,
            temperature=0.3
        )
        
        if not result['success']:
            return {
                "success": False,
                "error": result.get('error', 'LLM generation failed')
            }
        
        response_text = result['text'].strip()
        
        intent = "research"
        keywords = []
        answer_type = "explanatory"
        expanded_terms = []
        
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('Intent:'):
                intent = line.split(':', 1)[1].strip().lower()
            elif line.startswith('Keywords:'):
                kw_text = line.split(':', 1)[1].strip()
                keywords = [k.strip() for k in kw_text.split(',')]
            elif line.startswith('Answer Type:'):
                answer_type = line.split(':', 1)[1].strip().lower()
            elif line.startswith('Expanded Terms:'):
                exp_text = line.split(':', 1)[1].strip()
                expanded_terms = [t.strip() for t in exp_text.split(',')]
        
        if not keywords:
            keywords = user_query.split()[:5]
        
        # Combine original keywords with expanded terms for better retrieval
        all_search_terms = keywords + expanded_terms
        
        self.log(f"Extracted - Intent: {intent}, Keywords: {keywords[:3]}, Expanded: {len(expanded_terms)}")
        
        return {
            "success": True,
            "intent": intent,
            "keywords": keywords,
            "expanded_terms": expanded_terms,
            "all_search_terms": all_search_terms,
            "answer_type": answer_type,
            "original_query": user_query
        }


class RetrievalAgent(BaseAgent):
    def __init__(self, vector_store):
        super().__init__(
            name="RetrievalAgent",
            description="Retrieves relevant documents and images from knowledge base"
        )
        self.vector_store = vector_store
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        query = context.get("user_query", "")
        keywords = context.get("keywords", [])
        k = context.get("top_k", 10)  # FIX 3: Increased from 5 to 10 for better coverage
        
        if not query:
            return {
                "success": False,
                "error": "No query provided"
            }
        
        self.log(f"Searching for: {query[:100]}...")
        
        search_query = f"{query} {' '.join(keywords[:3])}"
        
        results = self.vector_store.search(search_query, k=k)
        
        if not results['documents']:
            self.log("No documents found", level="WARN")
            return {
                "success": True,
                "retrieved_docs": [],
                "retrieved_metadata": [],
                "num_results": 0
            }
        
        self.log(f"Retrieved {len(results['documents'])} documents")
        
        def _normalize_image_path(image_path: str) -> str:
            """Ensure image paths are web-accessible under /static/images/ to avoid 404s."""
            if not image_path:
                return ""
            if image_path.startswith("/static/images/"):
                return image_path
            normalized = image_path.replace("\\", "/")
            marker = "/static/images/"
            if marker in normalized:
                return normalized[normalized.index(marker):]
            if normalized.startswith("./static/images/"):
                return normalized.replace("./static", "")
            return image_path
        
        retrieved_metadata = []
        for meta in results['metadatas']:
            if 'images' in meta and isinstance(meta['images'], str):
                normalized_paths = [
                    _normalize_image_path(p.strip())
                    for p in meta['images'].split(',')
                    if p.strip()
                ]
                meta['images'] = ",".join(normalized_paths)
            if meta.get('image_path'):
                meta['image_path'] = _normalize_image_path(meta['image_path'])
            retrieved_metadata.append(meta)
        
        return {
            "success": True,
            "retrieved_docs": results['documents'],
            "retrieved_metadata": retrieved_metadata,
            "retrieved_ids": results['ids'],
            "search_query": search_query
        }


class ReasoningAgent(BaseAgent):
    def __init__(self, llm_client, image_captioner=None):
        super().__init__(
            name="ReasoningAgent",
            description="Generates answer using Chain-of-Thought reasoning"
        )
        self.llm_client = llm_client
        self.image_captioner = image_captioner
        self.max_retries = 3
        self.failure_log = []
    
    def _log_failure(self, error: Exception, context_info: Dict[str, Any]):
        """Log detailed failure information for debugging."""
        failure_entry = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'query': context_info.get('query', '')[:200],
            'context_length': context_info.get('context_length', 0),
            'prompt_length': context_info.get('prompt_length', 0)
        }
        self.failure_log.append(failure_entry)
        
        # Log to console
        print(f"\n{'='*80}")
        print(f"[ReasoningAgent] FAILURE LOG:")
        print(f"  Time: {failure_entry['timestamp']}")
        print(f"  Error Type: {failure_entry['error_type']}")
        print(f"  Error: {failure_entry['error_message']}")
        print(f"  Query: {failure_entry['query'][:100]}...")
        print(f"  Context Length: {failure_entry['context_length']} chars")
        print(f"  Prompt Length: {failure_entry['prompt_length']} chars")
        print(f"{'='*80}\n")
        
        # Write to log file
        try:
            os.makedirs('logs', exist_ok=True)
            with open('logs/reasoning_failures.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps(failure_entry, ensure_ascii=False) + '\n')
        except Exception as log_error:
            print(f"[ReasoningAgent] Could not write to log file: {log_error}")
    
    def _simplified_reasoning(self, query: str, context_text: str) -> Optional[str]:
        """Fallback: Use simplified prompt for reasoning."""
        self.log("Attempting simplified reasoning (Fallback Level 1)...")
        
        prompt = f"""You are a research assistant. Based on the following context, answer the question.

Context from documents:
{context_text}

Question: {query}

Provide a clear, accurate answer based ONLY on the context above. 
IMPORTANT: Add inline citations using [Source: filename, Page: X] format after each claim or fact.
If the context doesn't contain enough information, say so.

Answer:"""
        
        result = self.llm_client.generate(
            prompt=prompt,
            max_tokens=400,
            temperature=0.1
        )
        
        if result['success'] and result.get('text', '').strip():
            return result['text'].strip()
        return None
    
    def _direct_extraction(self, query: str, retrieved_docs: List[str], retrieved_metadata: List[Dict]) -> str:
        """Fallback Level 3: Direct text extraction without LLM."""
        self.log("Attempting direct extraction (Fallback Level 3)...")
        
        query_words = set(query.lower().split())
        relevant_sentences = []
        
        for doc, meta in zip(retrieved_docs[:3], retrieved_metadata[:3]):
            sentences = doc.replace('\n', ' ').split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 30:
                    sentence_words = set(sentence.lower().split())
                    overlap = len(query_words & sentence_words)
                    if overlap >= 2:
                        source = os.path.basename(meta.get('source', 'document'))
                        page = meta.get('page', 0) + 1
                        relevant_sentences.append(f"{sentence}. (Source: {source}, Page: {page})")
        
        if relevant_sentences:
            return "Based on the documents, I found the following relevant information:\n\n" + "\n\n".join(relevant_sentences[:5])
        
        return None
    
    def _graceful_fallback(self, query: str, retrieved_metadata: List[Dict]) -> str:
        """Final fallback: Return helpful error with source information."""
        self.log("Using graceful fallback (Final Level)...")
        
        sources = []
        for meta in retrieved_metadata[:3]:
            source = os.path.basename(meta.get('source', 'document'))
            page = meta.get('page', 0) + 1
            sources.append(f"{source} (Page {page})")
        
        if sources:
            source_list = ", ".join(sources)
            return f"""I found relevant information in the documents but encountered a processing error.

The relevant sections are from: {source_list}

Please try:
1. Rephrasing your question more specifically
2. Asking about a smaller topic
3. Requesting information from a specific page or section"""
        
        return "I was unable to process your query. Please try rephrasing your question or uploading relevant documents."
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        user_query = context.get("user_query", "")
        retrieved_docs = context.get("retrieved_docs", [])
        retrieved_metadata = context.get("retrieved_metadata", [])
        
        if not user_query:
            return {
                "success": False,
                "error": "No query provided"
            }
        
        self.log("Generating answer with Chain-of-Thought reasoning...")
        
        all_image_paths = []
        for meta in retrieved_metadata[:3]:
            if meta.get('images'):
                paths = [p.strip() for p in meta['images'].split(',') if p.strip()]
                all_image_paths.extend(paths)
        
        multimodal_available = self.llm_client.multimodal_health_check()
        use_multimodal = multimodal_available and len(all_image_paths) > 0
        
        if use_multimodal:
            self.log(f"Using multimodal server with {len(all_image_paths)} image(s)")
        
        # Collect image paths for response - ONLY from TOP 3 most relevant docs
        response_image_paths = []
        seen_paths = set()  # Track unique paths to avoid duplicates
        
        if retrieved_docs:
            context_parts = []
            
            for i, (doc, meta) in enumerate(zip(retrieved_docs[:3], retrieved_metadata[:3])):
                # Extract filename and page from metadata for citations
                source_path = meta.get('source', 'unknown')
                filename = os.path.basename(source_path)
                page_num = meta.get('page', 0) + 1  # Convert to 1-indexed
                
                # Check for images in this chunk
                has_image = meta.get('has_image', False)
                image_path = meta.get('image_path', '')
                
                # Also check legacy 'images' field
                if not image_path and meta.get('images'):
                    img_paths = [p.strip() for p in meta['images'].split(',') if p.strip()]
                    if img_paths:
                        image_path = img_paths[0]
                        has_image = True
                
                # Build context with SOURCE attribution
                doc_text = f"[[SOURCE: {filename} | PAGE: {page_num}]]\n{doc}"
                
                # Add image path info if available (avoid duplicates)
                if has_image and image_path and image_path not in seen_paths:
                    doc_text += f"\n[[IMAGE_PATH: {image_path}]]"
                    seen_paths.add(image_path)
                    response_image_paths.append({
                        'path': image_path,
                        'source': filename,
                        'page': page_num
                    })
                
                if not use_multimodal and self.image_captioner and meta.get('images'):
                    image_paths = [p.strip() for p in meta['images'].split(',') if p.strip()]
                    if image_paths:
                        self.log(f"Captioning {len(image_paths)} image(s) from document {i+1}")
                        captions = self.image_captioner.caption_multiple(image_paths)
                        if captions:
                            img_desc = " | ".join([f"Image: {cap}" for cap in captions])
                            doc_text += f"\n{img_desc}"
                
                context_parts.append(doc_text)
            
            context_text = "\n\n".join(context_parts)
            
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are an expert technical assistant analyzing documents.
Your goal is to answer questions strictly based on the provided context.

CRITICAL INSTRUCTIONS:
1. Answer ONLY using the provided Context.
2. You MUST cite the source filename and page number for every key fact. Format: (Source: filename.pdf, Page: X)
3. If the Context contains section numbers (e.g., 3.2.1, 5.4.1), cite them too.
4. Use the exact technical terminology found in the text.
5. If a retrieved chunk contains [[IMAGE_PATH: ...]], display it using ONLY this format: ![Description](path)
   - The path MUST be EXACTLY as provided in [[IMAGE_PATH: ...]]
   - DO NOT add any text after the image path
   - DO NOT include citations or sources inside the image markdown
6. If the answer is not in the context, state "Insufficient information provided."
7. ALWAYS write citations AFTER images, never inside image markdown syntax.

---
EXAMPLE (How to answer with citations and images):
Context: "[[SOURCE: design_doc.pdf | PAGE: 15]]
3.2.1 attitude and orbit control system (AOCS): functional chain of a satellite...
[[IMAGE_PATH: /static/images/fig1.png]]"
Question: "Define AOCS."
Answer: "According to section 3.2.1, AOCS is defined as the functional chain of a satellite which encompasses attitude and orbit sensors, actuators, and algorithms. (Source: design_doc.pdf, Page: 15)

![AOCS Diagram](/static/images/fig1.png)

(Source: design_doc.pdf, Page: 15)"

WRONG EXAMPLE (DO NOT DO THIS):
![Figure](/static/images/fig1.png) (Source: doc.pdf, Page: 5)
![Figure](/static/images/fig1.png**Sources:**)

CORRECT EXAMPLE:
![Figure](/static/images/fig1.png)

(Source: doc.pdf, Page: 5)
---
<|eot_id|><|start_header_id|>user<|end_header_id|>

Context:
{context_text}

Question:
{user_query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
        else:
            prompt = f"""Question: {user_query}

Think step-by-step and provide a clear, concise answer.

Answer:"""
        
        # Log prompt length for monitoring (remove verbose debug in production)
        self.log(f"Prompt length: {len(prompt)} chars")
        
        if use_multimodal:
            result = self.llm_client.generate_with_images(
                prompt=prompt,
                image_paths=all_image_paths[:3],
                max_tokens=600,
                temperature=0.1
            )
        else:
            result = self.llm_client.generate(
                prompt=prompt,
                max_tokens=600,
                temperature=0.1
            )
        
        # FALLBACK MECHANISM: Try multiple approaches if reasoning fails
        answer = None
        fallback_used = None
        
        # Attempt 1: Full reasoning with LLM
        if result['success'] and result.get('text', '').strip():
            answer = result['text'].strip()
            self.log("Full reasoning succeeded")
        else:
            # Log the failure
            error = Exception(result.get('error', 'LLM generation failed'))
            self._log_failure(error, {
                'query': user_query,
                'context_length': len(context_text) if 'context_text' in dir() else 0,
                'prompt_length': len(prompt) if 'prompt' in dir() else 0
            })
            
            # Attempt 2: Simplified reasoning
            if retrieved_docs:
                context_text_simple = "\n".join(retrieved_docs[:2])
                answer = self._simplified_reasoning(user_query, context_text_simple)
                if answer:
                    fallback_used = "simplified_reasoning"
                    self.log("Simplified reasoning succeeded")
            
            # Attempt 3: Direct extraction (no LLM)
            if not answer and retrieved_docs:
                answer = self._direct_extraction(user_query, retrieved_docs, retrieved_metadata)
                if answer:
                    fallback_used = "direct_extraction"
                    self.log("Direct extraction succeeded")
            
            # Final fallback: Graceful error message
            if not answer:
                answer = self._graceful_fallback(user_query, retrieved_metadata)
                fallback_used = "graceful_fallback"
                self.log("Using graceful fallback")
        
        if not answer:
            answer = "I was unable to generate an answer. Please try rephrasing your question."
        
        # HARD FIX: Programmatically append citations footer
        if retrieved_metadata:
            # Collect unique source citations
            seen_citations = set()
            citation_list = []
            for meta in retrieved_metadata[:5]:  # Top 5 sources
                filename = meta.get('filename', os.path.basename(meta.get('source', 'unknown')))
                page = meta.get('page', 0) + 1  # 1-indexed
                citation_key = f"{filename}:{page}"
                if citation_key not in seen_citations:
                    seen_citations.add(citation_key)
                    citation_list.append(f"- {filename} (Page {page})")
            
            if citation_list:
                answer += "\n\n**Sources:**\n" + "\n".join(citation_list)
        
        # Images are already included in LLM response via [[IMAGE_PATH:...]] markers in prompt
        # No need to append them again to avoid duplicates
        
        self.log(f"Generated answer ({len(answer)} chars)")
        
        return {
            "success": True,
            "answer": answer,
            "used_context": len(retrieved_docs) > 0,
            "used_multimodal": use_multimodal,
            "image_paths": response_image_paths,
            "fallback_used": fallback_used  # Track if fallback was used
        }


class VerificationAgent(BaseAgent):
    def __init__(self, llm_client):
        super().__init__(
            name="VerificationAgent",
            description="Verifies answer accuracy and calculates confidence score"
        )
        self.llm_client = llm_client
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        answer = context.get("answer", "")
        retrieved_docs = context.get("retrieved_docs", [])
        user_query = context.get("user_query", "")
        
        if not answer:
            return {
                "success": False,
                "error": "No answer to verify"
            }
        
        self.log("Verifying answer accuracy...")
        
        if not retrieved_docs:
            self.log("No context available for verification", level="WARN")
            return {
                "success": True,
                "confidence": 0.5,
                "verified": False,
                "issues": ["No source documents to verify against"]
            }
        
        context_text = "\n".join([doc[:1000] for doc in retrieved_docs[:3]])  # Increased for verification
        
        prompt = f"""Verify if the answer is supported by the context and check citation accuracy.

Context:
{context_text}

Question: {user_query}
Answer: {answer}

Verification checklist:
1. Does the answer align with the context?
2. Are citations present and accurate?
3. Are technical terms used correctly?
4. Is any information contradicted by the context?

Response format:
Confidence: [0.0-1.0]
Citation Quality: [good/partial/missing]
Issues: [list issues or "None"]"""

        result = self.llm_client.generate(
            prompt=prompt,
            max_tokens=200,
            temperature=0.3
        )
        
        confidence = 0.7
        issues = []
        
        if result['success']:
            response = result['text'].strip()
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('Confidence:'):
                    try:
                        conf_str = line.split(':', 1)[1].strip()
                        confidence = float(conf_str)
                        confidence = max(0.0, min(1.0, confidence))
                    except:
                        pass
                elif line.startswith('Issues:'):
                    issue_text = line.split(':', 1)[1].strip()
                    if issue_text.lower() != "none":
                        issues.append(issue_text)
        
        verified = confidence >= 0.7
        
        self.log(f"Confidence: {confidence:.2f}, Verified: {verified}")
        
        return {
            "success": True,
            "confidence": confidence,
            "verified": verified,
            "issues": issues
        }
