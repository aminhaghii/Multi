"""
Session API Routes
Handles chat session management endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import sys
import re as _re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.session_manager import session_manager

def sanitize_error(e: Exception, generic_msg: str = "An internal error occurred") -> str:
    """Sanitize exception messages to prevent information leakage."""
    msg = str(e)
    msg = _re.sub(r'[A-Za-z]:\\[^\s:]+', '[path]', msg)
    msg = _re.sub(r'/[^\s:]+/[^\s:]+', '[path]', msg)
    msg = _re.sub(r'line \d+', 'line [N]', msg)
    if len(msg) > 200:
        msg = msg[:200] + '...'
    sensitive = ['password', 'secret', 'key', 'token', 'credential', 'database']
    if any(p in msg.lower() for p in sensitive):
        return generic_msg
    return msg or generic_msg

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    id: str
    title: Optional[str]
    status: str
    created_at: str
    updated_at: str
    message_count: int
    rag_collection_id: str


@router.post("", response_model=Dict[str, Any])
async def create_session(request: CreateSessionRequest):
    """Create a new chat session"""
    try:
        session = session_manager.create_session(title=request.title)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.get("", response_model=Dict[str, Any])
async def list_sessions(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None
):
    """List all sessions with pagination"""
    try:
        sessions = session_manager.list_sessions(status=status, limit=limit, offset=offset)
        
        if search:
            sessions = [s for s in sessions if search.lower() in (s.get('title') or '').lower()]
        
        return {
            "sessions": sessions,
            "total": len(sessions),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_sessions(limit: int = Query(20, ge=1, le=50)):
    """Get recently active sessions"""
    try:
        return session_manager.list_sessions(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_session(session_id: str, include_messages: bool = False, limit: int = 50):
    """Get session details"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if include_messages:
            session['messages'] = session_manager.get_messages(session_id, limit=limit)
        
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.patch("/{session_id}", response_model=Dict[str, Any])
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session properties"""
    try:
        updates = request.dict(exclude_none=True)
        session = session_manager.update_session(session_id, **updates)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str, hard_delete: bool = False):
    """Delete a session"""
    try:
        success = session_manager.delete_session(session_id, hard_delete=hard_delete)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.post("/{session_id}/archive")
async def archive_session(session_id: str):
    """Archive a session"""
    try:
        success = session_manager.archive_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "message": "Session archived"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.post("/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume an archived or idle session"""
    try:
        session = session_manager.resume_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "session": session, "context_loaded": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.get("/{session_id}/messages", response_model=Dict[str, Any])
async def get_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Get messages for a session"""
    try:
        messages = session_manager.get_messages(session_id, limit=limit, offset=offset)
        return {
            "messages": messages,
            "has_more": len(messages) == limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.get("/{session_id}/summary")
async def get_session_summary(session_id: str):
    """Get session summary statistics"""
    try:
        summary = session_manager.generate_summary(session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="Session not found or no messages")
        return {"session_id": session_id, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_error(e))
