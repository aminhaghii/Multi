"""
Agent Space API Routes
Handles tool execution and capability management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from pathlib import Path

import sys
sys.path.insert(0, str(__file__).replace('\\', '/').rsplit('/', 3)[0])

from core.capability_registry import CapabilityRegistry
from agent_space.tools import (
    file_reader, file_writer, directory_lister,
    python_executor, data_analyzer, visualizer
)
from config.settings import settings

router = APIRouter(prefix="/api/agent-space", tags=["agent-space"])

capability_registry = CapabilityRegistry(Path(settings.config_dir) / "capabilities.yaml")


class ExecuteToolRequest(BaseModel):
    tool: str
    params: Dict[str, Any]
    session_id: Optional[str] = None


class ToolResponse(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


AVAILABLE_TOOLS = {
    "read_file": file_reader.execute,
    "write_file": file_writer.execute,
    "list_directory": directory_lister.execute,
    "execute_python": python_executor.execute,
    "analyze_data": data_analyzer.execute,
    "create_visualization": visualizer.execute,
}


@router.get("/capabilities")
async def get_capabilities():
    """Get all available capabilities and their status"""
    try:
        enabled = capability_registry.list_enabled()
        all_caps = capability_registry.list_all()
        
        return {
            "capabilities": all_caps,
            "enabled": enabled,
            "prompt_context": capability_registry.to_prompt_context()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_tools():
    """List available tools"""
    tools = []
    for name, func in AVAILABLE_TOOLS.items():
        tools.append({
            "name": name,
            "description": getattr(func, '__doc__', '') or f"Execute {name}",
            "available": True
        })
    
    return {"tools": tools}


@router.post("/execute", response_model=ToolResponse)
async def execute_tool(request: ExecuteToolRequest):
    """Execute an agent tool"""
    tool_name = request.tool
    params = request.params
    
    if tool_name not in AVAILABLE_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tool: {tool_name}. Available: {list(AVAILABLE_TOOLS.keys())}"
        )
    
    import time
    start_time = time.time()
    
    try:
        tool_func = AVAILABLE_TOOLS[tool_name]
        result = tool_func(**params)
        execution_time = time.time() - start_time
        
        success = result.get("success", True) if isinstance(result, dict) else True
        
        return ToolResponse(
            success=success,
            result=result,
            error=result.get("error") if isinstance(result, dict) else None,
            execution_time=execution_time
        )
    except Exception as e:
        execution_time = time.time() - start_time
        return ToolResponse(
            success=False,
            result=None,
            error=str(e),
            execution_time=execution_time
        )


@router.post("/execute/python")
async def execute_python_code(code: str, inputs: Optional[Dict[str, Any]] = None):
    """Quick endpoint for Python code execution"""
    try:
        result = python_executor.execute(code=code, inputs=inputs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/analyze")
async def analyze_data_quick(data_source: str, operations: Optional[List[Dict]] = None):
    """Quick endpoint for data analysis"""
    try:
        result = data_analyzer.execute(data_source=data_source, operations=operations)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/visualize")
async def create_visualization_quick(
    data: Dict[str, Any],
    chart_type: str,
    options: Optional[Dict[str, Any]] = None
):
    """Quick endpoint for visualization"""
    try:
        result = visualizer.execute(data=data, chart_type=chart_type, options=options)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspace")
async def get_workspace_info():
    """Get workspace directory information"""
    try:
        workspace_path = settings.workspace_dir
        result = directory_lister.execute(path=".", recursive=False)
        
        return {
            "workspace_root": str(workspace_path),
            "directories": result.get("directories", []),
            "files": result.get("files", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CheckPermissionRequest(BaseModel):
    category: str
    name: str
    file_size: Optional[int] = None
    extension: Optional[str] = None
    duration: Optional[float] = None


@router.post("/check-permission")
async def check_permission(request: CheckPermissionRequest):
    """Check if an action is permitted"""
    extra = {}
    if request.file_size is not None:
        extra["file_size"] = request.file_size
    if request.extension is not None:
        extra["extension"] = request.extension
    if request.duration is not None:
        extra["duration"] = request.duration
    allowed, reason = capability_registry.check_permission(request.category, request.name, **extra)
    return {
        "allowed": allowed,
        "reason": reason
    }
