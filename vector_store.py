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
        with self._lock:
            # Filter out duplicates by ID
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
            
            embeddings = np.array([self._generate_embedding(text) for text in new_texts])
            faiss.normalize_L2(embeddings)
            
            self.index.add(embeddings)
            self.documents.extend(new_texts)
            self.metadatas.extend(new_metadatas)
            self.ids.extend(new_ids)
            
            self._save()
    
    def search(self, query: str, k: int = 5) -> Dict[str, Any]:
        if len(self.documents) == 0:
            return {
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": []
            }
        
        query_embedding = self._generate_embedding(query).reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
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
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.metadata_path):
            os.remove(self.metadata_path)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.documents = []
        self.metadatas = []
        self.ids = []
    
    def get_collection_count(self) -> int:
        return len(self.documents)
    
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
        return list(set(meta.get('source', '') for meta in self.metadatas))
