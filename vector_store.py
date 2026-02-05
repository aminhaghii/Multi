import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os
import pickle
from pathlib import Path

class VectorStore:
    def __init__(self, persist_directory: str = "./faiss_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Use local cache for offline operation
        cache_dir = os.path.join(os.path.dirname(__file__), 'model_cache')
        os.makedirs(cache_dir, exist_ok=True)

        self.embedding_model = self._load_embedding_model(cache_dir)
        self.dimension = 384
        
        self.index_path = os.path.join(persist_directory, "index.faiss")
        self.metadata_path = os.path.join(persist_directory, "metadata.pkl")
        
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data.get('documents', [])
                    self.metadatas = data.get('metadatas', [])
                    self.ids = data.get('ids', [])
                # Validate data consistency
                if len(self.documents) != self.index.ntotal:
                    print(f"Warning: Index mismatch. Rebuilding index...")
                    self._rebuild_index()
            except (pickle.UnpicklingError, EOFError, KeyError) as e:
                print(f"Warning: Corrupt data files, starting fresh: {e}")
                self._init_empty()
            except Exception as e:
                print(f"Warning: Failed to load vector store: {e}")
                self._init_empty()
        else:
            self._init_empty()
    
    def _init_empty(self):
        """Initialize empty vector store"""
        self.index = faiss.IndexFlatL2(self.dimension)
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
        self.index = faiss.IndexFlatL2(self.dimension)
        if self.documents:
            embeddings = np.array([self._generate_embedding(doc) for doc in self.documents])
            self.index.add(embeddings)
            self._save()
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.astype('float32')
    
    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
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
        
        k = min(k, len(self.documents))
        distances, indices = self.index.search(query_embedding, k)
        
        results_docs = [self.documents[i] for i in indices[0]]
        results_meta = [self.metadatas[i] for i in indices[0]]
        results_ids = [self.ids[i] for i in indices[0]]
        
        return {
            "documents": results_docs,
            "metadatas": results_meta,
            "distances": distances[0].tolist(),
            "ids": results_ids
        }
    
    def _save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'metadatas': self.metadatas,
                'ids': self.ids
            }, f)
    
    def delete_collection(self):
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.metadata_path):
            os.remove(self.metadata_path)
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.metadatas = []
        self.ids = []
    
    def get_collection_count(self) -> int:
        return len(self.documents)
    
    def delete_by_file_hash(self, file_hash: str) -> int:
        """Delete documents by file hash efficiently"""
        indices_to_keep = []
        deleted_count = 0
        
        for i, meta in enumerate(self.metadatas):
            if meta.get('file_hash') != file_hash:
                indices_to_keep.append(i)
            else:
                deleted_count += 1
        
        if deleted_count == 0:
            return 0
        
        # Rebuild with only kept documents
        self.documents = [self.documents[i] for i in indices_to_keep]
        self.metadatas = [self.metadatas[i] for i in indices_to_keep]
        self.ids = [self.ids[i] for i in indices_to_keep]
        
        # Rebuild index
        self._rebuild_index()
        
        return deleted_count
    
    def get_unique_sources(self) -> List[str]:
        """Get list of unique source files"""
        return list(set(meta.get('source', '') for meta in self.metadatas))
