"""
Visualization Tools for Agent Space
Chart and graph generation utilities
"""
import base64
import io
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

WORKSPACE_ROOT = Path(__file__).parent.parent.parent / "agent_workspace"
OUTPUT_DIR = WORKSPACE_ROOT / "output"
MAX_DATA_POINTS = 10000

CHART_TYPES = [
    "line", "bar", "scatter", "pie", "heatmap",
    "box", "histogram", "area", "violin"
]


class Visualizer:
    """Create charts and visualizations"""
    
    name = "create_visualization"
    description = "Generate charts and graphs from data"
    
    @staticmethod
    def execute(
        data: Union[Dict, List],
        chart_type: str,
        options: Optional[Dict[str, Any]] = None,
        output_format: str = "png"
    ) -> Dict[str, Any]:
        """
        Create a visualization
        
        Args:
            data: Data to visualize (dict or list)
            chart_type: Type of chart (line, bar, scatter, pie, etc.)
            options: Chart options (title, labels, colors, etc.)
            output_format: Output format (png, svg, html)
        
        Returns:
            Dict with image data or file path
        """
        if not MATPLOTLIB_AVAILABLE:
            return {"success": False, "error": "matplotlib not available"}
        
        if chart_type not in CHART_TYPES:
            return {"success": False, "error": f"Unknown chart type: {chart_type}. Available: {CHART_TYPES}"}
        
        options = options or {}
        
        try:
            if PANDAS_AVAILABLE and isinstance(data, (dict, list)):
                df = pd.DataFrame(data)
            else:
                df = data
            
            if len(df) > MAX_DATA_POINTS:
                df = df.head(MAX_DATA_POINTS)
            
            fig, ax = plt.subplots(figsize=options.get("figsize", (10, 6)))
            
            if chart_type == "line":
                Visualizer._create_line(df, ax, options)
            elif chart_type == "bar":
                Visualizer._create_bar(df, ax, options)
            elif chart_type == "scatter":
                Visualizer._create_scatter(df, ax, options)
            elif chart_type == "pie":
                Visualizer._create_pie(df, ax, options)
            elif chart_type == "heatmap":
                Visualizer._create_heatmap(df, ax, options)
            elif chart_type == "box":
                Visualizer._create_box(df, ax, options)
            elif chart_type == "histogram":
                Visualizer._create_histogram(df, ax, options)
            elif chart_type == "area":
                Visualizer._create_area(df, ax, options)
            elif chart_type == "violin":
                Visualizer._create_violin(df, ax, options)
            
            if options.get("title"):
                ax.set_title(options["title"], fontsize=14, fontweight='bold')
            if options.get("xlabel"):
                ax.set_xlabel(options["xlabel"])
            if options.get("ylabel"):
                ax.set_ylabel(options["ylabel"])
            if options.get("legend", True) and chart_type not in ["pie", "heatmap"]:
                ax.legend()
            
            plt.tight_layout()
            
            if output_format == "base64":
                buf = io.BytesIO()
                plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
                buf.seek(0)
                image_base64 = base64.b64encode(buf.read()).decode('utf-8')
                plt.close(fig)
                
                return {
                    "success": True,
                    "format": "base64",
                    "image": image_base64,
                    "mime_type": "image/png"
                }
            else:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                filename = f"chart_{chart_type}_{id(fig)}.{output_format}"
                filepath = OUTPUT_DIR / filename
                plt.savefig(filepath, format=output_format, dpi=100, bbox_inches='tight')
                plt.close(fig)
                
                return {
                    "success": True,
                    "format": output_format,
                    "path": str(filepath),
                    "filename": filename
                }
                
        except Exception as e:
            plt.close('all')
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _create_line(df, ax, options):
        """Create line chart"""
        x = options.get("x")
        y = options.get("y")
        
        if x and y:
            if isinstance(y, list):
                for col in y:
                    ax.plot(df[x], df[col], label=col, marker='o', markersize=4)
            else:
                ax.plot(df[x], df[y], label=y, marker='o', markersize=4)
        else:
            df.plot(kind='line', ax=ax, marker='o', markersize=4)
    
    @staticmethod
    def _create_bar(df, ax, options):
        """Create bar chart"""
        x = options.get("x")
        y = options.get("y")
        
        if x and y:
            if isinstance(y, list):
                df.plot(kind='bar', x=x, y=y, ax=ax)
            else:
                ax.bar(df[x], df[y], label=y)
        else:
            df.plot(kind='bar', ax=ax)
        
        plt.xticks(rotation=45, ha='right')
    
    @staticmethod
    def _create_scatter(df, ax, options):
        """Create scatter plot"""
        x = options.get("x")
        y = options.get("y")
        color = options.get("color")
        size = options.get("size")
        
        if x and y:
            scatter_kwargs = {"alpha": 0.7}
            if color and color in df.columns:
                scatter_kwargs["c"] = df[color]
                scatter_kwargs["cmap"] = "viridis"
            if size and size in df.columns:
                scatter_kwargs["s"] = df[size]
            
            scatter = ax.scatter(df[x], df[y], **scatter_kwargs)
            
            if color and color in df.columns:
                plt.colorbar(scatter, ax=ax, label=color)
    
    @staticmethod
    def _create_pie(df, ax, options):
        """Create pie chart"""
        values = options.get("values")
        labels = options.get("labels")
        
        if values and labels:
            ax.pie(df[values], labels=df[labels], autopct='%1.1f%%', startangle=90)
        elif len(df.columns) >= 2:
            ax.pie(df.iloc[:, 1], labels=df.iloc[:, 0], autopct='%1.1f%%', startangle=90)
        
        ax.axis('equal')
    
    @staticmethod
    def _create_heatmap(df, ax, options):
        """Create heatmap"""
        numeric_df = df.select_dtypes(include=[np.number])
        
        if options.get("correlation", False):
            data = numeric_df.corr()
        else:
            data = numeric_df
        
        sns.heatmap(data, annot=True, fmt='.2f', cmap='coolwarm', ax=ax,
                   center=0, square=True, linewidths=0.5)
    
    @staticmethod
    def _create_box(df, ax, options):
        """Create box plot"""
        columns = options.get("columns")
        
        if columns:
            df[columns].plot(kind='box', ax=ax)
        else:
            df.select_dtypes(include=[np.number]).plot(kind='box', ax=ax)
    
    @staticmethod
    def _create_histogram(df, ax, options):
        """Create histogram"""
        column = options.get("column")
        bins = options.get("bins", 30)
        
        if column:
            ax.hist(df[column], bins=bins, edgecolor='black', alpha=0.7)
            ax.set_xlabel(column)
        else:
            df.select_dtypes(include=[np.number]).iloc[:, 0].hist(ax=ax, bins=bins, edgecolor='black', alpha=0.7)
        
        ax.set_ylabel('Frequency')
    
    @staticmethod
    def _create_area(df, ax, options):
        """Create area chart"""
        x = options.get("x")
        y = options.get("y")
        
        if x and y:
            if isinstance(y, list):
                df.plot(kind='area', x=x, y=y, ax=ax, alpha=0.5)
            else:
                ax.fill_between(df[x], df[y], alpha=0.5)
                ax.plot(df[x], df[y])
        else:
            df.plot(kind='area', ax=ax, alpha=0.5)
    
    @staticmethod
    def _create_violin(df, ax, options):
        """Create violin plot"""
        columns = options.get("columns")
        
        if columns:
            data = [df[col].dropna() for col in columns]
            ax.violinplot(data)
            ax.set_xticks(range(1, len(columns) + 1))
            ax.set_xticklabels(columns)
        else:
            numeric_cols = df.select_dtypes(include=[np.number]).columns[:5]
            data = [df[col].dropna() for col in numeric_cols]
            ax.violinplot(data)
            ax.set_xticks(range(1, len(numeric_cols) + 1))
            ax.set_xticklabels(numeric_cols, rotation=45)


class QuickChart:
    """Quick chart generation helpers"""
    
    @staticmethod
    def bar_chart(labels: List[str], values: List[float], title: str = "Bar Chart") -> Dict[str, Any]:
        """Create simple bar chart"""
        return Visualizer.execute(
            data={"label": labels, "value": values},
            chart_type="bar",
            options={"x": "label", "y": "value", "title": title}
        )
    
    @staticmethod
    def line_chart(x: List, y: List, title: str = "Line Chart") -> Dict[str, Any]:
        """Create simple line chart"""
        return Visualizer.execute(
            data={"x": x, "y": y},
            chart_type="line",
            options={"x": "x", "y": "y", "title": title}
        )
    
    @staticmethod
    def pie_chart(labels: List[str], values: List[float], title: str = "Pie Chart") -> Dict[str, Any]:
        """Create simple pie chart"""
        return Visualizer.execute(
            data={"label": labels, "value": values},
            chart_type="pie",
            options={"labels": "label", "values": "value", "title": title}
        )


visualizer = Visualizer()
quick_chart = QuickChart()
