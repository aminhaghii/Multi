🔧 COMPREHENSIVE FIX IMPLEMENTATION MAP
Resolving All Identified Issues in Agentic Research Assistant
CRITICAL ISSUE #1: LLM REASONING FAILURES
Problem Analysis
The ReasoningAgent fails on approximately 25% of queries with error "Reasoning failed" without detailed information. This is the highest priority issue affecting system reliability.

Root Cause Investigation
Step 1: Add Comprehensive Error Logging
File: agents/reasoning_agent.py (or agents/specific_agents.py)

Current Problem: Errors are caught but not logged with details

Implementation:

text

TASK: Enhance error logging in ReasoningAgent

Location: agents/reasoning_agent.py (or wherever ReasoningAgent is defined)

Find the main reasoning method (likely called 'reason', 'generate_answer', or 'process')

Add the following error handling pattern:

1. Wrap the entire reasoning logic in try-except
2. Log the following on any exception:
   - Full exception type and message
   - Stack trace
   - Input query that caused the failure
   - Context chunks that were passed
   - LLM prompt that was constructed
   - LLM response (if any was received before failure)

3. Create a dedicated log file for reasoning failures:
   - Path: logs/reasoning_failures.log
   - Format: timestamp, query, context_length, error_type, error_message, stack_trace

4. Add timing logs:
   - Time when LLM request started
   - Time when LLM response received (or timeout)
   - Total reasoning duration

5. Add context validation before sending to LLM:
   - Check if context is empty
   - Check if context exceeds token limit
   - Check if context contains malformed data
Step 2: Fix Token Limit Issues
Problem: Context window of 2048 tokens may be insufficient

Implementation:

text

TASK: Implement smart context truncation

Location: agents/reasoning_agent.py

1. Before sending to LLM, calculate approximate token count:
   - Use tiktoken library or simple word count * 1.3 estimation
   - Reserve tokens for: system prompt (~200), query (~100), response (~500)
   - Available for context: 2048 - 200 - 100 - 500 = ~1248 tokens

2. Implement context prioritization:
   - Score each chunk by relevance (from retrieval score)
   - Sort chunks by score descending
   - Add chunks until token limit reached
   - Always include at least top 3 chunks

3. Add context compression for long chunks:
   - If single chunk > 400 tokens, summarize or truncate
   - Keep first and last sentences (usually most important)
   - Remove redundant whitespace and formatting

4. Log when truncation occurs:
   - Original context length
   - Truncated context length
   - Number of chunks removed
   - Chunks that were kept (IDs/scores)
Step 3: Improve Prompt Engineering
Problem: Current prompt may not handle edge cases well

Implementation:

text

TASK: Redesign ReasoningAgent prompt template

Location: agents/reasoning_agent.py or config/prompts/

Current prompt structure (assumed):
- System message
- Context
- Query
- Request for answer

New prompt structure:

---
SYSTEM PROMPT:
You are a precise research assistant. Your task is to answer questions 
based ONLY on the provided context. Follow these rules strictly:

1. ONLY use information from the context below
2. If the answer is in the context, provide it clearly
3. If the answer is NOT in the context, say: "This information is not available in the provided documents."
4. NEVER make up information or use external knowledge
5. Quote relevant parts of the context when possible
6. If the context contains partial information, provide what is available and note what is missing

---
CONTEXT FROM DOCUMENTS:
{context}

---
USER QUESTION:
{query}

---
INSTRUCTIONS:
- Read the context carefully
- Find information relevant to the question
- Formulate a clear, accurate answer
- Include source references (page numbers if available)
- If uncertain, express the level of confidence

ANSWER:
---

Additional prompt variations for different query types:

For FACTUAL queries (what, when, who, where):
- Add: "Provide a direct, concise answer with the specific fact requested."

For ANALYTICAL queries (why, how, compare):
- Add: "Provide a structured analysis based on the context."

For EXTRACTION queries (list all, show all, extract):
- Add: "Create a comprehensive list of all relevant items from the context."

For NUMERICAL queries (how many, what percentage, calculate):
- Add: "Provide the exact numbers from the context. Do not estimate."
Step 4: Add Fallback Mechanisms
Implementation:

text

TASK: Implement multi-level fallback for reasoning failures

Location: agents/reasoning_agent.py and main_engine.py

Fallback Level 1: Retry with simplified prompt
- If first attempt fails, retry with minimal prompt
- Remove complex instructions
- Just: "Context: {context}\n\nQuestion: {query}\n\nAnswer based on context:"

Fallback Level 2: Retry with reduced context
- If still failing, reduce context to top 2 chunks only
- This reduces complexity and token count

Fallback Level 3: Direct extraction mode
- If LLM reasoning completely fails
- Use simple string matching to find relevant sentences
- Return: "Based on the documents, I found the following relevant information: {matched_sentences}"

