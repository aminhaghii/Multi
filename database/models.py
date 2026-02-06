"""
Database Models for Agentic Research Assistant
Implements: Sessions, Messages, AgentActions, MiniApps, RAGCollections, Documents
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

Base = declarative_base()


class SessionStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AppStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AppCreator(str, Enum):
    AGENT = "agent"
    USER = "user"


class CollectionType(str, Enum):
    SESSION = "session"
    GLOBAL = "global"
    DOCUMENT = "document"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def generate_uuid():
    return str(uuid.uuid4())


class Session(Base):
    """Chat session with RAG collection"""
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    title = Column(String(255), nullable=True)
    status = Column(String(20), default=SessionStatus.ACTIVE.value)
    extra_data = Column(JSON, default=dict)
    rag_collection_id = Column(String(36), unique=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True)
    is_public = Column(Boolean, default=True)
    tags = Column(JSON, default=list)
    summary = Column(Text, nullable=True)
    
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    agent_actions = relationship("AgentAction", back_populates="session", cascade="all, delete-orphan")
    rag_collection = relationship("RAGCollection", back_populates="session", uselist=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "title": self.title,
            "status": self.status,
            "metadata": self.extra_data,
            "rag_collection_id": self.rag_collection_id,
            "user_id": self.user_id,
            "is_public": self.is_public,
            "tags": self.tags,
            "summary": self.summary,
            "message_count": len(self.messages) if self.messages else 0
        }


class Message(Base):
    """Chat message with metadata"""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), default=MessageRole.USER.value)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, default=dict)
    parent_id = Column(String(36), ForeignKey("messages.id"), nullable=True)
    vector_id = Column(String(36), nullable=True)
    tokens_used = Column(Integer, default=0)
    
    session = relationship("Session", back_populates="messages")
    agent_actions = relationship("AgentAction", back_populates="message")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.extra_data,
            "parent_id": self.parent_id,
            "vector_id": self.vector_id,
            "tokens_used": self.tokens_used
        }


class AgentAction(Base):
    """Agent execution log"""
    __tablename__ = "agent_actions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=True)
    agent_type = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False)
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    status = Column(String(20), default=ActionStatus.PENDING.value)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    resources_used = Column(JSON, default=dict)
    
    session = relationship("Session", back_populates="agent_actions")
    message = relationship("Message", back_populates="agent_actions")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "agent_type": self.agent_type,
            "action_type": self.action_type,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "resources_used": self.resources_used
        }


class MiniApp(Base):
    """Mini application created by agent or user"""
    __tablename__ = "mini_apps"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    creator = Column(String(20), default=AppCreator.AGENT.value)
    code = Column(Text, nullable=True)
    config = Column(JSON, default=dict)
    dependencies = Column(JSON, default=list)
    status = Column(String(20), default=AppStatus.DRAFT.value)
    execution_count = Column(Integer, default=0)
    category = Column(String(50), nullable=True)
    icon = Column(String(50), nullable=True)
    permissions_required = Column(JSON, default=list)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "creator": self.creator,
            "config": self.config,
            "dependencies": self.dependencies,
            "status": self.status,
            "execution_count": self.execution_count,
            "category": self.category,
            "icon": self.icon,
            "permissions_required": self.permissions_required
        }


class RAGCollection(Base):
    """RAG vector collection metadata"""
    __tablename__ = "rag_collections"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=True)
    type = Column(String(20), default=CollectionType.SESSION.value)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    embedding_model = Column(String(100), default="all-MiniLM-L6-v2")
    extra_data = Column(JSON, default=dict)
    
    session = relationship("Session", back_populates="rag_collection")
    documents = relationship("Document", back_populates="collection", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "type": self.type,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "embedding_model": self.embedding_model,
            "metadata": self.extra_data
        }


class Document(Base):
    """Uploaded document metadata"""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    collection_id = Column(String(36), ForeignKey("rag_collections.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default=DocumentStatus.PENDING.value)
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    extra_data = Column(JSON, default=dict)
    
    collection = relationship("RAGCollection", back_populates="documents")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "metadata": self.extra_data
        }
