"""
File Tools for Agent Space
Secure file operations within workspace boundaries
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

WORKSPACE_ROOT = Path(__file__).parent.parent.parent / "agent_workspace"
OUTPUT_DIR = WORKSPACE_ROOT / "output"
DATA_DIR = WORKSPACE_ROOT / "data"

ALLOWED_READ_EXTENSIONS = [".txt", ".md", ".json", ".csv", ".pdf", ".html", ".py"]
ALLOWED_WRITE_EXTENSIONS = [".txt", ".md", ".json", ".csv", ".html"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _validate_path(path: str, base_dir: Path) -> Path:
    """Validate and resolve path within workspace"""
    resolved = (base_dir / path).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise PermissionError(f"Access denied: Path outside workspace")
    return resolved


def _get_file_info(path: Path) -> Dict[str, Any]:
    """Get file metadata"""
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(WORKSPACE_ROOT)),
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "extension": path.suffix,
        "is_file": path.is_file(),
        "is_dir": path.is_dir()
    }


class FileReader:
    """Read files from workspace"""
    
    name = "read_file"
    description = "Read file contents from workspace"
    
    @staticmethod
    def execute(path: str, encoding: str = "utf-8", max_lines: Optional[int] = None) -> Dict[str, Any]:
        """
        Read file from workspace
        
        Args:
            path: Relative path within workspace
            encoding: File encoding (default: utf-8)
            max_lines: Maximum lines to read (optional, for preview)
        
        Returns:
            Dict with content and metadata
        """
        try:
            full_path = _validate_path(path, WORKSPACE_ROOT)
            
            if not full_path.exists():
                return {"success": False, "error": f"File not found: {path}"}
            
            if full_path.suffix not in ALLOWED_READ_EXTENSIONS:
                return {"success": False, "error": f"Extension not allowed: {full_path.suffix}"}
            
            if full_path.stat().st_size > MAX_FILE_SIZE:
                return {"success": False, "error": f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)"}
            
            with open(full_path, 'r', encoding=encoding) as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    content = "".join(lines)
                    truncated = True
                else:
                    content = f.read()
                    truncated = False
            
            return {
                "success": True,
                "content": content,
                "metadata": _get_file_info(full_path),
                "truncated": truncated
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class FileWriter:
    """Write files to output directory"""
    
    name = "write_file"
    description = "Write content to file in output directory"
    
    @staticmethod
    def execute(path: str, content: str, mode: str = "write", encoding: str = "utf-8") -> Dict[str, Any]:
        """
        Write content to file
        
        Args:
            path: Relative path within output directory
            content: Content to write
            mode: 'write' or 'append'
            encoding: File encoding
        
        Returns:
            Dict with success status and file info
        """
        try:
            full_path = _validate_path(path, OUTPUT_DIR)
            
            if full_path.suffix not in ALLOWED_WRITE_EXTENSIONS:
                return {"success": False, "error": f"Extension not allowed: {full_path.suffix}"}
            
            if len(content.encode(encoding)) > MAX_FILE_SIZE:
                return {"success": False, "error": f"Content too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)"}
            
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            write_mode = 'a' if mode == 'append' else 'w'
            with open(full_path, write_mode, encoding=encoding) as f:
                f.write(content)
            
            return {
                "success": True,
                "path": str(full_path.relative_to(WORKSPACE_ROOT)),
                "full_path": str(full_path),
                "size": full_path.stat().st_size,
                "mode": mode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class DirectoryLister:
    """List directory contents"""
    
    name = "list_directory"
    description = "List files and subdirectories in workspace"
    
    @staticmethod
    def execute(path: str = ".", recursive: bool = False, pattern: str = "*") -> Dict[str, Any]:
        """
        List directory contents
        
        Args:
            path: Relative path within workspace
            recursive: Include subdirectories
            pattern: Glob pattern to filter
        
        Returns:
            Dict with files and directories
        """
        try:
            full_path = _validate_path(path, WORKSPACE_ROOT)
            
            if not full_path.exists():
                return {"success": False, "error": f"Directory not found: {path}"}
            
            if not full_path.is_dir():
                return {"success": False, "error": f"Not a directory: {path}"}
            
            files = []
            directories = []
            
            if recursive:
                items = full_path.rglob(pattern)
            else:
                items = full_path.glob(pattern)
            
            for item in items:
                if item == full_path:
                    continue
                info = _get_file_info(item)
                if item.is_file():
                    files.append(info)
                elif item.is_dir():
                    directories.append(info)
            
            return {
                "success": True,
                "path": path,
                "files": files,
                "directories": directories,
                "total_files": len(files),
                "total_directories": len(directories)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class JSONHandler:
    """Handle JSON file operations"""
    
    name = "json_handler"
    description = "Read and write JSON files"
    
    @staticmethod
    def read(path: str) -> Dict[str, Any]:
        """Read and parse JSON file"""
        result = FileReader.execute(path)
        if not result["success"]:
            return result
        
        try:
            data = json.loads(result["content"])
            return {"success": True, "data": data, "metadata": result["metadata"]}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}
    
    @staticmethod
    def write(path: str, data: Any, indent: int = 2) -> Dict[str, Any]:
        """Write data as JSON file"""
        try:
            content = json.dumps(data, indent=indent, ensure_ascii=False)
            return FileWriter.execute(path, content)
        except Exception as e:
            return {"success": False, "error": str(e)}


file_reader = FileReader()
file_writer = FileWriter()
directory_lister = DirectoryLister()
json_handler = JSONHandler()