Fallback Level 4: Graceful degradation
- If all else fails
- Return: "I found relevant information in the documents but encountered an error processing it. The relevant sections are from: {source_list}. Please try rephrasing your question."

Implementation structure:

def reason(self, query, context):
    # Attempt 1: Full reasoning
    try:
        result = self._full_reasoning(query, context)
        if result and len(result) > 50:
            return result
    except Exception as e:
        log_error("Full reasoning failed", e)
    
    # Attempt 2: Simplified prompt
    try:
        result = self._simplified_reasoning(query, context)
        if result and len(result) > 50:
            return result
    except Exception as e:
        log_error("Simplified reasoning failed", e)
    
    # Attempt 3: Reduced context
    try:
        reduced_context = context[:2]  # Top 2 chunks only
        result = self._simplified_reasoning(query, reduced_context)
        if result and len(result) > 50:
            return result
    except Exception as e:
        log_error("Reduced context reasoning failed", e)
    
    # Attempt 4: Direct extraction
    try:
        result = self._direct_extraction(query, context)
        return result
    except Exception as e:
        log_error("Direct extraction failed", e)
    
    # Final fallback
    return self._graceful_fallback(query, context)
Step 5: LLM Communication Improvements
Implementation:

text

TASK: Improve LLM client robustness

Location: llm_client.py

1. Add request timeout handling:
   - Set explicit timeout (30 seconds)
   - Handle timeout exception gracefully
   - Log timeout occurrences

2. Add retry logic for transient failures:
   - Retry up to 3 times on connection errors
   - Exponential backoff: 1s, 2s, 4s
   - Different handling for different error types

3. Add response validation:
   - Check if response is empty
   - Check if response is just whitespace
   - Check if response is error message from LLM
   - Check minimum response length (at least 20 chars for valid answer)

4. Add health check before reasoning:
   - Quick ping to LLM server
   - If unhealthy, return appropriate error instead of generic failure

5. Handle LLM-specific error patterns:
   - "I cannot", "I don't know" -> Mark as low confidence, not failure
   - Empty response -> Retry with different prompt
   - Repeated text -> Truncate and retry
   - JSON parsing errors -> Extract text content manually

Code structure:

class LLMClient:
    def __init__(self):
        self.timeout = 30
        self.max_retries = 3
        self.base_url = "http://127.0.0.1:8080"
    
    def generate(self, prompt, max_tokens=512):
        for attempt in range(self.max_retries):
            try:
                response = self._send_request(prompt, max_tokens)
                validated = self._validate_response(response)
                if validated:
                    return validated
            except TimeoutError:
                log(f"Timeout on attempt {attempt + 1}")
                continue
            except ConnectionError:
                log(f"Connection error on attempt {attempt + 1}")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            except Exception as e:
                log(f"Unexpected error: {e}")
                break
        
        return None  # All attempts failed
    
    def _validate_response(self, response):
        if not response or len(response.strip()) < 20:
            return None
        if response.strip().startswith("Error"):
            return None
        # Remove potential repeated text
        response = self._remove_repetition(response)
        return response
CRITICAL ISSUE #2: CANVAS AUTO-DETECTION
Problem Analysis
Backend correctly creates artifact object but frontend doesn't open Canvas panel because it only checks markdown patterns, not metadata.artifact.

Implementation Fix
Step 1: Fix Frontend Detection Logic
File: static/index.html

Implementation:

text

TASK: Fix detectAndOpenCanvas function

Location: static/index.html, around line 990-1010

Find the current detectAndOpenCanvas function and replace with:

function detectAndOpenCanvas(response, metadata) {
    // PRIORITY 1: Check metadata.artifact from backend (most reliable)
    if (metadata && metadata.artifact && metadata.artifact.content) {
        console.log('Opening canvas from metadata.artifact');
        openCanvas(
            metadata.artifact.title || 'Generated Report',
            metadata.artifact.type || 'report',
            metadata.artifact.content
        );
        return true;
    }
    
    // PRIORITY 2: Check for code blocks with specific types
    const codeBlockPattern = /```(html|markdown|report|code|table|json|csv)\n([\s\S]*?)```/g;
    const matches = [...response.matchAll(codeBlockPattern)];
    
    if (matches.length > 0) {
        // Take the largest code block (likely the main content)
        let largestMatch = matches[0];
        for (const match of matches) {
            if (match[2].length > largestMatch[2].length) {
                largestMatch = match;
            }
        }
        
        const type = largestMatch[1];
        const content = largestMatch[2];
        
        console.log('Opening canvas from code block:', type);
        openCanvas('Generated ' + type.charAt(0).toUpperCase() + type.slice(1), type, content);
        return true;
    }
    
    // PRIORITY 3: Check for very long responses (auto-report)
    if (response.length > 2000) {
        console.log('Opening canvas for long response');
        const htmlContent = formatLongResponseAsHTML(response);
        openCanvas('Detailed Response', 'report', htmlContent);
        return true;
    }
    
    return false;
}

