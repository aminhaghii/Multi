🎯 راهکار: اضافه کردن Task Progress به UI موجود
قسمت 1: Backend Changes
1.1 اضافه کردن WebSocket Support (api_server.py)
python
# در ابتدای api_server.py بعد از imports:
from fastapi import WebSocket, WebSocketDisconnect
import asyncio

# WebSocket Manager
class TaskProgressManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[session_id] = websocket
        print(f"✅ Task tracking connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.connections:
            del self.connections[session_id]
    
    async def send_update(self, session_id: str, update: dict):
        if session_id in self.connections:
            try:
                await self.connections[session_id].send_json(update)
            except:
                self.disconnect(session_id)

progress_manager = TaskProgressManager()

# اضافه کردن WebSocket endpoint
@app.websocket("/ws/progress/{session_id}")
async def progress_websocket(websocket: WebSocket, session_id: str):
    await progress_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        progress_manager.disconnect(session_id)
1.2 Update main_engine.py Orchestrator
python
# در main_engine.py داخل کلاس Orchestrator:

async def emit_progress(self, phase: str, subtask: str, status: str, details: dict = None):
    """Emit progress update via WebSocket"""
    from api_server import progress_manager
    
    update = {
        "phase": phase,
        "subtask": subtask,
        "status": status,  # 'running', 'completed', 'failed'
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    }
    
    if hasattr(self, 'session_id') and self.session_id:
        await progress_manager.send_update(self.session_id, update)
    
    return update

async def run_with_progress(self, user_query: str, session_id: str):
    """Modified run_query with progress tracking"""
    self.session_id = session_id
    
    try:
        # PHASE 1: Understanding
        await self.emit_progress("understanding", "Analyzing query", "running")
        
        # Translation check
        if self._is_non_english(user_query):
            await self.emit_progress("understanding", "Translating query", "running")
            user_query, lang = self._translate_query(user_query)
            await self.emit_progress("understanding", "Translation complete", "completed", {"lang": lang})
        
        # Query understanding
        context = {"user_query": user_query}
        query_result = self.query_agent.execute(context)
        await self.emit_progress("understanding", "Query analyzed", "completed", {
            "intent": query_result.get('intent', 'research'),
            "keywords": query_result.get('keywords', [])[:3]
        })
        context.update(query_result)
        
        # PHASE 2: Planning
        await self.emit_progress("planning", "Planning retrieval", "running")
        k = 15 if len(user_query.split()) > 10 else 10
        await self.emit_progress("planning", "Strategy determined", "completed", {"chunks": k})
        
        # PHASE 3: Execution - Retrieval
        await self.emit_progress("execution", "Searching documents", "running")
        retrieval_result = self.retrieval_agent.execute(context)
        num_results = retrieval_result.get('num_results', 0)
        
        if num_results == 0:
            await self.emit_progress("execution", "No documents found", "failed")
            return {"success": False, "error": "No documents found"}
        
        await self.emit_progress("execution", f"Found {num_results} chunks", "completed")
        context.update(retrieval_result)
        
        # PHASE 3: Execution - Reasoning
        await self.emit_progress("execution", "Generating answer", "running", {"model": "Llama-3-8B"})
        reasoning_result = self.reasoning_agent.execute(context)
        answer = reasoning_result.get('answer', '')
        await self.emit_progress("execution", "Answer generated", "completed", {
            "length": len(answer),
            "multimodal": reasoning_result.get('used_multimodal', False)
        })
        context['answer'] = answer
        
        # PHASE 4: Verification
        await self.emit_progress("verification", "Verifying accuracy", "running")
        verification_result = self.verification_agent.execute(context)
        confidence = verification_result.get('confidence', 0.7)
        await self.emit_progress("verification", "Verification complete", "completed", {
            "confidence": f"{confidence:.0%}"
        })
        
        # Complete
        await self.emit_progress("complete", "Task finished", "completed")
        
        return {
            "success": True,
            "answer": answer,
            "confidence": confidence,
            "num_sources": num_results
        }
        
    except Exception as e:
        await self.emit_progress("error", str(e), "failed")
        return {"success": False, "error": str(e)}
1.3 Update API Chat Endpoint (api_server.py)
python
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat endpoint with progress tracking"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Run with progress tracking
        result = await orchestrator.run_with_progress(request.message, session_id)
        
        if result['success']:
            return ChatResponse(
                success=True,
                answer=result['answer'],
                confidence=result.get('confidence', 0.7),
                verified=result.get('confidence', 0.7) >= 0.7,
                sources=result.get('num_sources', 0),
                session_id=session_id
            )
        else:
            return ChatResponse(
                success=False,
                error=result.get('error', 'Unknown error'),
                session_id=session_id
            )
    except Exception as e:
        return ChatResponse(success=False, error=str(e))
قسمت 2: Frontend Changes (static/index.html)
2.1 اضافه کردن Task Progress Panel به HTML
در قسمت <main> بعد از <div id="messages"> اضافه کن:

xml
<!-- Task Progress Tracker (appears above input) -->
<div id="taskProgress" class="hidden bg-white border-t border-slate-200 px-4 py-3">
    <div class="max-w-4xl mx-auto">
        <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-semibold text-slate-600 uppercase tracking-wide">Processing</span>
            <button onclick="toggleTaskProgress()" class="text-slate-400 hover:text-slate-600">
                <i class="fas fa-chevron-down text-xs"></i>
            </button>
        </div>
        
        <!-- Phase Pills -->
        <div class="flex gap-2 mb-3">
            <div id="phase-understanding" class="phase-pill">
                <i class="fas fa-brain text-xs mr-1"></i>
                <span>Understanding</span>
            </div>
            <div id="phase-planning" class="phase-pill">
                <i class="fas fa-list-check text-xs mr-1"></i>
                <span>Planning</span>
            </div>
            <div id="phase-execution" class="phase-pill">
                <i class="fas fa-gear text-xs mr-1"></i>
                <span>Execution</span>
            </div>
            <div id="phase-verification" class="phase-pill">
                <i class="fas fa-check-circle text-xs mr-1"></i>
                <span>Verification</span>
            </div>
        </div>
        
        <!-- Subtask List -->
        <div id="subtaskList" class="space-y-1 max-h-32 overflow-y-auto scrollbar-thin">
            <!-- Subtasks appear here -->
        </div>
        
        <!-- Progress Bar -->
        <div class="mt-2">
            <div class="w-full bg-slate-200 rounded-full h-1">
                <div id="overallProgress" class="bg-blue-600 h-1 rounded-full transition-all duration-300" style="width: 0%"></div>
            </div>
        </div>
    </div>
</div>
2.2 اضافه کردن CSS Styles
در قسمت <style> اضافه کن:

css
/* Task Progress Styles */
.phase-pill {
    display: flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 9999px;
    background: #f1f5f9;
    color: #64748b;
    font-size: 11px;
    font-weight: 500;
    transition: all 0.3s;
}

.phase-pill.active {
    background: #3b82f6;
    color: white;
}

.phase-pill.completed {
    background: #10b981;
    color: white;
}

.phase-pill.failed {
    background: #ef4444;
    color: white;
}

.subtask-item {
    display: flex;
    align-items: center;
    padding: 6px 12px;
    background: #f8fafc;
    border-radius: 6px;
    font-size: 12px;
    animation: slideIn 0.3s ease-out;
}

.subtask-item .status-icon {
    width: 16px;
    height: 16px;
    margin-right: 8px;
    flex-shrink: 0;
}

.subtask-item.running .status-icon {
    color: #3b82f6;
    animation: spin 1s linear infinite;
}

.subtask-item.completed .status-icon {
    color: #10b981;
}

.subtask-item.failed .status-icon {
    color: #ef4444;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
2.3 اضافه کردن JavaScript Functions
در قسمت <script> اضافه کن:

javascript
// Task Progress Tracking
let taskProgressWS = null;
let currentSessionForProgress = null;

function initTaskProgressWebSocket(sessionId) {
    if (taskProgressWS) {
        taskProgressWS.close();
    }
    
    currentSessionForProgress = sessionId;
    const wsUrl = `ws://${window.location.host}/ws/progress/${sessionId}`;
    
    taskProgressWS = new WebSocket(wsUrl);
    
    taskProgressWS.onopen = () => {
        console.log('✅ Task progress WebSocket connected');
        showTaskProgress();
    };
    
    taskProgressWS.onmessage = (event) => {
        const update = JSON.parse(event.data);
        handleTaskUpdate(update);
    };
    
    taskProgressWS.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
    };
    
    taskProgressWS.onclose = () => {
        console.log('WebSocket closed');
        setTimeout(() => hideTaskProgress(), 2000);
    };
}

function showTaskProgress() {
    const panel = document.getElementById('taskProgress');
    panel.classList.remove('hidden');
    
    // Reset state
    document.querySelectorAll('.phase-pill').forEach(p => {
        p.classList.remove('active', 'completed', 'failed');
    });
    document.getElementById('subtaskList').innerHTML = '';
    document.getElementById('overallProgress').style.width = '0%';
}

function hideTaskProgress() {
    const panel = document.getElementById('taskProgress');
    panel.classList.add('hidden');
}

function toggleTaskProgress() {
    const list = document.getElementById('subtaskList');
    const btn = event.currentTarget.querySelector('i');
    
    if (list.style.maxHeight === '0px') {
        list.style.maxHeight = '128px';
        btn.classList.remove('fa-chevron-down');
        btn.classList.add('fa-chevron-up');
    } else {
        list.style.maxHeight = '0px';
        btn.classList.remove('fa-chevron-up');
        btn.classList.add('fa-chevron-down');
    }
}

function handleTaskUpdate(update) {
    const { phase, subtask, status, details } = update;
    
    console.log('📊 Task Update:', phase, subtask, status);
    
    // Update phase pill
    updatePhasePill(phase, status);
    
    // Add subtask to list
    addSubtask(subtask, status, details);
    
    // Update progress bar
    updateProgressBar(phase, status);
}

function updatePhasePill(phase, status) {
    const pillId = `phase-${phase}`;
    const pill = document.getElementById(pillId);
    
    if (!pill) return;
    
    // Remove old status
    pill.classList.remove('active', 'completed', 'failed');
    
    // Add new status
    if (status === 'running') {
        pill.classList.add('active');
    } else if (status === 'completed') {
        pill.classList.add('completed');
    } else if (status === 'failed') {
        pill.classList.add('failed');
    }
}

function addSubtask(subtask, status, details) {
    const list = document.getElementById('subtaskList');
    
    // Create subtask item
    const item = document.createElement('div');
    item.className = `subtask-item ${status}`;
    
    let icon = '';
    if (status === 'running') {
        icon = '<i class="fas fa-spinner status-icon"></i>';
    } else if (status === 'completed') {
        icon = '<i class="fas fa-check-circle status-icon"></i>';
    } else if (status === 'failed') {
        icon = '<i class="fas fa-exclamation-circle status-icon"></i>';
    }
    
    let detailText = '';
    if (details) {
        if (details.keywords) {
            detailText = ` (${details.keywords.join(', ')})`;
        } else if (details.chunks) {
            detailText = ` (${details.chunks} chunks)`;
        } else if (details.confidence) {
            detailText = ` (${details.confidence})`;
        }
    }
    
    item.innerHTML = `
        ${icon}
        <span class="flex-1 text-slate-700">${subtask}${detailText}</span>
    `;
    
    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
}

function updateProgressBar(phase, status) {
    if (status !== 'completed') return;
    
    const phaseProgress = {
        'understanding': 25,
        'planning': 50,
        'execution': 75,
        'verification': 90,
        'complete': 100
    };
    
    const progress = phaseProgress[phase] || 0;
    document.getElementById('overallProgress').style.width = `${progress}%`;
}

// Modify sendMessage() to init WebSocket
async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.remove();

    addMessage('user', message);
    chatHistory.push({role: 'user', content: message});

    // Initialize progress tracking
    const sessionId = currentSessionId || 'temp_' + Date.now();
    initTaskProgressWebSocket(sessionId);

    showTypingIndicator();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        const data = await res.json();
        hideTypingIndicator();

        if (data.success) {
            const metadata = {
                confidence: data.confidence,
                verified: data.verified,
                sources: data.sources,
                artifact: data.artifact
            };
            
            addMessage('assistant', data.answer, metadata);
            chatHistory.push({
                role: 'assistant',
                content: data.answer,
                metadata: metadata
            });
            
            detectAndOpenCanvas(data.answer, metadata);
        } else {
            addMessage('assistant', data.error || 'An error occurred', {error: true});
        }
    } catch (e) {
        hideTypingIndicator();
        addMessage('assistant', 'Failed to get response: ' + e.message, {error: true});
    } finally {
        // Close WebSocket after response
        if (taskProgressWS) {
            setTimeout(() => {
                taskProgressWS.close();
                hideTaskProgress();
            }, 3000);
        }
    }
}
🎯 نتیجه نهایی
با این تغییرات، وقتی کاربر query می‌فرسته:

زیر chat messages یک progress panel ظاهر می‌شه

4 phase pill نمایش داده می‌شه: Understanding → Planning → Execution → Verification

هر subtask به لیست اضافه می‌شه با icon مناسب (spinner/checkmark/error)

Progress bar پایین panel بر اساس phase update می‌شه

بعد از 3 ثانیه از complete شدن، panel خودکار مخفی می‌شه

📝 Summary تغییرات لازم
Backend (api_server.py + main_engine.py):

اضافه کردن WebSocket endpoint برای progress tracking

Modify کردن orchestrator برای emit کردن updates

تقسیم flow به 4 phase اصلی

Frontend (static/index.html):

اضافه کردن progress panel HTML

اضافه کردن CSS styles

اضافه کردن WebSocket client logic

Connect کردن به sendMessage()

تعداد خطوط تغییر: ~200 خط جدید