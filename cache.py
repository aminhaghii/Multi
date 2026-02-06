import sqlite3
import hashlib
import json
import time
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

class ResponseCache:
    """SQLite-based cache for RAG responses with intelligent invalidation"""
    
    def __init__(self, db_path: str = "./cache/responses.db"):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure the cache DB file and schema exist (handles manual deletions)."""
        db_exists = os.path.exists(self.db_path)
        if not db_exists:
            self._init_db()
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='cached_responses'"
                )
                if cursor.fetchone() is None:
                    self._init_db()
        except sqlite3.OperationalError:
            self._init_db()

    def _init_db(self):
        """Initialize SQLite database with proper schema"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    user_query TEXT NOT NULL,
                    response_data TEXT NOT NULL,  -- JSON serialized response
                    kb_hash TEXT NOT NULL,        -- Hash of knowledge base state
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    ttl_hours INTEGER DEFAULT 24
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_hash 
                ON cached_responses(query_hash)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_hash 
                ON cached_responses(kb_hash)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON cached_responses(created_at)
            """)
            
            conn.commit()
    
    def _generate_query_hash(self, user_query: str) -> str:
        """Generate consistent hash for query"""
        normalized_query = user_query.strip().lower()
        return hashlib.sha256(normalized_query.encode()).hexdigest()
    
    def set_vector_store(self, vector_store):
        """Set the vector store reference to avoid re-creating it on every call"""
        self._vector_store = vector_store

    def _generate_kb_hash(self, vector_store=None) -> str:
        """Generate hash representing current knowledge base state"""
        try:
            # Use passed vector_store, cached reference, or fallback
            vs = vector_store or getattr(self, '_vector_store', None)
            if vs is None:
                # Lightweight check: just use file existence and size
                try:
                    index_path = "./faiss_db/index.faiss"
                    if os.path.exists(index_path):
                        file_size = os.path.getsize(index_path)
                        meta_path = "./faiss_db/metadata.json"
                        meta_size = os.path.getsize(meta_path) if os.path.exists(meta_path) else 0
                        kb_state = f"file_{file_size}_{meta_size}"
                        return hashlib.md5(kb_state.encode()).hexdigest()
                    else:
                        return hashlib.md5("empty_kb".encode()).hexdigest()
                except Exception:
                    return hashlib.md5("fallback_kb_state".encode()).hexdigest()
            
            # Simple hash based on document count and total chunks
            doc_count = len(set(meta.get('source', '') for meta in vs.metadatas))
            chunk_count = len(vs.documents)
            
            kb_state = f"{doc_count}_{chunk_count}_{len(vs.ids)}"
            return hashlib.md5(kb_state.encode()).hexdigest()
        except Exception:
            # Fallback if vector store not available
            return hashlib.md5("fallback_kb_state".encode()).hexdigest()
    
    def get(self, user_query: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if valid and not expired"""
        self._ensure_db()
        query_hash = self._generate_query_hash(user_query)
        current_kb_hash = self._generate_kb_hash()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT response_data, created_at, ttl_hours, access_count
                FROM cached_responses 
                WHERE query_hash = ? AND kb_hash = ?
            """, (query_hash, current_kb_hash))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            response_data, created_at, ttl_hours, access_count = row
            
            # Check if expired - use naive datetime comparison
            try:
                # Handle various datetime formats from SQLite
                created_at_clean = created_at.replace('Z', '').replace('+00:00', '')
                created_time = datetime.fromisoformat(created_at_clean)
            except ValueError:
                # Fallback: treat as expired if can't parse
                cursor.execute("DELETE FROM cached_responses WHERE query_hash = ?", (query_hash,))
                conn.commit()
                return None
            
            expiry_time = created_time + timedelta(hours=ttl_hours)
            
            if datetime.now() > expiry_time:
                # Delete expired entry
                cursor.execute("DELETE FROM cached_responses WHERE query_hash = ?", (query_hash,))
                conn.commit()
                return None
            
            # Update access statistics
            cursor.execute("""
                UPDATE cached_responses 
                SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                WHERE query_hash = ?
            """, (query_hash,))
            conn.commit()
            
            return json.loads(response_data)
    
    def set(self, user_query: str, response_data: Dict[str, Any], ttl_hours: int = 24):
        """Cache a successful response"""
        self._ensure_db()
        query_hash = self._generate_query_hash(user_query)
        kb_hash = self._generate_kb_hash()
        
        # Only cache successful responses
        if not response_data.get('success', False):
            return
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cached_responses 
                (query_hash, user_query, response_data, kb_hash, ttl_hours)
                VALUES (?, ?, ?, ?, ?)
            """, (
                query_hash,
                user_query,
                json.dumps(response_data),
                kb_hash,
                ttl_hours
            ))
            conn.commit()
    
    def invalidate_by_kb(self):
        """Invalidate all cached responses when knowledge base changes"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get current KB hash
            current_kb_hash = self._generate_kb_hash()
            
            # Delete all entries with different KB hash
            cursor.execute("""
                DELETE FROM cached_responses 
                WHERE kb_hash != ?
            """, (current_kb_hash,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"🗑️ Cache: Invalidated {deleted_count} entries due to KB changes")
            return deleted_count
    
    def clear_all(self):
        """Clear all cached responses"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cached_responses")
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"🗑️ Cache: Cleared all {deleted_count} entries")
            return deleted_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total entries
            cursor.execute("SELECT COUNT(*) FROM cached_responses")
            total_entries = cursor.fetchone()[0]
            
            # Entries accessed more than once
            cursor.execute("SELECT COUNT(*) FROM cached_responses WHERE access_count > 1")
            reused_entries = cursor.fetchone()[0]
            
            # Average access count
            cursor.execute("SELECT AVG(access_count) FROM cached_responses")
            avg_access = cursor.fetchone()[0] or 0
            
            # Oldest entry
            cursor.execute("SELECT MIN(created_at) FROM cached_responses")
            oldest = cursor.fetchone()[0]
            
            return {
                "total_entries": total_entries,
                "reused_entries": reused_entries,
                "reuse_rate": (reused_entries / total_entries * 100) if total_entries > 0 else 0,
                "avg_access_count": round(avg_access, 2),
                "oldest_entry": oldest
            }
    
    def cleanup_expired(self):
        """Remove expired entries"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM cached_responses 
                WHERE created_at < datetime('now', '-' || ttl_hours || ' hours')
            """)
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                print(f"🗑️ Cache: Cleaned up {deleted_count} expired entries")
            
            return deleted_count

# Global cache instance
_cache_instance = None

def get_cache() -> ResponseCache:
    """Get or create global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ResponseCache()
    return _cache_instance