// Helper function to format long response as HTML
function formatLongResponseAsHTML(response) {
    // Convert markdown-like formatting to HTML
    let html = response
        // Headers
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        // Bold
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Lists
        .replace(/^\- (.*$)/gim, '<li>$1</li>')
        .replace(/^\* (.*$)/gim, '<li>$1</li>')
        .replace(/^(\d+)\. (.*$)/gim, '<li>$2</li>')
        // Paragraphs
        .replace(/\n\n/g, '</p><p>')
        // Line breaks
        .replace(/\n/g, '<br>');
    
    // Wrap lists
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    
    // Wrap in container
    return `
        <div style="font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; padding: 20px;">
            <p>${html}</p>
        </div>
    `;
}
Step 2: Update sendMessage Response Handler
File: static/index.html

Implementation:

text

TASK: Update the response handler in sendMessage function

Location: static/index.html, in the sendMessage async function, after receiving response

Find where the response is processed (after fetch call) and add:

// After parsing the JSON response
const data = await response.json();

// ... existing code to display message ...

// ADD THIS: Check for artifact and open canvas
if (data.artifact || data.metadata?.artifact) {
    const artifact = data.artifact || data.metadata.artifact;
    
    // Small delay to let the message render first
    setTimeout(() => {
        openCanvas(
            artifact.title || 'Generated Content',
            artifact.type || 'report',
            artifact.content || ''
        );
    }, 500);
}

// Also call detectAndOpenCanvas for markdown-based artifacts
setTimeout(() => {
    detectAndOpenCanvas(data.response || data.answer || '', data.metadata || data);
}, 600);
Step 3: Add Canvas Toggle Button to Messages
Implementation:

text

TASK: Add manual canvas toggle for artifact messages

Location: static/index.html, in message rendering section

When rendering assistant messages, add a canvas button if artifact exists:

// In the message bubble creation code, add:

