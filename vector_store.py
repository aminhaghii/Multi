import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os
import pickle
import json
from pathlib import Path
import threading

class VectorStore:
    def __init__(self, persist_directory: str = "./faiss_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Use local cache for offline operation
        cache_dir = os.path.join(os.path.dirname(__file__), 'model_cache')
        os.makedirs(cache_dir, exist_ok=True)

        self.embedding_model = self._load_embedding_model(cache_dir)
        self.dimension = self.embedding_model.get_sentence_embedding_dimension()
        
        # Threading lock for race condition prevention (BUG-001 FIX)
        self._lock = threading.Lock()
        
        self.index_path = os.path.join(persist_directory, "index.faiss")
        self.metadata_path = os.path.join(persist_directory, "metadata.json")
        
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                # BUG-011 FIX: Use JSON instead of pickle for safe deserialization
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.documents = data.get('documents', [])
                    self.metadatas = data.get('metadatas', [])
                    self.ids = data.get('ids', [])
                # Validate data consistency
                if len(self.documents) != self.index.ntotal:
                    print(f"Warning: Index mismatch. Rebuilding index...")
                    self._rebuild_index()
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Corrupt data files, starting fresh: {e}")
                self._init_empty()
            except Exception as e:
                print(f"Warning: Failed to load vector store: {e}")
                self._init_empty()
        else:
            self._init_empty()
    
    def _init_empty(self):
        """Initialize empty vector store"""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.documents = []
        self.metadatas = []
        self.ids = []

    def _resolve_local_snapshot(self, cache_dir: str, repo_id: str) -> str:
        """Return the path to the first local snapshot of a HF repo if it exists."""
        safe_repo = repo_id.replace('/', '--')
        repo_root = Path(cache_dir) / f"models--{safe_repo}"
        snapshots_dir = repo_root / "snapshots"
        if snapshots_dir.is_dir():
            for child in snapshots_dir.iterdir():
                if child.is_dir():
                    return str(child)
        return ""

    def _load_embedding_model(self, cache_dir: str) -> SentenceTransformer:
        """Load SentenceTransformer from local cache if available to avoid network calls."""
        local_path = self._resolve_local_snapshot(cache_dir, 'sentence-transformers/all-MiniLM-L6-v2')
        if local_path:
            try:
                return SentenceTransformer(local_path)
            except Exception as exc:
                print(f"Warning: Failed to load local embedding model at {local_path}: {exc}")
        # Fallback to default behavior (may require network on first run)
        return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', cache_folder=cache_dir)
    
    def _rebuild_index(self):
        """Rebuild FAISS index from documents"""
        self.index = faiss.IndexFlatIP(self.dimension)
        if self.documents:
            embeddings = np.array([self._generate_embedding(doc) for doc in self.documents])
            faiss.normalize_L2(embeddings)
            self.index.add(embeddings)
            self._save()
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.astype('float32')
    
    def _normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """Normalize embeddings for cosine similarity with IndexFlatIP"""
        faiss.normalize_L2(embeddings)
        return embeddings
    
    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        # Phase 1: Filter duplicates under lock (fast, needs shared state)
        with self._lock:
            existing_ids = set(self.ids)
        
        new_texts = []
        new_metadatas = []
        new_ids = []
        for text, meta, doc_id in zip(texts, metadatas, ids):
            if doc_id not in existing_ids:
                new_texts.append(text)
                new_metadatas.append(meta)
                new_ids.append(doc_id)
                existing_ids.add(doc_id)
        
        if not new_texts:
            print("No new documents to add (all duplicates)")
            return
        
        # Phase 2: Generate embeddings outside lock (CPU-heavy, no shared state)
        embeddings = np.array([self._generate_embedding(text) for text in new_texts])
        faiss.normalize_L2(embeddings)
        
        # Phase 3: Add to index under lock (mutates shared state)
        with self._lock:
            # Re-check for duplicates added by concurrent calls during embedding
            final_texts = []
            final_metadatas = []
            final_ids = []
            final_embeddings = []
            current_ids = set(self.ids)
            for i, doc_id in enumerate(new_ids):
                if doc_id not in current_ids:
                    final_texts.append(new_texts[i])
                    final_metadatas.append(new_metadatas[i])
                    final_ids.append(doc_id)
                    final_embeddings.append(embeddings[i])
                    current_ids.add(doc_id)
            
            if not final_texts:
                print("No new documents to add (all duplicates after re-check)")
                return
            
            final_emb_array = np.array(final_embeddings)
            self.index.add(final_emb_array)
            self.documents.extend(final_texts)
            self.metadatas.extend(final_metadatas)
            self.ids.extend(final_ids)
            
            self._save()
    
    def search(self, query: str, k: int = 5) -> Dict[str, Any]:
        # Generate embedding outside the lock (CPU-bound, doesn't need shared state)
        query_embedding = self._generate_embedding(query).reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
        with self._lock:
            if len(self.documents) == 0:
                return {
                    "documents": [],
                    "metadatas": [],
                    "distances": [],
                    "ids": []
                }
            
            k = min(k, len(self.documents))
            distances, indices = self.index.search(query_embedding, k)
            
            # Filter out invalid indices (-1 returned by FAISS when fewer results than k)
            results_docs = []
            results_meta = []
            results_ids = []
            results_distances = []
            
            for idx, dist in zip(indices[0], distances[0]):
                if idx >= 0 and idx < len(self.documents):
                    results_docs.append(self.documents[idx])
                    results_meta.append(self.metadatas[idx])
                    results_ids.append(self.ids[idx])
                    results_distances.append(float(dist))
        
            return {
                "documents": results_docs,
                "metadatas": results_meta,
                "distances": results_distances,
                "ids": results_ids
            }
    
    def _save(self):
        """Save index and metadata - BUG-011 FIX: Use JSON for safe serialization"""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump({
                'documents': self.documents,
                'metadatas': self.metadatas,
                'ids': self.ids
            }, f, ensure_ascii=False, indent=2)
    
    def delete_collection(self):
        with self._lock:
            if os.path.exists(self.index_path):
                os.remove(self.index_path)
            if os.path.exists(self.metadata_path):
                os.remove(self.metadata_path)
            self.index = faiss.IndexFlatIP(self.dimension)
            self.documents = []
            self.metadatas = []
            self.ids = []
    
    def get_collection_count(self) -> int:
        with self._lock:
            return len(self.documents)
    
    def get_stats(self) -> Dict[str, Any]:
        """Return thread-safe snapshot of vector store statistics."""
        with self._lock:
            doc_count = len(set(m.get('source', '') for m in self.metadatas))
            chunk_count = len(self.documents)
        return {"document_count": doc_count, "chunk_count": chunk_count}
    
<<<<<<< C:/Users/aminh/OneDrive/Desktop/Multi_agent/vector_store.py
=======
    def get_snapshot(self) -> Dict[str, list]:
        """Return a thread-safe shallow copy of documents and metadatas."""
        with self._lock:
            return {
                "documents": list(self.documents),
                "metadatas": list(self.metadatas),
                "ids": list(self.ids)
            }
    
>>>>>>> C:/Users/aminh/.windsurf/worktrees/Multi_agent/Multi_agent-7a8feee4/vector_store.py
    def delete_by_file_hash(self, file_hash: str) -> int:
        """Delete documents by file hash efficiently with atomic operation (BUG-008 FIX)"""
        with self._lock:
            indices_to_keep = []
            deleted_count = 0
            
            for i, meta in enumerate(self.metadatas):
                if meta.get('file_hash') != file_hash:
                    indices_to_keep.append(i)
                else:
                    deleted_count += 1
            
            if deleted_count == 0:
                return 0
            
            # Create backup before modification (atomic operation)
            old_documents = self.documents.copy()
            old_metadatas = self.metadatas.copy()
            old_ids = self.ids.copy()
            
            try:
                # Rebuild with only kept documents
                self.documents = [self.documents[i] for i in indices_to_keep]
                self.metadatas = [self.metadatas[i] for i in indices_to_keep]
                self.ids = [self.ids[i] for i in indices_to_keep]
                
                # Rebuild index
                self._rebuild_index()
                
                return deleted_count
            except Exception as e:
                # Rollback on failure (BUG-008 FIX)
                print(f"Error during delete, rolling back: {e}")
                self.documents = old_documents
                self.metadatas = old_metadatas
                self.ids = old_ids
                self._rebuild_index()
                return 0
    
    def get_unique_sources(self) -> List[str]:
        """Get list of unique source files"""
        with self._lock:
            return list(set(meta.get('source', '') for meta in self.metadatas))
