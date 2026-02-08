"""
Data Tools for Agent Space
Data analysis and manipulation utilities
"""
import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

WORKSPACE_ROOT = Path(__file__).parent.parent.parent / "agent_workspace"
MAX_ROWS = 100000


class DataAnalyzer:
    """Analyze data with pandas"""
    
    name = "analyze_data"
    description = "Perform statistical analysis on datasets"
    
    @staticmethod
    def execute(
        data_source: Union[str, List, Dict],
        operations: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze data from file or inline
        
        Args:
            data_source: File path, list, or dict of data
            operations: List of operations to perform
        
        Returns:
            Analysis results
        """
        if not PANDAS_AVAILABLE:
            return {"success": False, "error": "pandas not available"}
        
        try:
            if isinstance(data_source, str):
                file_path = (WORKSPACE_ROOT / data_source).resolve()
                if not str(file_path).startswith(str(WORKSPACE_ROOT.resolve())):
                    return {"success": False, "error": "Access denied: path outside workspace"}
                if not file_path.exists():
                    return {"success": False, "error": f"File not found: {data_source}"}
                
                if file_path.suffix == '.csv':
                    df = pd.read_csv(file_path, nrows=MAX_ROWS)
                elif file_path.suffix == '.json':
                    df = pd.read_json(file_path)
                elif file_path.suffix == '.xlsx':
                    df = pd.read_excel(file_path, nrows=MAX_ROWS)
                else:
                    return {"success": False, "error": f"Unsupported format: {file_path.suffix}"}
            elif isinstance(data_source, list):
                df = pd.DataFrame(data_source)
            elif isinstance(data_source, dict):
                df = pd.DataFrame(data_source)
            else:
                return {"success": False, "error": "Invalid data source type"}
            
            if len(df) > MAX_ROWS:
                df = df.head(MAX_ROWS)
                truncated = True
            else:
                truncated = False
            
            results = {
                "success": True,
                "shape": {"rows": len(df), "columns": len(df.columns)},
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "truncated": truncated
            }
            
            if operations:
                results["operations"] = []
                for op in operations:
                    op_type = op.get("type")
                    op_result = DataAnalyzer._execute_operation(df, op)
                    results["operations"].append({
                        "type": op_type,
                        "result": op_result
                    })
            else:
                results["statistics"] = DataAnalyzer._get_statistics(df)
                results["sample"] = df.head(5).to_dict(orient='records')
            
            return results
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _get_statistics(df) -> Dict[str, Any]:
        """Get descriptive statistics"""
        stats = {}
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            desc = df[numeric_cols].describe()
            stats["numeric"] = desc.to_dict()
        
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        if len(cat_cols) > 0:
            stats["categorical"] = {}
            for col in cat_cols[:5]:
                stats["categorical"][col] = {
                    "unique": df[col].nunique(),
                    "top_values": df[col].value_counts().head(5).to_dict()
                }
        
        stats["missing"] = df.isnull().sum().to_dict()
        
        return stats
    
    @staticmethod
    def _execute_operation(df, operation: Dict) -> Any:
        """Execute a single operation on dataframe"""
        op_type = operation.get("type")
        params = operation.get("params", {})
        
        if op_type == "describe":
            return df.describe().to_dict()
        
        elif op_type == "filter":
            column = params.get("column")
            condition = params.get("condition")
            value = params.get("value")
            
            if condition == "equals":
                result = df[df[column] == value]
            elif condition == "greater":
                result = df[df[column] > value]
            elif condition == "less":
                result = df[df[column] < value]
            elif condition == "contains":
                result = df[df[column].str.contains(value, na=False)]
            else:
                return {"error": f"Unknown condition: {condition}"}
            
            return {"rows": len(result), "sample": result.head(10).to_dict(orient='records')}
        
        elif op_type == "aggregate":
            column = params.get("column")
            func = params.get("function", "mean")
            group_by = params.get("group_by")
            
            if group_by:
                result = df.groupby(group_by)[column].agg(func)
                return result.to_dict()
            else:
                return {func: float(getattr(df[column], func)())}
        
        elif op_type == "correlation":
            columns = params.get("columns")
            if columns:
                result = df[columns].corr()
            else:
                result = df.select_dtypes(include=[np.number]).corr()
            return result.to_dict()
        
        elif op_type == "value_counts":
            column = params.get("column")
            return df[column].value_counts().head(20).to_dict()
        
        elif op_type == "sort":
            column = params.get("column")
            ascending = params.get("ascending", True)
            result = df.sort_values(column, ascending=ascending)
            return result.head(20).to_dict(orient='records')
        
        else:
            return {"error": f"Unknown operation: {op_type}"}


class DataTransformer:
    """Transform and manipulate data"""
    
    name = "transform_data"
    description = "Transform datasets"
    
    @staticmethod
    def execute(data: Union[List, Dict], transformations: List[Dict]) -> Dict[str, Any]:
        """Apply transformations to data"""
        if not PANDAS_AVAILABLE:
            return {"success": False, "error": "pandas not available"}
        
        try:
            df = pd.DataFrame(data)
            
            for transform in transformations:
                t_type = transform.get("type")
                params = transform.get("params", {})
                
                if t_type == "rename":
                    df = df.rename(columns=params.get("columns", {}))
                
                elif t_type == "drop":
                    df = df.drop(columns=params.get("columns", []))
                
                elif t_type == "fillna":
                    value = params.get("value", 0)
                    df = df.fillna(value)
                
                elif t_type == "dropna":
                    df = df.dropna()
                
                elif t_type == "select":
                    df = df[params.get("columns", [])]
                
                elif t_type == "add_column":
                    name = params.get("name")
                    expression = params.get("expression")
                    # Use pd.eval for safe expression evaluation (no arbitrary code)
                    df[name] = pd.eval(expression, local_dict={"df": df}, engine="python")
            
            return {
                "success": True,
                "shape": {"rows": len(df), "columns": len(df.columns)},
                "columns": list(df.columns),
                "data": df.to_dict(orient='records')
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class CSVHandler:
    """Handle CSV operations"""
    
    name = "csv_handler"
    description = "Read and write CSV files"
    
    @staticmethod
    def read(path: str, **kwargs) -> Dict[str, Any]:
        """Read CSV file"""
        if not PANDAS_AVAILABLE:
            return {"success": False, "error": "pandas not available"}
        
        try:
            file_path = (WORKSPACE_ROOT / path).resolve()
            if not str(file_path).startswith(str(WORKSPACE_ROOT.resolve())):
                return {"success": False, "error": "Access denied: path outside workspace"}
            df = pd.read_csv(file_path, nrows=MAX_ROWS, **kwargs)
            
            return {
                "success": True,
                "shape": {"rows": len(df), "columns": len(df.columns)},
                "columns": list(df.columns),
                "data": df.to_dict(orient='records')
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def write(path: str, data: Union[List, Dict], **kwargs) -> Dict[str, Any]:
        """Write data to CSV file"""
        if not PANDAS_AVAILABLE:
            return {"success": False, "error": "pandas not available"}
        
        try:
            df = pd.DataFrame(data)
            output_base = (WORKSPACE_ROOT / "output").resolve()
            file_path = (output_base / path).resolve()
            if not str(file_path).startswith(str(output_base)):
                return {"success": False, "error": "Access denied: path outside output directory"}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(file_path, index=False, **kwargs)
            
            return {
                "success": True,
                "path": str(file_path),
                "rows": len(df),
                "columns": len(df.columns)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


data_analyzer = DataAnalyzer()
data_transformer = DataTransformer()
csv_handler = CSVHandler()