if (hasArtifact || response.length > 1500) {
    const canvasButton = document.createElement('button');
    canvasButton.className = 'canvas-toggle-btn';
    canvasButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z">
            </path>
        </svg>
        <span>Open in Canvas</span>
    `;
    canvasButton.onclick = () => {
        if (artifactContent) {
            openCanvas(artifactTitle, artifactType, artifactContent);
        } else {
            // Generate from response
            const html = formatLongResponseAsHTML(response);
            openCanvas('Response Details', 'report', html);
        }
    };
    messageActions.appendChild(canvasButton);
}

// Add CSS for the button:
.canvas-toggle-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: linear-gradient(135deg, #0891b2, #0e7490);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
}

.canvas-toggle-btn:hover {
    background: linear-gradient(135deg, #0e7490, #155e75);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(8, 145, 178, 0.3);
}
Step 4: Improve Artifact Detection in Backend
File: main_engine.py

Implementation:

text

TASK: Enhance artifact detection logic

Location: main_engine.py, in _detect_artifact_need method

Replace current implementation with:

def _detect_artifact_need(self, query: str, answer: str, intent: str) -> Optional[Dict[str, Any]]:
    """
    Detect if the response should include an artifact for Canvas panel.
    
    Returns artifact dict or None.
    """
    query_lower = query.lower()
    
    # Keywords that strongly indicate artifact need
    strong_artifact_keywords = [
        'create a report', 'generate a report', 'write a report',
        'create a summary', 'generate a summary',
        'create a table', 'generate a table', 'make a table',
        'create a chart', 'generate a chart',
        'create a visualization', 'visualize',
        'compile a list', 'list all', 'show all', 'extract all',
        'create a document', 'format as',
        'comprehensive analysis', 'detailed analysis',
        'compare and contrast', 'comparison of'
    ]
    
    # Check for strong keywords
    for keyword in strong_artifact_keywords:
        if keyword in query_lower:
            return self._generate_artifact(query, answer, 'report')
    
    # Check intent-based triggers
    if intent in ['report_generation', 'data_extraction', 'comparison', 'analysis']:
        return self._generate_artifact(query, answer, 'report')
    
    # Check response length (very long responses benefit from canvas)
    if len(answer) > 1500:
        # Check if response has structure (headers, lists, etc.)
        has_structure = any([
            '##' in answer,
            '\n- ' in answer,
            '\n* ' in answer,
            '\n1. ' in answer,
            '|' in answer and '-|-' in answer  # Tables
        ])
        
        if has_structure:
            return self._generate_artifact(query, answer, 'report')
    
    # Check for data-heavy responses
    if self._is_data_heavy(answer):
        return self._generate_artifact(query, answer, 'data')
    
    return None

def _is_data_heavy(self, answer: str) -> bool:
    """Check if answer contains significant structured data."""
    # Count data indicators
    indicators = 0
    
    # Numbers and percentages
    import re
    numbers = re.findall(r'\d+\.?\d*%?', answer)
    if len(numbers) > 10:
        indicators += 1
    
    # Table-like patterns
    if answer.count('|') > 10:
        indicators += 1
    
    # List items
    list_items = len(re.findall(r'\n[-*]\s', answer))
    if list_items > 5:
        indicators += 1
    
    # Numbered items
    numbered = len(re.findall(r'\n\d+\.\s', answer))
    if numbered > 5:
        indicators += 1
    
    return indicators >= 2

def _generate_artifact(self, query: str, answer: str, artifact_type: str) -> Dict[str, Any]:
    """Generate properly formatted artifact."""
    
    # Determine title from query
    title = self._extract_title(query)
    
    # Format content based on type
    if artifact_type == 'report':
        content = self._format_as_html_report(answer, query)
    elif artifact_type == 'data':
        content = self._format_as_data_view(answer)
    else:
        content = self._format_as_html_report(answer, query)
    
    return {
        'title': title,
        'type': artifact_type,
        'content': content
    }

def _extract_title(self, query: str) -> str:
    """Extract a meaningful title from the query."""
    # Remove common prefixes
    prefixes = [
        'create a ', 'generate a ', 'write a ', 'make a ',
        'show me ', 'give me ', 'provide ', 'list ',
        'what is ', 'what are ', 'how to '
    ]
    
    title = query
    for prefix in prefixes:
        if title.lower().startswith(prefix):
            title = title[len(prefix):]
            break
    
    # Capitalize and limit length
    title = title.strip().capitalize()
    if len(title) > 50:
        title = title[:47] + '...'
    
    return title or 'Generated Report'

def _format_as_html_report(self, content: str, query: str) -> str:
    """Format content as a styled HTML report."""
    
    # Convert markdown to HTML
    import re
    
    html_content = content
    
    # Headers
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    
    # Bold and italic
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_content)
    
    # Lists
    html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^\* (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^(\d+)\. (.+)$', r'<li>\2</li>', html_content, flags=re.MULTILINE)
    
    # Wrap consecutive <li> elements in <ul>
    html_content = re.sub(r'((?:<li>.+?</li>\n?)+)', r'<ul>\1</ul>', html_content)
    
    # Paragraphs
    paragraphs = html_content.split('\n\n')
    html_content = ''.join([
        f'<p>{p.strip()}</p>' if not p.strip().startswith('<') else p 
        for p in paragraphs if p.strip()
    ])
    
    # Create full HTML document
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
                line-height: 1.7;
                color: #1e293b;
                max-width: 800px;
                margin: 0 auto;
                padding: 40px 20px;
                background: #ffffff;
            }}
            h1 {{
                color: #0f172a;
                font-size: 28px;
                font-weight: 700;
                border-bottom: 3px solid #0891b2;
                padding-bottom: 12px;
                margin-bottom: 24px;
            }}
            h2 {{
                color: #1e293b;
                font-size: 22px;
                font-weight: 600;
                margin-top: 32px;
                margin-bottom: 16px;
            }}
            h3 {{
                color: #334155;
                font-size: 18px;
                font-weight: 600;
                margin-top: 24px;
                margin-bottom: 12px;
            }}
            p {{
                margin-bottom: 16px;
                text-align: justify;
            }}
            ul {{
                margin: 16px 0;
                padding-left: 24px;
            }}
            li {{
                margin-bottom: 8px;
            }}
            strong {{
                color: #0f172a;
            }}
            .report-header {{
                background: linear-gradient(135deg, #0891b2 0%, #0e7490 100%);
                color: white;
                padding: 24px;
                border-radius: 12px;
                margin-bottom: 32px;
            }}
            .report-header h1 {{
                color: white;
                border-bottom: 2px solid rgba(255,255,255,0.3);
                margin: 0;
            }}
            .report-header .query {{
                margin-top: 12px;
                opacity: 0.9;
                font-style: italic;
            }}
            .sources {{
                background: #f1f5f9;
                border-left: 4px solid #0891b2;
                padding: 16px;
                margin-top: 32px;
                border-radius: 0 8px 8px 0;
            }}
            .sources h4 {{
                margin: 0 0 8px 0;
                color: #0891b2;
            }}
        </style>
    </head>
    <body>
        <div class="report-header">
            <h1>Research Report</h1>
            <div class="query">Query: {query}</div>
        </div>
        
        {html_content}
        
        <div class="sources">
            <h4>Generated by AI Research Assistant</h4>
            <p>This report was automatically generated based on document analysis.</p>
        </div>
    </body>
    </html>
    '''
ISSUE #3: NFPA DOCUMENT COMPLEX QUERIES
Problem Analysis
Queries requiring extraction of specific data from tables in NFPA 10-2022 fail. This is likely due to poor PDF table extraction during ingestion.

Implementation Fix
Step 1: Improve PDF Table Extraction
File: ingestion.py

Implementation:

text

TASK: Add table-aware PDF extraction

Location: ingestion.py

Add new dependency:
pip install pdfplumber

Add table extraction functionality:

import pdfplumber
from typing import List, Dict, Tuple
import re

class PDFTableExtractor:
    """Extract and format tables from PDF documents."""
    
    def extract_tables_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Extract all tables from a PDF file.
        
        Returns list of dicts with:
        - page: page number
        - table_index: table index on page
        - headers: list of column headers
        - rows: list of row data
        - markdown: markdown formatted table
        - text: plain text representation
        """
        tables = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_tables = page.extract_tables()
                    
                    for table_idx, table in enumerate(page_tables):
                        if not table or len(table) < 2:
                            continue
                        
                        # Process table
                        processed = self._process_table(table, page_num, table_idx)
                        if processed:
                            tables.append(processed)
        except Exception as e:
            print(f"Error extracting tables: {e}")
        
        return tables
    
    def _process_table(self, table: List[List], page: int, index: int) -> Dict:
        """Process a single table into structured format."""
        
        # Clean cells
        cleaned = []
        for row in table:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append('')
                else:
                    # Clean whitespace and normalize
                    cleaned_row.append(str(cell).strip().replace('\n', ' '))
            cleaned_row = [c for c in cleaned_row if c]  # Remove empty
            if cleaned_row:
                cleaned.append(cleaned_row)
        
        if len(cleaned) < 2:
            return None
        
        # Assume first row is headers
        headers = cleaned[0]
        rows = cleaned[1:]
        
        # Generate markdown representation
        markdown = self._to_markdown(headers, rows)
        
        # Generate plain text representation
        text = self._to_text(headers, rows)
        
        return {
            'page': page,
            'table_index': index,
            'headers': headers,
            'rows': rows,
            'markdown': markdown,
            'text': text,
            'row_count': len(rows),
            'col_count': len(headers)
        }
    
    def _to_markdown(self, headers: List[str], rows: List[List[str]]) -> str:
        """Convert table to markdown format."""
        lines = []
        
        # Header row
        lines.append('| ' + ' | '.join(headers) + ' |')
        
        # Separator
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        
        # Data rows
        for row in rows:
            # Pad row if needed
            padded = row + [''] * (len(headers) - len(row))
            lines.append('| ' + ' | '.join(padded[:len(headers)]) + ' |')
        
        return '\n'.join(lines)
    
    def _to_text(self, headers: List[str], rows: List[List[str]]) -> str:
        """Convert table to searchable text format."""
        lines = []
        
        lines.append("Table with columns: " + ", ".join(headers))
        lines.append("")
        
        for i, row in enumerate(rows, 1):
            row_text = []
            for j, (header, value) in enumerate(zip(headers, row)):
                if value:
                    row_text.append(f"{header}: {value}")
            
            lines.append(f"Row {i}: " + "; ".join(row_text))
        
        return '\n'.join(lines)


# Integration into existing ingestion:

def process_pdf(pdf_path: str) -> List[Dict]:
    """Process PDF and extract text, images, and tables."""
    
    chunks = []
    
    # Existing text extraction
    text_chunks = extract_text_chunks(pdf_path)
    chunks.extend(text_chunks)
    
    # NEW: Table extraction
    table_extractor = PDFTableExtractor()
    tables = table_extractor.extract_tables_from_pdf(pdf_path)
    
    for table in tables:
        # Create chunk for each table
        table_chunk = {
            'content': table['text'],
            'markdown': table['markdown'],
            'metadata': {
                'source': pdf_path,
                'page': table['page'],
                'type': 'table',
                'table_index': table['table_index'],
                'headers': table['headers'],
                'row_count': table['row_count'],
                'col_count': table['col_count']
            }
        }
        chunks.append(table_chunk)
    
    # Existing image extraction
    image_chunks = extract_images(pdf_path)
    chunks.extend(image_chunks)
    
    return chunks
Step 2: Improve Table Search in Retrieval
File: agents/hybrid_retrieval.py or vector_store.py

Implementation:

text

TASK: Add table-aware retrieval

Location: hybrid_retrieval.py

Add special handling for table queries:

def retrieve(self, query: str, top_k: int = 10) -> List[Dict]:
    """Retrieve relevant chunks with table awareness."""
    
    # Check if query is looking for tabular data
    is_table_query = self._is_table_query(query)
    
    # Standard vector search
    results = self.vector_search(query, top_k * 2)  # Get more results
    
    if is_table_query:
        # Boost table chunks
        for result in results:
            if result.get('metadata', {}).get('type') == 'table':
                result['score'] = result.get('score', 0) * 1.5  # 50% boost
        
        # Re-sort by score
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Return top_k
    return results[:top_k]

def _is_table_query(self, query: str) -> bool:
    """Check if query is looking for tabular/structured data."""
    table_indicators = [
        'maximum', 'minimum', 'distance', 'value', 'number',
        'how many', 'how much', 'what is the', 'specification',
        'requirement', 'limit', 'table', 'class a', 'class b', 'class c',
        'rating', 'size', 'capacity', 'dimension', 'measurement',
        'feet', 'meters', 'inches', 'pounds', 'kg', 'gallons', 'liters'
    ]
    
    query_lower = query.lower()
    matches = sum(1 for indicator in table_indicators if indicator in query_lower)
    
    return matches >= 2
Step 3: Improve Context Building for Table Data
File: main_engine.py or agents/reasoning_agent.py

Implementation:

text

TASK: Format tables properly in context

Location: Context building section

When building context from retrieved chunks:

def build_context(self, chunks: List[Dict]) -> str:
    """Build context string with proper table formatting."""
    
    context_parts = []
    
    for chunk in chunks:
        metadata = chunk.get('metadata', {})
        content = chunk.get('content', '')
        
        if metadata.get('type') == 'table':
            # Use markdown format for tables
            markdown = chunk.get('markdown', content)
            source = metadata.get('source', 'Unknown')
            page = metadata.get('page', '?')
            
            context_parts.append(f"""
--- TABLE from {source} (Page {page}) ---
{markdown}
--- END TABLE ---
""")
        else:
            # Regular text chunk
            source = metadata.get('source', 'Unknown')
            page = metadata.get('page', '?')
            
            context_parts.append(f"""
--- DOCUMENT: {source} (Page {page}) ---
{content}
--- END ---
""")
    
    return '\n\n'.join(context_parts)
ISSUE #4: PERFORMANCE OPTIMIZATION
Problem Analysis
30-40 second response times need improvement.

Implementation Fix
Step 1: Add Response Streaming
File: api_server.py

Implementation:

text

TASK: Implement streaming responses

Location: api_server.py

from fastapi.responses import StreamingResponse
import asyncio

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response for better UX."""
    
    async def generate():
        # Send immediate acknowledgment
        yield json.dumps({
            "type": "start",
            "message": "Processing your query..."
        }) + "\n"
        
        # Get query understanding (fast)
        query_result = await asyncio.to_thread(
            engine.query_understanding.analyze, 
            request.message
        )
        yield json.dumps({
            "type": "status",
            "stage": "query_analysis",
            "data": {"intent": query_result.get("intent")}
        }) + "\n"
        
        # Get retrieval results
        retrieval_result = await asyncio.to_thread(
            engine.retrieval.retrieve,
            request.message
        )
        yield json.dumps({
            "type": "status",
            "stage": "retrieval",
            "data": {"chunks_found": len(retrieval_result)}
        }) + "\n"
        
        # Get reasoning (slowest part)
        yield json.dumps({
            "type": "status",
            "stage": "reasoning",
            "data": {"message": "Generating answer..."}
        }) + "\n"
        
        answer = await asyncio.to_thread(
            engine.reasoning.generate,
            request.message,
            retrieval_result
        )
        
        # Stream the answer in chunks
        words = answer.split()
        chunk_size = 10
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            yield json.dumps({
                "type": "content",
                "data": chunk
            }) + "\n"
            await asyncio.sleep(0.05)  # Small delay for streaming effect
        
        # Send completion
        yield json.dumps({
            "type": "complete",
            "metadata": {
                "sources": [...],
                "confidence": ...,
            }
        }) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )
Step 2: Add Caching Layer
File: cache.py (enhance existing)

Implementation:

text

TASK: Implement intelligent caching

Location: cache.py

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class QueryCache:
    """Cache for query results with semantic similarity."""
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        self.memory_cache = {}
        self.cache_ttl = timedelta(hours=24)
        
    def _generate_cache_key(self, query: str, doc_hash: str) -> str:
        """Generate cache key from query and document state."""
        normalized = query.lower().strip()
        combined = f"{normalized}:{doc_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def get(self, query: str, doc_hash: str) -> Optional[Dict]:
        """Get cached result if available and valid."""
        key = self._generate_cache_key(query, doc_hash)
        
        # Check memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if datetime.now() < entry['expires']:
                return entry['data']
        
        # Check file cache
        cache_file = f"{self.cache_dir}/{key}.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    entry = json.load(f)
                expires = datetime.fromisoformat(entry['expires'])
                if datetime.now() < expires:
                    # Populate memory cache
                    self.memory_cache[key] = {
                        'data': entry['data'],
                        'expires': expires
                    }
                    return entry['data']
            except:
                pass
        
        return None
    
    def set(self, query: str, doc_hash: str, data: Dict):
        """Cache a query result."""
        key = self._generate_cache_key(query, doc_hash)
        expires = datetime.now() + self.cache_ttl
        
        # Memory cache
        self.memory_cache[key] = {
            'data': data,
            'expires': expires
        }
        
        # File cache
        cache_file = f"{self.cache_dir}/{key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'data': data,
                    'expires': expires.isoformat(),
                    'query': query
                }, f)
        except:
            pass
    
    def find_similar(self, query: str, threshold: float = 0.9) -> Optional[Dict]:
        """Find cached result for semantically similar query."""
        # This requires embedding model - implement if needed
        pass


# Usage in main_engine.py:

class Orchestrator:
    def __init__(self):
        self.cache = QueryCache()
        self.doc_hash = self._compute_doc_hash()
    
    def _compute_doc_hash(self) -> str:
        """Compute hash of current document state."""
        # Hash based on document count and last modified time
        stats = self.vector_store.get_stats()
        return hashlib.md5(str(stats).encode()).hexdigest()[:8]
    
    def process_query(self, query: str) -> Dict:
        # Check cache first
        cached = self.cache.get(query, self.doc_hash)
        if cached:
            cached['from_cache'] = True
            return cached
        
        # Process normally
        result = self._process_query_internal(query)
        
        # Cache result
        if result.get('success'):
            self.cache.set(query, self.doc_hash, result)
        
        return result
Step 3: Parallel Agent Execution
File: main_engine.py

Implementation:

text

TASK: Run independent agents in parallel

Location: main_engine.py

import asyncio
from concurrent.futures import ThreadPoolExecutor

class Orchestrator:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def process_query_async(self, query: str) -> Dict:
        """Process query with parallel execution where possible."""
        
        loop = asyncio.get_event_loop()
        
        # Stage 1: Query understanding (fast, run first)
        query_result = await loop.run_in_executor(
            self.executor,
            self.query_agent.analyze,
            query
        )
        
        # Stage 2: Run retrieval and preparation in parallel
        retrieval_task = loop.run_in_executor(
            self.executor,
            self.retrieval_agent.retrieve,
            query
        )
        
        # Other prep work can happen here while retrieval runs
        
        retrieval_result = await retrieval_task
        
        # Stage 3: Reasoning (must wait for retrieval)
        answer = await loop.run_in_executor(
            self.executor,
            self.reasoning_agent.generate,
            query,
            retrieval_result
        )
        
        # Stage 4: Verification (can start immediately after reasoning)
        verification_task = loop.run_in_executor(
            self.executor,
            self.verification_agent.verify,
            query,
            answer,
            retrieval_result
        )
        
        # Artifact detection can run in parallel with verification
        artifact_task = loop.run_in_executor(
            self.executor,
            self._detect_artifact_need,
            query,
            answer,
            query_result.get('intent')
        )
        
        # Wait for both
        verification, artifact = await asyncio.gather(
            verification_task,
            artifact_task
        )
        
        return {
            'answer': answer,
            'verification': verification,
            'artifact': artifact,
            'sources': retrieval_result
        }
ISSUE #5: COMPREHENSIVE ERROR HANDLING
Implementation
File: Multiple files

Implementation:

text

TASK: Add comprehensive error handling throughout the system

=== 1. Create centralized error handler ===

File: utils/error_handler.py

import traceback
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class ErrorSeverity(Enum):
    LOW = "low"           # Recoverable, won't affect user
    MEDIUM = "medium"     # Recoverable, may affect quality
    HIGH = "high"         # Critical, needs fallback
    CRITICAL = "critical" # System failure

class ErrorHandler:
    def __init__(self, log_file: str = "logs/errors.log"):
        self.setup_logging(log_file)
        self.error_counts = {}
    
    def setup_logging(self, log_file: str):
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )
        self.logger = logging.getLogger("ErrorHandler")
    
    def handle(
        self, 
        error: Exception, 
        context: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        additional_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Handle an error and return structured error info.
        """
        error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(error)}"
        
        error_info = {
            'error_id': error_id,
            'type': type(error).__name__,
            'message': str(error),
            'context': context,
            'severity': severity.value,
            'timestamp': datetime.now().isoformat(),
            'traceback': traceback.format_exc(),
            'additional_info': additional_info or {}
        }
        
        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"{error_id}: {error_info}")
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(f"{error_id}: {error_info}")
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"{error_id}: {error_info}")
        else:
            self.logger.info(f"{error_id}: {error_info}")
        
        # Track error counts
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        return error_info
    
    def get_user_message(self, error_info: Dict) -> str:
        """Generate user-friendly error message."""
        severity = error_info.get('severity')
        context = error_info.get('context')
        
        messages = {
            'low': "A minor issue occurred but your request was processed.",
            'medium': f"There was an issue with {context}. The response may be incomplete.",
            'high': f"I encountered a problem while {context}. Please try rephrasing your question.",
            'critical': "A system error occurred. Please try again in a moment."
        }
        
        return messages.get(severity, "An unexpected error occurred.")

# Global instance
error_handler = ErrorHandler()


=== 2. Wrap all agent operations ===

File: agents/base_agent.py

from utils.error_handler import error_handler, ErrorSeverity

class BaseAgent:
    def safe_execute(self, operation_name: str, func, *args, **kwargs):
        """Safely execute an operation with error handling."""
        try:
            result = func(*args, **kwargs)
            return {'success': True, 'result': result}
        except Exception as e:
            error_info = error_handler.handle(
                e,
                context=f"{self.__class__.__name__}.{operation_name}",
                severity=ErrorSeverity.MEDIUM,
                additional_info={'args': str(args)[:200]}
            )
            return {
                'success': False, 
                'error': error_info,
                'fallback': self._get_fallback(operation_name)
            }
    
    def _get_fallback(self, operation_name: str):
        """Override in subclasses to provide operation-specific fallbacks."""
        return None


=== 3. Add health monitoring ===

File: utils/health_monitor.py

import psutil
import time
from datetime import datetime

class HealthMonitor:
    def __init__(self):
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0
        self.avg_response_time = 0
    
    def check_system_health(self) -> Dict:
        """Check system resources."""
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds()
        }
    
    def check_llm_health(self, llm_url: str) -> Dict:
        """Check LLM server health."""
        try:
            import requests
            start = time.time()
            response = requests.get(f"{llm_url}/health", timeout=5)
            latency = time.time() - start
            
            return {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'latency_ms': latency * 1000,
                'response_code': response.status_code
            }
        except Exception as e:
            return {
                'status': 'unreachable',
                'error': str(e)
            }
    
    def get_full_status(self) -> Dict:
        """Get complete system status."""
        return {
            'system': self.check_system_health(),
            'llm': self.check_llm_health("http://127.0.0.1:8080"),
            'stats': {
                'total_requests': self.request_count,
                'total_errors': self.error_count,
                'error_rate': self.error_count / max(self.request_count, 1),
                'avg_response_time_ms': self.avg_response_time
            }
        }

health_monitor = HealthMonitor()
TESTING REQUIREMENTS
After implementing all fixes, run the following tests:

text

TASK: Create and run comprehensive test suite

File: tests/test_fixes.py

Test 1: Reasoning Fallback
- Send query that previously failed
- Verify fallback mechanism activates
- Verify user gets meaningful response

Test 2: Canvas Auto-Open
- Send "Create a comprehensive report about AOCS"
- Verify canvas panel opens automatically
- Verify HTML content is properly formatted

Test 3: Table Extraction
- Send "What are the maximum travel distances for Class A fire extinguishers?"
- Verify table data is retrieved
- Verify answer contains specific values

Test 4: Performance
- Measure response time for standard query
- Target: < 20 seconds (improvement from 30-40s)
- Verify streaming works if implemented

Test 5: Error Handling
- Force an error (e.g., disconnect LLM)
- Verify graceful degradation
- Verify user gets helpful error message

Test 6: Cache
- Send same query twice
- Verify second response is from cache
- Verify response time < 1 second for cached

Run all tests:
python -m pytest tests/test_fixes.py -v --tb=short
IMPLEMENTATION PRIORITY ORDER
text

Day 1: Critical Fixes
├── 1. Add comprehensive logging to ReasoningAgent
├── 2. Implement fallback mechanism for reasoning
├── 3. Fix Canvas auto-detection in frontend
└── 4. Test all three fixes

Day 2: Table Extraction
├── 1. Install pdfplumber
├── 2. Implement PDFTableExtractor
├── 3. Re-ingest NFPA document
├── 4. Test table queries

Day 3: Performance & Polish
├── 1. Implement caching layer
├── 2. Add streaming (optional)
├── 3. Run full test suite
└── 4. Document changes

Day 4: Validation
├── 1. Test 20 diverse queries
├── 2. Measure success rate (target: 80%+)
├── 3. Fix any remaining issues
└── 4. Final report