"""
Export chat history to PDF, Markdown, or Word formats
"""
import os
import html
from datetime import datetime
from typing import List, Dict
from pathlib import Path


def generate_markdown(chat_history: List[Dict]) -> str:
    """Generate Markdown report from chat history"""
    md = f"# Chat Report\n\n"
    md += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "---\n\n"
    
    image_paths = []
    
    for i, entry in enumerate(chat_history, 1):
        role = entry.get('role', 'user')
        content = entry.get('content', '')
        metadata = entry.get('metadata', {})
        
        if role == 'user':
            md += f"## Question {i}\n\n"
            md += f"{content}\n\n"
        elif role == 'assistant':
            md += f"## Answer {i}\n\n"
            md += f"{content}\n\n"
            
            # Add metadata
            if metadata:
                md += "**Metadata:**\n"
                if 'confidence' in metadata:
                    try:
                        conf_val = float(metadata['confidence'])
                        md += f"- Confidence: {conf_val:.0%}\n"
                    except (ValueError, TypeError):
                        md += f"- Confidence: {metadata['confidence']}\n"
                if 'verified' in metadata:
                    md += f"- Verified: {'✓' if metadata['verified'] else '✗'}\n"
                if 'sources' in metadata:
                    md += f"- Sources: {metadata['sources']}\n"
                md += "\n"
            
            # Collect image paths
            if metadata.get('image_paths'):
                for img in metadata['image_paths']:
                    img_path = img.get('path', '')
                    if img_path and img_path not in image_paths:
                        image_paths.append(img_path)
        
        md += "---\n\n"
    
    # Add images section at the end
    if image_paths:
        md += "# Related Figures\n\n"
        for i, img_path in enumerate(image_paths, 1):
            md += f"## Figure {i}\n\n"
            md += f"![Figure {i}]({img_path})\n\n"
            md += f"*Source: {img_path}*\n\n"
    
    return md


def generate_html(chat_history: List[Dict]) -> str:
    """Generate HTML report from chat history"""
    html_out = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Chat Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            line-height: 1.6;
        }}
        .header {{
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .entry {{
            margin-bottom: 30px;
            padding: 20px;
            border-radius: 8px;
        }}
        .user {{
            background-color: #e3f2fd;
        }}
        .assistant {{
            background-color: #f5f5f5;
        }}
        .metadata {{
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
        }}
        .images {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #333;
        }}
        .image-item {{
            margin-bottom: 30px;
        }}
        .image-item img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        h1, h2 {{
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Chat Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
"""
    
    image_paths = []
    
    for i, entry in enumerate(chat_history, 1):
        role = entry.get('role', 'user')
        # EXPORT-001 FIX: Escape HTML to prevent XSS
        raw_content = entry.get('content', '')
        safe_content = html.escape(raw_content)
        content = safe_content.replace('\n', '<br>')
        metadata = entry.get('metadata', {})
        
        if role == 'user':
            html_out += f"""
    <div class="entry user">
        <h2>Question {i}</h2>
        <p>{content}</p>
    </div>
"""
        elif role == 'assistant':
            html_out += f"""
    <div class="entry assistant">
        <h2>Answer {i}</h2>
        <p>{content}</p>
"""
            if metadata:
                html_out += '        <div class="metadata">\n'
                if 'confidence' in metadata:
                    try:
                        conf_val = float(metadata['confidence'])
                        html_out += f'            <p><strong>Confidence:</strong> {conf_val:.0%}</p>\n'
                    except (ValueError, TypeError):
                        html_out += f'            <p><strong>Confidence:</strong> {html.escape(str(metadata["confidence"]))}</p>\n'
                if 'verified' in metadata:
                    verified = '✓' if metadata['verified'] else '✗'
                    html_out += f'            <p><strong>Verified:</strong> {verified}</p>\n'
                if 'sources' in metadata:
                    html_out += f'            <p><strong>Sources:</strong> {html.escape(str(metadata["sources"]))}</p>\n'
                html_out += '        </div>\n'
            
            html_out += '    </div>\n'
            
            # Collect image paths
            if metadata.get('image_paths'):
                for img in metadata['image_paths']:
                    img_path = img.get('path', '')
                    if img_path and img_path not in image_paths:
                        image_paths.append((img_path, img.get('source', ''), img.get('page', '')))
    
    # Add images section
    if image_paths:
        html_out += """
    <div class="images">
        <h1>Related Figures</h1>
"""
        for i, (img_path, source, page) in enumerate(image_paths, 1):
            safe_img_path = html.escape(str(img_path))
            safe_source = html.escape(str(source))
            safe_page = html.escape(str(page))
            html_out += f"""
        <div class="image-item">
            <h2>Figure {i}</h2>
            <img src="{safe_img_path}" alt="Figure {i}">
            <p><em>Source: {safe_source} (Page {safe_page})</em></p>
        </div>
"""
        html_out += """
    </div>
"""
    
    html_out += """
</body>
</html>
"""
    return html_out


def save_markdown(chat_history: List[Dict], output_path: str) -> str:
    """Save chat history as Markdown file"""
    md_content = generate_markdown(chat_history)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return output_path


def save_html(chat_history: List[Dict], output_path: str) -> str:
    """Save chat history as HTML file (can be converted to PDF)"""
    html_content = generate_html(chat_history)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path


def export_chat(chat_history: List[Dict], format: str = 'markdown', output_dir: str = './exports') -> str:
    """
    Export chat history to specified format
    
    Args:
        chat_history: List of chat entries with role, content, metadata
        format: 'markdown', 'html', or 'pdf'
        output_dir: Directory to save exported files
    
    Returns:
        Path to exported file
    """
    # EXPORT-002 FIX: Prevent path traversal
    safe_dir = os.path.abspath(output_dir)
    exports_base = os.path.abspath('./exports')
    if not safe_dir.startswith(exports_base):
        raise ValueError("Invalid output directory - path traversal detected")
    
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format == 'markdown':
        filename = f"chat_report_{timestamp}.md"
        output_path = os.path.join(output_dir, filename)
        return save_markdown(chat_history, output_path)
    
    elif format == 'html':
        filename = f"chat_report_{timestamp}.html"
        output_path = os.path.join(output_dir, filename)
        return save_html(chat_history, output_path)
    
    elif format == 'pdf':
        # First generate HTML, then convert to PDF using browser print
        html_filename = f"chat_report_{timestamp}.html"
        html_path = os.path.join(output_dir, html_filename)
        save_html(chat_history, html_path)
        
        # Return HTML path - frontend can use browser print to PDF
        return html_path
    
    else:
        raise ValueError(f"Unsupported format: {format}")
