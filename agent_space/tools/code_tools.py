"""
Code Tools for Agent Space
Safe Python code execution in sandboxed environment
"""
import sys
import io
import ast
import time
import traceback
from typing import Dict, Any, List, Optional
from contextlib import redirect_stdout, redirect_stderr
import threading
import queue

ALLOWED_IMPORTS = [
    "numpy", "pandas", "matplotlib", "seaborn",
    "json", "csv", "datetime", "math", "random",
    "collections", "itertools", "functools", "re",
    "statistics", "decimal", "fractions"
]

BLOCKED_IMPORTS = [
    "os", "sys", "subprocess", "shutil", "socket",
    "requests", "urllib", "ftplib", "smtplib",
    "pickle", "shelve", "multiprocessing", "threading",
    "ctypes", "importlib", "builtins", "__builtins__"
]

TIMEOUT_SECONDS = 30
MAX_OUTPUT_SIZE = 100000  # 100KB


class CodeValidator:
    """Validate Python code for safety"""
    
    @staticmethod
    def check_imports(code: str) -> tuple[bool, str]:
        """Check if code contains blocked imports"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module in BLOCKED_IMPORTS:
                        return False, f"Blocked import: {module}"
                    if module not in ALLOWED_IMPORTS and module not in ['math', 'json', 're']:
                        return False, f"Import not in allowlist: {module}"
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module.split('.')[0] if node.module else ''
                if module in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {module}"
        
        return True, "OK"
    
    @staticmethod
    def check_dangerous_calls(code: str) -> tuple[bool, str]:
        """Check for dangerous function calls"""
        dangerous = ['eval', 'exec', 'compile', 'open', '__import__', 'globals', 'locals']
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True, "OK"  # Already caught in check_imports
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in dangerous:
                        return False, f"Dangerous function call: {node.func.id}"
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in dangerous:
                        return False, f"Dangerous method call: {node.func.attr}"
        
        return True, "OK"
    
    @staticmethod
    def validate(code: str) -> tuple[bool, str]:
        """Full validation of code"""
        valid, msg = CodeValidator.check_imports(code)
        if not valid:
            return False, msg
        
        valid, msg = CodeValidator.check_dangerous_calls(code)
        if not valid:
            return False, msg
        
        return True, "Code is safe to execute"


class PythonExecutor:
    """Execute Python code safely"""
    
    name = "execute_python"
    description = "Execute Python code in a sandboxed environment"
    
    @staticmethod
    def execute(code: str, inputs: Optional[Dict[str, Any]] = None, timeout: int = TIMEOUT_SECONDS) -> Dict[str, Any]:
        """
        Execute Python code safely
        
        Args:
            code: Python code to execute
            inputs: Variables to inject into execution context
            timeout: Maximum execution time in seconds
        
        Returns:
            Dict with stdout, stderr, return_value, execution_time
        """
        valid, msg = CodeValidator.validate(code)
        if not valid:
            return {
                "success": False,
                "error": msg,
                "stdout": "",
                "stderr": "",
                "return_value": None,
                "execution_time": 0
            }
        
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "reversed": reversed,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "type": type,
                "isinstance": isinstance,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                "True": True,
                "False": False,
                "None": None,
            }
        }
        
        if inputs:
            safe_globals.update(inputs)
        
        try:
            import numpy as np
            import pandas as pd
            safe_globals['np'] = np
            safe_globals['numpy'] = np
            safe_globals['pd'] = pd
            safe_globals['pandas'] = pd
        except ImportError:
            pass
        
        try:
            import json
            import math
            import random
            import statistics
            import re
            from datetime import datetime, timedelta
            from collections import Counter, defaultdict
            
            safe_globals['json'] = json
            safe_globals['math'] = math
            safe_globals['random'] = random
            safe_globals['statistics'] = statistics
            safe_globals['re'] = re
            safe_globals['datetime'] = datetime
            safe_globals['timedelta'] = timedelta
            safe_globals['Counter'] = Counter
            safe_globals['defaultdict'] = defaultdict
        except ImportError:
            pass
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        result_queue = queue.Queue()
        
        def run_code():
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec_result = exec(code, safe_globals)
                    
                    if '_result' in safe_globals:
                        result_queue.put(("success", safe_globals['_result']))
                    else:
                        result_queue.put(("success", None))
            except Exception as e:
                result_queue.put(("error", traceback.format_exc()))
        
        start_time = time.time()
        thread = threading.Thread(target=run_code)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        execution_time = time.time() - start_time
        
        if thread.is_alive():
            return {
                "success": False,
                "error": f"Execution timed out after {timeout} seconds",
                "stdout": stdout_capture.getvalue()[:MAX_OUTPUT_SIZE],
                "stderr": stderr_capture.getvalue()[:MAX_OUTPUT_SIZE],
                "return_value": None,
                "execution_time": execution_time
            }
        
        try:
            status, result = result_queue.get_nowait()
        except queue.Empty:
            status, result = "error", "No result returned"
        
        stdout = stdout_capture.getvalue()[:MAX_OUTPUT_SIZE]
        stderr = stderr_capture.getvalue()[:MAX_OUTPUT_SIZE]
        
        if status == "error":
            return {
                "success": False,
                "error": result,
                "stdout": stdout,
                "stderr": stderr,
                "return_value": None,
                "execution_time": execution_time
            }
        
        return {
            "success": True,
            "error": None,
            "stdout": stdout,
            "stderr": stderr,
            "return_value": result,
            "execution_time": execution_time
        }


class CodeAnalyzer:
    """Analyze code structure and complexity"""
    
    name = "analyze_code"
    description = "Analyze Python code structure"
    
    @staticmethod
    def execute(code: str) -> Dict[str, Any]:
        """Analyze code and return metrics"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"success": False, "error": f"Syntax error: {e}"}
        
        functions = []
        classes = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "line": node.lineno
                })
            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(f"from {node.module}")
        
        lines = code.split('\n')
        
        return {
            "success": True,
            "metrics": {
                "total_lines": len(lines),
                "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
                "functions": len(functions),
                "classes": len(classes),
                "imports": len(imports)
            },
            "functions": functions,
            "classes": classes,
            "imports": imports
        }


python_executor = PythonExecutor()
code_analyzer = CodeAnalyzer()
code_validator = CodeValidator()
