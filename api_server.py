import os
os.environ["TRANSFORMERS_NO_TF"] = "1"

import faiss
import numpy as np
import hashlib

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import shutil
import json
from threading import Thread

from main_engine import Orchestrator
from llm_client import LLMClient
from vector_store import VectorStore
from cache import get_cache
from ingestion import DocumentProcessor
from export_utils import export_chat

try:
    from core.session_manager import session_manager
    from database.connection import init_database
    init_database()  # Ensure DB tables exist before any session operations
    SESSION_SUPPORT = True
except ImportError as e:
    print(f"Warning: Session support not available: {e}")
    SESSION_SUPPORT = False
    session_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize on startup, cleanup on shutdown."""
    global llm_client, vector_store, processor, orchestrator, image_captioner, voice_transcriber, cache

    llm_client = LLMClient(base_url="http://127.0.0.1:8080")
    vector_store = VectorStore(persist_directory="./faiss_db")
    processor = DocumentProcessor(vector_store, chunk_size=800, chunk_overlap=160)
    cache = get_cache()
    cache.set_vector_store(vector_store)

    try:
        from image_captioner import ImageCaptioner
        image_captioner = ImageCaptioner()
    except Exception as e:
        print(f"Warning: Could not load image captioner: {e}")
        image_captioner = None

    try:
        from voice_transcriber import VoiceTranscriber
        voice_transcriber = VoiceTranscriber(model_size="tiny")
    except Exception as e:
        print(f"Warning: Could not load voice transcriber: {e}")
        voice_transcriber = None

    orchestrator = Orchestrator(
        llm_client=llm_client,
        vector_store=vector_store,
        image_captioner=image_captioner,
        max_refinement_iterations=2,
        confidence_threshold=0.7
    )

    yield  # Application runs here

    # Shutdown cleanup (if needed in the future)


app = FastAPI(title="Agentic Research Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_client = None
vector_store = None
processor = None
orchestrator = None
image_captioner = None
voice_transcriber = None
cache = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # For chat history persistence

class ImageInfo(BaseModel):
    path: str
    source: str
    page: int

class ExportRequest(BaseModel):
    chat_history: List[dict]
    format: str = 'markdown'

class ArtifactInfo(BaseModel):
    title: str
    type: str
    content: str

class ChatResponse(BaseModel):
    success: bool
    answer: str
    confidence: float
    verified: bool
    iterations: int
    sources: int
    logs: List[dict] = []
    error: Optional[str] = None
    image_paths: List[ImageInfo] = []  # Images referenced in the answer
    artifact: Optional[ArtifactInfo] = None  # Artifact for Canvas panel

class KBStats(BaseModel):
    document_count: int
    llm_status: bool
    multimodal_status: bool

class DocumentNode(BaseModel):
    id: str
    name: str
    type: str
    metadata: dict

@app.get("/api/health")
async def health():
    llm_status = llm_client.health_check()
    multimodal_status = llm_client.multimodal_health_check()
    
    return {
        "status": "ok" if llm_status else "degraded",
        "llm_available": llm_status,
        "multimodal_available": multimodal_status
    }

@app.get("/api/health/detailed")
async def detailed_health():
    """Detailed health check with all system components"""
    from datetime import datetime
    
    # Get vector store stats (snapshot under lock)
    try:
        with vector_store._lock:
            snap_metas = list(vector_store.metadatas)
            chunk_count = len(vector_store.documents)
        vs_stats = {
            "document_count": len(set(m.get('source', '') for m in snap_metas)),
            "chunk_count": chunk_count
        }
    except Exception:
        vs_stats = {"document_count": 0, "chunk_count": 0}
    
    # Get cache stats
    try:
        cache_stats = cache.get_stats()
    except Exception:
        cache_stats = {"total_entries": 0, "reuse_rate": 0}
    
    return {
        "llm_status": llm_client.health_check(),
        "multimodal_status": llm_client.multimodal_health_check(),
        "image_captioner_available": image_captioner is not None,
        "vector_store": vs_stats,
        "cache": cache_stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stats", response_model=KBStats)
async def get_stats():
    return KBStats(
        document_count=vector_store.get_collection_count(),
        llm_status=llm_client.health_check(),
        multimodal_status=llm_client.multimodal_health_check()
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    if not llm_client.health_check():
        return ChatResponse(
            success=False,
            answer="",
            confidence=0,
            verified=False,
            iterations=0,
            sources=0,
            error="LLM Server is offline"
        )
    
    # CHAT PERSISTENCE FIX: Save user message to database
    if SESSION_SUPPORT and request.session_id:
        try:
            session_manager.add_message(
                session_id=request.session_id,
                role="user",
                content=request.message
            )
        except Exception as e:
            print(f"Warning: Failed to save user message: {e}")
    
    try:
        result = orchestrator.run_query(request.message)
        
        if result['success']:
            # CHAT PERSISTENCE FIX: Save assistant response to database
            if SESSION_SUPPORT and request.session_id:
                try:
                    session_manager.add_message(
                        session_id=request.session_id,
                        role="assistant",
                        content=result['answer'],
                        metadata={
                            "confidence": result.get('confidence'),
                            "verified": result.get('verified'),
                            "sources": result.get('num_sources'),
                            "iterations": result.get('num_iterations')
                        }
                    )
                except Exception as e:
                    print(f"Warning: Failed to save assistant message: {e}")
            
            # Get image_paths directly from response
            image_paths = []
            raw_image_paths = result.get('image_paths', [])
            if raw_image_paths:
                image_paths = [
                    ImageInfo(path=img.get('path', ''), source=img.get('source', ''), page=img.get('page', 0))
                    for img in raw_image_paths
                ]
            
            # Get artifact info if present
            artifact_data = result.get('artifact')
            artifact = None
            if artifact_data:
                artifact = ArtifactInfo(
                    title=artifact_data.get('title', 'Artifact'),
                    type=artifact_data.get('type', 'document'),
                    content=artifact_data.get('content', '')
                )
            
            return ChatResponse(
                success=True,
                answer=result['answer'],
                confidence=result['confidence'],
                verified=result['verified'],
                iterations=result['num_iterations'],
                sources=result['num_sources'],
                logs=result.get('execution_log', []),
                image_paths=image_paths,
                artifact=artifact
            )
        else:
            return ChatResponse(
                success=False,
                answer="",
                confidence=0,
                verified=False,
                iterations=0,
                sources=0,
                logs=result.get('execution_log', []),
                error=result.get('error', 'Unknown error')
            )
    except Exception as e:
        return ChatResponse(
            success=False,
            answer="",
            confidence=0,
            verified=False,
            iterations=0,
            sources=0,
            error=str(e)
        )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not llm_client.health_check():
        raise HTTPException(status_code=503, detail="LLM Server is offline")

    # CHAT PERSISTENCE FIX: Save user message to database at start of stream
    if SESSION_SUPPORT and request.session_id:
        try:
            session_manager.add_message(
                session_id=request.session_id,
                role="user",
                content=request.message
            )
        except Exception as e:
            print(f"Warning: Failed to save user message in stream: {e}")

    import asyncio

    async def event_generator():
        loop = asyncio.get_running_loop()
        async_queue: asyncio.Queue = asyncio.Queue()
        
        def progress_callback(event):
            loop.call_soon_threadsafe(async_queue.put_nowait, {"type": "progress", "payload": event})

        def worker():
            try:
                result = orchestrator.run_query(
                    request.message,
                    progress_callback=progress_callback,
                    use_cache=False
                )

                if result.get('success'):
                    image_paths = []
                    raw_image_paths = result.get('image_paths', [])
                    if raw_image_paths:
                        image_paths = [
                            {"path": img.get('path', ''), "source": img.get('source', ''), "page": img.get('page', 0)}
                            for img in raw_image_paths
                        ]

                    artifact_data = result.get('artifact')
                    artifact = None
                    if artifact_data:
                        artifact = {
                            "title": artifact_data.get('title', 'Artifact'),
                            "type": artifact_data.get('type', 'document'),
                            "content": artifact_data.get('content', '')
                        }

                    payload = {
                        "success": True,
                        "answer": result.get('answer', ''),
                        "confidence": result.get('confidence', 0),
                        "verified": result.get('verified', False),
                        "iterations": result.get('num_iterations', 0),
                        "sources": result.get('num_sources', 0),
                        "logs": result.get('execution_log', []),
                        "image_paths": image_paths,
                        "artifact": artifact
                    }
                else:
                    payload = {
                        "success": False,
                        "error": result.get('error', 'Unknown error'),
                        "logs": result.get('execution_log', [])
                    }

                loop.call_soon_threadsafe(async_queue.put_nowait, {"type": "final", "payload": payload})
                
                # CHAT PERSISTENCE FIX: Save assistant response to database
                if SESSION_SUPPORT and request.session_id and result.get('success'):
                    try:
                        session_manager.add_message(
                            session_id=request.session_id,
                            role="assistant",
                            content=result.get('answer', ''),
                            metadata={
                                "confidence": result.get('confidence'),
                                "verified": result.get('verified'),
                                "sources": result.get('num_sources'),
                                "iterations": result.get('num_iterations')
                            }
                        )
                    except Exception as e:
                        print(f"Warning: Failed to save assistant message in stream: {e}")
            except Exception as exc:
                loop.call_soon_threadsafe(async_queue.put_nowait, {"type": "error", "payload": {"error": str(exc)}})
            finally:
                loop.call_soon_threadsafe(async_queue.put_nowait, {"type": "done"})

        Thread(target=worker, daemon=True).start()

        while True:
            event = await async_queue.get()
            if event["type"] == "done":
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    os.makedirs("./data", exist_ok=True)
    
    # Sanitize filename to prevent path traversal
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in '._-')
    if not safe_filename.endswith('.pdf'):
        safe_filename += '.pdf'
    file_path = f"./data/{safe_filename}"
    
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    try:
        result = processor.process_pdf(file_path)
        # Invalidate cache when new document is uploaded
        cache.invalidate_by_kb()
        return {
            "success": True,
            "message": f"Processed {result['num_chunks']} chunks from {result['num_pages']} pages",
            "chunks": result['num_chunks'],
            "pages": result['num_pages']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


MAX_FILE_SIZE_MB = 50  # Maximum file size in MB

@app.post("/api/upload/document")
async def upload_document(file: UploadFile = File(...)):
    allowed_extensions = ['.pdf', '.docx', '.doc', '.md', '.txt', '.rtf']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Unsupported document type")

    os.makedirs("./data", exist_ok=True)
    
    # Read content and check size
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
    
    # Sanitize filename
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in '._-')
    file_path = f"./data/{safe_filename}"

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext == '.pdf':
            result = processor.process_pdf(file_path)
            message = f"Processed {result['num_chunks']} chunks from {result['num_pages']} pages"
        elif ext in ['.docx', '.doc']:
            result = processor.process_word(file_path)
            message = f"Processed {result['num_chunks']} chunks from Word document"
        elif ext == '.md':
            result = processor.process_markdown(file_path)
            message = f"Processed {result['num_chunks']} chunks from Markdown file"
        elif ext == '.txt':
            result = processor.process_text(file_path)
            message = f"Processed {result['num_chunks']} chunks from Text file"
        elif ext == '.rtf':
            result = processor.process_rtf(file_path)
            message = f"Processed {result['num_chunks']} chunks from RTF file"
        else:
            raise HTTPException(status_code=400, detail="Unsupported document type")

        cache.invalidate_by_kb()
        return {
            "success": True,
            "message": message,
            "chunks": result.get('num_chunks', 0),
            "pages": result.get('num_pages', 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    allowed_extensions = ['.png', '.jpg', '.jpeg']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG files are allowed")
    
    os.makedirs("./data", exist_ok=True)
    
    # Read content and check size (BUG-005 FIX)
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
    
    # Sanitize filename
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in '._-')
    file_path = f"./data/{safe_filename}"
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    try:
        if image_captioner is None:
            raise HTTPException(status_code=500, detail="Image captioner not available. Server may still be loading.")
        caption = image_captioner.caption_image(file_path)
        
        text_with_caption = (
            f"[Uploaded Image] File: {file.filename}\n"
            f"Type: image photo picture\n"
            f"Caption: {caption}\n"
            f"Description: This image shows {caption}. "
            f"The uploaded photo contains visual content described as: {caption}."
        )
        
        file_hash = hashlib.sha256(content).hexdigest()[:8]
        
        metadata = {
            "source": file_path,
            "page": 0,
            "chunk_index": 0,
            "file_hash": file_hash,
            "images": file_path,
            "has_image": True,
            "image_path": file_path,
            "caption": caption
        }
        
        vector_store.add_documents([text_with_caption], [metadata], [file_hash])
        
        # Invalidate cache when new image is uploaded
        cache.invalidate_by_kb()
        
        return {
            "success": True,
            "message": f"Image processed with caption: {caption[:100]}...",
            "caption": caption
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/audio")
async def upload_audio(file: UploadFile = File(...)):
    allowed_extensions = ['.wav', '.mp3', '.m4a', '.ogg']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Only WAV, MP3, M4A, OGG files are allowed")
    
    os.makedirs("./data", exist_ok=True)
    
    # Read content and check size (BUG-005 FIX)
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
    
    # Sanitize filename
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in '._-')
    file_path = f"./data/{safe_filename}"
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    try:
        if voice_transcriber is None:
            raise HTTPException(status_code=500, detail="Voice transcriber not available. Server may still be loading.")
        transcription = voice_transcriber.transcribe(file_path)
        
        if transcription.startswith("Error"):
            raise HTTPException(status_code=500, detail=transcription)
        
        text_with_transcription = (
            f"[Uploaded Audio] File: {file.filename}\n"
            f"Type: audio voice sound recording\n"
            f"Transcription: {transcription}\n"
            f"Content: The audio recording says: {transcription}"
        )
        
        file_hash = hashlib.sha256(content).hexdigest()[:8]
        
        metadata = {
            "source": file_path,
            "page": 0,
            "chunk_index": 0,
            "file_hash": file_hash,
            "images": "",
            "has_image": False,
            "image_path": "",
            "caption": ""
        }
        
        vector_store.add_documents([text_with_transcription], [metadata], [file_hash])
        
        # Invalidate cache when new audio is uploaded
        cache.invalidate_by_kb()
        
        return {
            "success": True,
            "message": f"Audio transcribed and saved: {transcription[:100]}...",
            "transcription": transcription
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/cache/clear")
async def clear_cache():
    try:
        cache.clear_all()
        return {"success": True, "message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/kb/clear")
async def clear_kb():
    try:
        if os.path.exists("./faiss_db"):
            shutil.rmtree("./faiss_db")
        
        global vector_store
        vector_store = VectorStore(persist_directory="./faiss_db")
        
        global processor
        processor = DocumentProcessor(vector_store, chunk_size=800, chunk_overlap=160)
        
        # CRITICAL: Update orchestrator's vector store reference
        if orchestrator:
            orchestrator.update_vector_store(vector_store)
        
        # Update cache's vector store reference for correct KB hash calculations
        cache.set_vector_store(vector_store)
        
        # Clear all cache entries when KB is cleared
        cache.clear_all()
        
        return {"success": True, "message": "Knowledge base cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/list")
async def get_documents_list():
    try:
        # Snapshot under lock to avoid race conditions with concurrent uploads/deletes
        with vector_store._lock:
            snap_documents = list(vector_store.documents)
            snap_metadatas = list(vector_store.metadatas)
        
        docs_map = {}
        total_size = 0
        
        for idx, metadata in enumerate(snap_metadatas):
            source = metadata.get('source', 'unknown')
            file_hash = metadata.get('file_hash', 'unknown')
            images = metadata.get('images', '')
            
            if source not in docs_map:
                file_type = 'pdf' if source.endswith('.pdf') else 'image' if any(source.endswith(ext) for ext in ['.png', '.jpg', '.jpeg']) else 'audio' if any(source.endswith(ext) for ext in ['.wav', '.mp3', '.m4a', '.ogg']) else 'document'
                
                file_size = 0
                if os.path.exists(source):
                    file_size = os.path.getsize(source)
                
                docs_map[source] = {
                    "id": file_hash,
                    "name": os.path.basename(source),
                    "type": file_type,
                    "path": source,
                    "chunks": 0,
                    "images": 0,
                    "size": file_size
                }
            
            docs_map[source]["chunks"] += 1
            if images:
                docs_map[source]["images"] += len([x for x in images.split(',') if x.strip()])
            
            if idx < len(snap_documents):
                total_size += len(snap_documents[idx].encode('utf-8'))
        
        return {
            "documents": list(docs_map.values()),
            "storage_bytes": total_size
        }
    except Exception as e:
        return {"documents": [], "storage_bytes": 0, "error": str(e)}

@app.delete("/api/documents/{file_hash}")
async def delete_document(file_hash: str):
    try:
        # Use the efficient delete method
        deleted_count = vector_store.delete_by_file_hash(file_hash)
        
        if deleted_count == 0:
            return {"success": False, "error": "Document not found"}
        
        # Invalidate cache after deletion
        cache.invalidate_by_kb()
        
        return {"success": True, "message": f"Deleted {deleted_count} chunks"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/documents/graph")
async def get_documents_graph():
    try:
        # Snapshot under lock to avoid race conditions
        with vector_store._lock:
            snap_documents = list(vector_store.documents)
            snap_metadatas = list(vector_store.metadatas)
        
        root = {
            "name": "Knowledge Base",
            "type": "root",
            "children": []
        }
        
        doc_map = {}
        
        for idx, metadata in enumerate(snap_metadatas):
            source = metadata.get('source', 'unknown')
            file_hash = metadata.get('file_hash', 'unknown')
            page = metadata.get('page', 0)
            chunk_idx = metadata.get('chunk_index', 0)
            images = metadata.get('images', '')
            
            if source not in doc_map:
                file_type = 'pdf' if source.endswith('.pdf') else 'image' if any(source.endswith(ext) for ext in ['.png', '.jpg', '.jpeg']) else 'audio' if any(source.endswith(ext) for ext in ['.wav', '.mp3', '.m4a', '.ogg']) else 'document'
                
                doc_map[source] = {
                    "name": os.path.basename(source),
                    "type": file_type,
                    "id": file_hash,
                    "children": []
                }
                root["children"].append(doc_map[source])
            
            doc_text = snap_documents[idx] if idx < len(snap_documents) else ""
            chunk_node = {
                "name": f"Chunk {chunk_idx} (Page {page})",
                "type": "chunk",
                "id": f"{file_hash}_chunk_{idx}",
                "text": doc_text[:100] + "..." if len(doc_text) > 100 else doc_text,
                "children": []
            }
            
            if images:
                for img_path in images.split(','):
                    img_path = img_path.strip()
                    if img_path:
                        chunk_node["children"].append({
                            "name": os.path.basename(img_path),
                            "type": "image",
                            "id": f"{file_hash}_img_{os.path.basename(img_path)}",
                            "path": img_path
                        })
            
            doc_map[source]["children"].append(chunk_node)
        
        return {"tree": root}
    except Exception as e:
        return {"tree": {"name": "Error", "children": []}, "error": str(e)}

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None

@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest = None):
    """Create a new chat session"""
    title = request.title if request else None
    if not SESSION_SUPPORT:
        return {"id": f"temp_{id(title)}", "title": title or "New Chat", "message": "Session support not available"}
    try:
        session = session_manager.create_session(title=title)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/recent")
async def get_recent_sessions(limit: int = 20):
    """Get recently active sessions"""
    if not SESSION_SUPPORT:
        return []
    try:
        return session_manager.list_sessions(limit=limit)
    except Exception as e:
        return []

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, include_messages: bool = False):
    """Get session details"""
    if not SESSION_SUPPORT:
        return {"id": session_id, "title": "Session", "messages": [], "message_count": 0}
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if include_messages:
            session['messages'] = session_manager.get_messages(session_id)
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session"""
    if not SESSION_SUPPORT:
        return {"success": True, "message": "Session deleted (session support disabled)"}
    try:
        success = session_manager.delete_session(session_id)
        if success:
            return {"success": True, "message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export")
async def export_history(request: ExportRequest):
    """Export chat history to specified format"""
    try:
        file_path = export_chat(
            chat_history=request.chat_history,
            format=request.format,
            output_dir='./exports'
        )
        
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type='application/octet-stream'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/favicon.ico")
async def favicon():
    return {"status": "no favicon"}

app.mount("/static", StaticFiles(directory="static"), name="static")
# SECURITY: /data directory no longer served as static files to prevent unauthorized access to uploads

# Register agent-space routes (tool execution, capabilities)
try:
    from api.routes.agent_space import router as agent_space_router
    app.include_router(agent_space_router)
except ImportError as e:
    print(f"Warning: Agent space routes not available: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
