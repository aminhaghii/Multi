"""
Session Manager
Handles chat session lifecycle, state management, and RAG collection initialization
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session as DBSession

from database.models import Session, Message, RAGCollection, SessionStatus, MessageRole, CollectionType
from database.connection import get_db_session


class SessionManager:
    """Manages chat sessions and their lifecycle"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, title: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat session with fresh RAG collection"""
        session_id = str(uuid.uuid4())
        rag_collection_id = f"session_{session_id}"
        
        with get_db_session() as db:
            session = Session(
                id=session_id,
                title=title or "New Chat",
                status=SessionStatus.ACTIVE.value,
                rag_collection_id=rag_collection_id,
                user_id=user_id,
                extra_data={"created_via": "session_manager"}
            )
            db.add(session)
            
            rag_collection = RAGCollection(
                id=rag_collection_id,
                session_id=session_id,
                type=CollectionType.SESSION.value,
                name=f"Session {session_id[:8]}",
                extra_data={"isolated": True}
            )
            db.add(rag_collection)
            
            result = session.to_dict()
        
        self.active_sessions[session_id] = {
            "id": session_id,
            "rag_collection_id": rag_collection_id,
            "created_at": datetime.utcnow(),
            "message_count": 0
        }
        
        return result
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details"""
        with get_db_session() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                return session.to_dict()
        return None
    
    def list_sessions(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List sessions with optional filtering"""
        with get_db_session() as db:
            query = db.query(Session)
            
            if status:
                query = query.filter(Session.status == status)
            
            query = query.filter(Session.status != SessionStatus.DELETED.value)
            query = query.order_by(Session.updated_at.desc())
            query = query.offset(offset).limit(limit)
            
            sessions = query.all()
            return [s.to_dict() for s in sessions]
    
    def update_session(self, session_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Update session properties"""
        with get_db_session() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                return None
            
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            
            session.updated_at = datetime.utcnow()
            return session.to_dict()
    
    def archive_session(self, session_id: str) -> bool:
        """Archive a session"""
        result = self.update_session(session_id, status=SessionStatus.ARCHIVED.value)
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        return result is not None
    
    def delete_session(self, session_id: str, hard_delete: bool = False) -> bool:
        """Delete a session (soft or hard)"""
        success = False
        if hard_delete:
            with get_db_session() as db:
                session = db.query(Session).filter(Session.id == session_id).first()
                if session:
                    db.delete(session)
                    success = True
        else:
            result = self.update_session(session_id, status=SessionStatus.DELETED.value)
            success = result is not None
        
        if success and session_id in self.active_sessions:
            del self.active_sessions[session_id]
        return success
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Add a message to session"""
        message_id = str(uuid.uuid4())
        
        with get_db_session() as db:
            message = Message(
                id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                extra_data=metadata or {}
            )
            db.add(message)
            
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.updated_at = datetime.utcnow()
                if not session.title or session.title == "New Chat":
                    session.title = content[:50] + "..." if len(content) > 50 else content
            
            result = message.to_dict()
        
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["message_count"] += 1
        
        return result
    
    def get_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a session"""
        with get_db_session() as db:
            messages = db.query(Message)\
                .filter(Message.session_id == session_id)\
                .order_by(Message.created_at.asc())\
                .offset(offset).limit(limit)\
                .all()
            return [m.to_dict() for m in messages]
    
    def get_session_context(self, session_id: str, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent messages formatted for LLM context"""
        messages = self.get_messages(session_id, limit=max_messages)
        return [{"role": m["role"], "content": m["content"]} for m in messages]
    
    def resume_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Resume an archived or idle session"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        self.update_session(session_id, status=SessionStatus.ACTIVE.value)
        
        self.active_sessions[session_id] = {
            "id": session_id,
            "rag_collection_id": session.get("rag_collection_id"),
            "resumed_at": datetime.utcnow(),
            "message_count": len(self.get_messages(session_id))
        }
        
        return self.get_session(session_id)
    
    def generate_summary(self, session_id: str) -> Optional[str]:
        """Generate AI summary of session (placeholder)"""
        messages = self.get_messages(session_id)
        if not messages:
            return None
        
        topics = set()
        for m in messages:
            if m["role"] == "user":
                words = m["content"].split()[:5]
                topics.add(" ".join(words))
        
        summary = f"Discussion about: {', '.join(list(topics)[:3])}"
        self.update_session(session_id, summary=summary)
        return summary


session_manager = SessionManager()
