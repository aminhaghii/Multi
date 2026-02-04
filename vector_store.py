import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os
import pickle

class VectorStore:
    def __init__(self, persist_directory: str = "./faiss_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Use local cache for offline operation
        cache_dir = os.path.join(os.path.dirname(__file__), 'model_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        self.embedding_model = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2',
            cache_folder=cache_dir
        )
        self.dimension = 384
        
        self.index_path = os.path.join(persist_directory, "index.faiss")
        self.metadata_path = os.path.join(persist_directory, "metadata.pkl")
        
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                data = pickle.load(f)
                self.documents = data['documents']
                self.metadatas = data['metadatas']
                self.ids = data['ids']
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.documents = []
            self.metadatas = []
            self.ids = []
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.astype('float32')
    
    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        embeddings = np.array([self._generate_embedding(text) for text in texts])
        
        self.index.add(embeddings)
        self.documents.extend(texts)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)
        
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
