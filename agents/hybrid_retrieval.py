"""
Hybrid Retrieval Agent - ترکیب Vector + Keyword Search
این agent مشکل اصلی retrieval را حل می‌کند
"""

import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """نتیجه جستجو با metadata"""
    document: str
    metadata: Dict[str, Any]
    score: float
    source: str  # 'vector', 'keyword', 'section'
    chunk_index: int

class HybridRetrievalAgent:
    """
    Agent هیبریدی برای بهبود retrieval accuracy
    
    ترکیب سه روش:
    1. Vector Similarity Search
    2. Keyword Exact Match
    3. Section Number Search (برای 3.2.9, etc.)
    """
    
    def __init__(self, vector_store, config: Optional[Dict] = None):
        self.vs = vector_store
        self.config = config or {}
        
        # تنظیمات پیش‌فرض
        self.vector_weight = self.config.get('vector_weight', 0.4)
        self.keyword_weight = self.config.get('keyword_weight', 0.4)
        self.section_weight = self.config.get('section_weight', 0.2)
        self.min_keyword_score = self.config.get('min_keyword_score', 0.1)
        
        # Technical terms برای aerospace domain
        self.technical_terms = {
            'worst case analysis', 'sensitivity analysis', 'monte carlo',
            'pointing error', 'thermal control', 'power budget',
            'link budget', 'orbit determination', 'attitude control',
            'ecss', 'fmea', 'fmeca', 'reliability', 'redundancy'
        }
        
        logger.info("HybridRetrievalAgent initialized with weights: "
                   f"vector={self.vector_weight}, keyword={self.keyword_weight}, "
                   f"section={self.section_weight}")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        اجرای جستجوی هیبریدی
        
        Args:
            context: شامل user_query و سایر اطلاعات
            
        Returns:
            Dict با documents, metadatas, scores
        """
        query = context.get("user_query", "")
        k = context.get("top_k", 10)  # FIX 3: Increased from 5 to 10 for better coverage
        
        if not query:
            return self._empty_result("Empty query")
        
        logger.info(f"🔍 Hybrid search for: '{query[:50]}...'")
        
        try:
            # 1. Vector Search
            vector_results = self._vector_search(query, k * 2)
            logger.debug(f"Vector search returned {len(vector_results)} results")
            
            # 2. Keyword Search
            keyword_results = self._keyword_search(query, k * 2)
            logger.debug(f"Keyword search returned {len(keyword_results)} results")
            
            # 3. Section Number Search
            section_results = self._section_search(query, k)
            logger.debug(f"Section search returned {len(section_results)} results")
            
            # 4. Merge and Re-rank
            merged_results = self._merge_and_rerank(
                vector_results, 
                keyword_results, 
                section_results,
                query
            )
            
            # 5. Select top k
            final_results = merged_results[:k]
            
            # 6. Build response
            return self._build_response(final_results, query)
            
        except Exception as e:
            logger.error(f"Hybrid retrieval error: {e}")
            return self._empty_result(str(e))
    
    def _vector_search(self, query: str, k: int) -> List[SearchResult]:
        """Vector similarity search"""
        results = []
        
        try:
            search_result = self.vs.search(query, k=k)
            
            documents = search_result.get('documents', [])
            metadatas = search_result.get('metadatas', [])
            distances = search_result.get('distances', [])
            
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                # Convert distance to similarity score (0-1)
                distance = distances[i] if i < len(distances) else 1.0
                score = 1.0 / (1.0 + distance)  # Inverse distance
                
                results.append(SearchResult(
                    document=doc,
                    metadata=meta or {},
                    score=score,
                    source='vector',
                    chunk_index=i
                ))
                
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
        
        return results
    
    def _keyword_search(self, query: str, k: int) -> List[SearchResult]:
        """Keyword-based exact match search"""
        results = []
        
        # Extract keywords
        keywords = self._extract_keywords(query)
        
        if not keywords:
            return results
        
        # Get all documents from vector store
        all_docs = getattr(self.vs, 'documents', [])
        all_metas = getattr(self.vs, 'metadatas', [])
        
        if not all_docs:
            logger.warning("No documents in vector store for keyword search")
            return results
        
        # Score each document
        scored_docs = []
        for i, (doc, meta) in enumerate(zip(all_docs, all_metas)):
            score = self._calculate_keyword_score(doc, keywords)
            
            if score >= self.min_keyword_score:
                scored_docs.append((i, doc, meta or {}, score))
        
        # Sort by score
        scored_docs.sort(key=lambda x: x[3], reverse=True)
        
        # Convert to SearchResult
        for i, (idx, doc, meta, score) in enumerate(scored_docs[:k]):
            results.append(SearchResult(
                document=doc,
                metadata=meta,
                score=score,
                source='keyword',
                chunk_index=idx
            ))
        
        return results
    
    def _section_search(self, query: str, k: int) -> List[SearchResult]:
        """Search for section numbers like 3.2.9"""
        results = []
        
        # Find section patterns in query
        section_pattern = r'\d+\.\d+(?:\.\d+)?'
        sections = re.findall(section_pattern, query)
        
        if not sections:
            return results
        
        logger.info(f"🔢 Searching for sections: {sections}")
        
        # Get all documents
        all_docs = getattr(self.vs, 'documents', [])
        all_metas = getattr(self.vs, 'metadatas', [])
        
        for section in sections:
            for i, (doc, meta) in enumerate(zip(all_docs, all_metas)):
                if section in doc:
                    # Higher score for exact section match
                    score = 0.9 if f" {section} " in f" {doc} " else 0.7
                    
                    results.append(SearchResult(
                        document=doc,
                        metadata=meta or {},
                        score=score,
                        source='section',
                        chunk_index=i
                    ))
        
        # Remove duplicates and sort
        seen = set()
        unique_results = []
        for r in results:
            doc_hash = hash(r.document[:200])
            if doc_hash not in seen:
                seen.add(doc_hash)
                unique_results.append(r)
        
        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:k]
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query"""
        # Convert to lowercase
        query_lower = query.lower()
        
        # Remove stop words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these',
            'those', 'am', 'or', 'and', 'but', 'if', 'because', 'until',
            'while', 'about', 'against', 'how', 'where', 'when', 'why',
            'چیست', 'است', 'در', 'از', 'به', 'که', 'این', 'آن', 'با', 'را'
        }
        
        # Tokenize
        words = re.findall(r'\b\w+\b', query_lower)
        
        # Filter stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Add technical multi-word terms
        for term in self.technical_terms:
            if term in query_lower:
                keywords.append(term)
        
        return list(set(keywords))
    
    def _calculate_keyword_score(self, document: str, keywords: List[str]) -> float:
        """Calculate keyword match score for a document"""
        if not keywords:
            return 0.0
        
        doc_lower = document.lower()
        
        # Count matches
        matches = 0
        total_weight = 0
        
        for keyword in keywords:
            weight = 2.0 if keyword in self.technical_terms else 1.0
            total_weight += weight
            
            if keyword in doc_lower:
                # Exact match gets full weight
                matches += weight
                
                # Bonus for multiple occurrences
                count = doc_lower.count(keyword)
                if count > 1:
                    matches += weight * 0.1 * min(count - 1, 3)
        
        return matches / total_weight if total_weight > 0 else 0.0
    
    def _merge_and_rerank(
        self,
        vector_results: List[SearchResult],
        keyword_results: List[SearchResult],
        section_results: List[SearchResult],
        query: str
    ) -> List[SearchResult]:
        """Merge results from all sources and re-rank"""
        
        # Combine all results
        all_results = []
        doc_scores = defaultdict(lambda: {'scores': [], 'result': None})
        
        # Process each source
        for result in vector_results:
            doc_hash = hash(result.document[:200])
            doc_scores[doc_hash]['scores'].append(
                ('vector', result.score * self.vector_weight)
            )
            doc_scores[doc_hash]['result'] = result
        
        for result in keyword_results:
            doc_hash = hash(result.document[:200])
            doc_scores[doc_hash]['scores'].append(
                ('keyword', result.score * self.keyword_weight)
            )
            if doc_scores[doc_hash]['result'] is None:
                doc_scores[doc_hash]['result'] = result
        
        for result in section_results:
            doc_hash = hash(result.document[:200])
            doc_scores[doc_hash]['scores'].append(
                ('section', result.score * self.section_weight)
            )
            if doc_scores[doc_hash]['result'] is None:
                doc_scores[doc_hash]['result'] = result
        
        # Calculate final scores
        for doc_hash, data in doc_scores.items():
            if data['result'] is None:
                continue
            
            # Sum weighted scores
            final_score = sum(score for _, score in data['scores'])
            
            # Bonus for appearing in multiple sources
            source_count = len(data['scores'])
            if source_count > 1:
                final_score *= (1 + 0.1 * (source_count - 1))
            
            result = data['result']
            result.score = final_score
            result.source = '+'.join(sorted(set(s for s, _ in data['scores'])))
            all_results.append(result)
        
        # Sort by final score
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        return all_results
    
    def _build_response(self, results: List[SearchResult], query: str) -> Dict[str, Any]:
        """Build final response dict"""
        
        if not results:
            return self._empty_result("No results found")
        
        # Convert scores to distances (inverse) for compatibility with main_engine
        distances = [1.0 - min(r.score, 0.99) for r in results]
        
        return {
            "success": True,
            # Use BOTH key names for compatibility
            "documents": [r.document for r in results],
            "metadatas": [r.metadata for r in results],
            "retrieved_docs": [r.document for r in results],  # For ReasoningAgent
            "retrieved_metadata": [r.metadata for r in results],  # For ReasoningAgent
            "scores": [r.score for r in results],
            "distances": distances,  # For main_engine relevance check
            "sources": [r.source for r in results],
            "num_results": len(results),
            "retrieval_method": "hybrid",
            "query": query
        }
    
    def _empty_result(self, reason: str) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "success": False,
            "documents": [],
            "metadatas": [],
            "retrieved_docs": [],  # For ReasoningAgent
            "retrieved_metadata": [],  # For ReasoningAgent
            "scores": [],
            "distances": [],
            "sources": [],
            "num_results": 0,
            "retrieval_method": "hybrid",
            "error": reason
        }
