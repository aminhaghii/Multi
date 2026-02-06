import fitz  # PyMuPDF
from PIL import Image
import io
import os
import re
from typing import List, Dict, Any, Tuple, Optional
from vector_store import VectorStore
import hashlib
from tqdm import tqdm

class DocumentProcessor:
    """
    Enhanced Document Processor with Multimodal Image Retrieval
    - Extracts images from PDFs and saves to static directory
    - Detects figure captions and links them to images
    - Provides proper metadata for source attribution
    """
    
    def __init__(self, vector_store: VectorStore, chunk_size: int = 800, chunk_overlap: int = 160):
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.images_dir = "./static/images"  # Changed to static for web serving
        self.extracted_images_dir = "./extracted_images"  # Legacy compatibility
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.extracted_images_dir, exist_ok=True)
        
        # Caption detection patterns
        self.caption_patterns = [
            r'(?i)figure\s*\d+[:\.\-\s]',
            r'(?i)fig\.\s*\d+[:\.\-\s]',
            r'(?i)diagram\s*\d+[:\.\-\s]',
            r'(?i)image\s*\d+[:\.\-\s]',
            r'(?i)chart\s*\d+[:\.\-\s]',
            r'(?i)table\s*\d+[:\.\-\s]',
        ]
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal attacks."""
        # Get just the basename (remove any path components)
        base = os.path.basename(filename)
        # Remove extension
        base = os.path.splitext(base)[0]
        # Replace any dangerous characters with underscore
        # Only allow alphanumeric, spaces, hyphens, and underscores
        safe = re.sub(r'[^\w\s-]', '_', base)
        # Remove any leading/trailing whitespace
        safe = safe.strip()
        # Ensure not empty
        if not safe:
            safe = "unnamed_document"
        return safe

    def _chunk_text(self, text: str) -> List[str]:
        # Character-based chunking with word boundary awareness
        # chunk_size and chunk_overlap are now treated as character counts
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + self.chunk_size
            if end < text_len:
                # Try to break at a word boundary (space, newline)
                boundary = text.rfind(' ', start + self.chunk_size // 2, end)
                if boundary != -1:
                    end = boundary
            else:
                end = text_len
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap if end < text_len else text_len
        
        return chunks
    
    def _detect_caption(self, text: str) -> Optional[str]:
        """Detect if text contains a figure/diagram caption"""
        for pattern in self.caption_patterns:
            match = re.search(pattern, text)
            if match:
                # Extract the full caption (up to end of sentence or 200 chars)
                start = match.start()
                end_match = re.search(r'[.!?\n]', text[start:start+200])
                end = start + (end_match.end() if end_match else 200)
                return text[start:end].strip()
        return None
    
    def _extract_images_pymupdf(self, doc: fitz.Document, file_hash: str, filename_base: str) -> Dict[int, List[Dict]]:
        """
        Extract images from PDF using PyMuPDF with better quality
        Returns: Dict mapping page_num -> list of image info dicts
        """
        page_images = {}
        
        # Create document-specific image directory
        doc_images_dir = os.path.join(self.images_dir, filename_base)
        os.makedirs(doc_images_dir, exist_ok=True)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            page_images[page_num] = []
            render_matrix = fitz.Matrix(2, 2)
            rendered_page_image = None
            if image_list:
                page_pixmap = page.get_pixmap(matrix=render_matrix, alpha=False)
                rendered_page_image = Image.frombytes(
                    "RGB",
                    (page_pixmap.width, page_pixmap.height),
                    page_pixmap.samples,
                )
            
            for img_idx, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    
                    if base_image:
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"].lower()
                        
                        # Filter out tiny images (likely icons/decorations)
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)
                        if width < 50 or height < 50:
                            continue

                        # Prefer rendering from page to preserve white background
                        image = None
                        if rendered_page_image:
                            rects = page.get_image_rects(xref)
                            if rects:
                                rect = rects[0] * render_matrix
                                crop_box = (
                                    int(rect.x0),
                                    int(rect.y0),
                                    int(rect.x1),
                                    int(rect.y1),
                                )
                                image = rendered_page_image.crop(crop_box)
                                image_ext = "png"

                        if image is None:
                            # Fallback: open via PIL to normalize mode and handle transparency
                            image = Image.open(io.BytesIO(image_bytes))
                            has_alpha = image.mode in ("RGBA", "LA") or (
                                image.mode == "P" and "transparency" in image.info
                            )

                            if has_alpha:
                                # Flatten transparency over white background to avoid black
                                if image.mode != "RGBA":
                                    image = image.convert("RGBA")
                                background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                                background.paste(image, mask=image.split()[-1])
                                image = background.convert("RGB")
                                image_ext = "png"
                            else:
                                # Ensure consistent RGB output
                                image = image.convert("RGB")

                        # Save image (force PNG when transparency handled)
                        img_filename = f"page{page_num+1}_img{img_idx+1}.{image_ext}"
                        img_path = os.path.join(doc_images_dir, img_filename)

                        image.save(img_path, format=image_ext.upper())
                        width, height = image.size
                        
                        # Web-accessible path
                        web_path = f"/static/images/{filename_base}/{img_filename}"
                        
                        page_images[page_num].append({
                            "local_path": img_path,
                            "web_path": web_path,
                            "width": width,
                            "height": height,
                            "page": page_num
                        })
                        
                except Exception as e:
                    print(f"Error extracting image {img_idx} from page {page_num}: {e}")
                    continue
        
        return page_images
    
    def _find_caption_for_chunk(self, chunk_text: str) -> Optional[str]:
        """Find any figure/table caption in the chunk text"""
        return self._detect_caption(chunk_text)
    
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process PDF with enhanced image extraction and caption detection
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        print(f"Processing PDF: {pdf_path}")
        filename = os.path.basename(pdf_path)
        filename_base = self._sanitize_filename(filename)
        
        with open(pdf_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:8]
        
        # Use PyMuPDF for processing
        doc = fitz.open(pdf_path)
        
        # Extract all images first
        print("Extracting images...")
        page_images = self._extract_images_pymupdf(doc, file_hash, filename_base)
        total_images = sum(len(imgs) for imgs in page_images.values())
        print(f"Extracted {total_images} images from {len(doc)} pages")
        
        all_texts = []
        all_metadatas = []
        all_ids = []
        
        for page_num in tqdm(range(len(doc)), desc="Processing pages"):
            page = doc[page_num]
            text = page.get_text()
            
            if text.strip():
                chunks = self._chunk_text(text)
                images_on_page = page_images.get(page_num, [])
                
                for chunk_idx, chunk in enumerate(chunks):
                    chunk_id = f"{file_hash}_p{page_num}_c{chunk_idx}"
                    
                    # Check if this chunk contains a caption
                    caption = self._find_caption_for_chunk(chunk)
                    has_image = False
                    image_path = ""
                    image_web_path = ""
                    
                    # If chunk has caption and page has images, link them
                    if caption and images_on_page:
                        has_image = True
                        # Use the first/most relevant image on the page
                        image_path = images_on_page[0]["local_path"]
                        image_web_path = images_on_page[0]["web_path"]
                    elif images_on_page and chunk_idx == 0:
                        # First chunk of a page with images
                        has_image = True
                        image_path = images_on_page[0]["local_path"]
                        image_web_path = images_on_page[0]["web_path"]
                    
                    # Build legacy images string for compatibility
                    legacy_images = ",".join([img["local_path"] for img in images_on_page]) if images_on_page else ""
                    
                    metadata = {
                        "source": pdf_path,
                        "filename": filename,
                        "page": page_num,
                        "chunk_index": chunk_idx,
                        "file_hash": file_hash,
                        "images": legacy_images,
                        "has_image": has_image,
                        "image_path": image_web_path,
                        "caption": caption or ""
                    }
                    
                    all_texts.append(chunk)
                    all_metadatas.append(metadata)
                    all_ids.append(chunk_id)
        
        num_pages = len(doc)
        doc.close()
        
        # FIX 2: Create separate vector chunks for images
        # This ensures images are retrievable via caption search
        # Use multiple search keys to improve discoverability
        image_chunks_added = 0
        for page_num, images in page_images.items():
            for img_idx, img_info in enumerate(images):
                # Find caption from nearby text chunks
                caption = ""
                page_text_context = ""
                for idx, meta in enumerate(all_metadatas):
                    if meta.get('page') == page_num:
                        if meta.get('caption'):
                            caption = meta['caption']
                        # Get first 100 words of page text for context
                        if idx < len(all_texts):
                            page_text_context = ' '.join(all_texts[idx].split()[:100])
                        break
                
                # Create highly searchable image chunk with multiple keywords
                if not caption:
                    caption = f"Figure diagram image from page {page_num + 1}"
                
                # Build comprehensive search text for image retrieval
                image_text = f"""[IMAGE SEARCH KEY] {caption}
Visual content: figure diagram chart image illustration architecture block diagram
Source: {filename} page {page_num + 1}
Context: {page_text_context[:200] if page_text_context else 'Document visual content'}
This is an image/figure that can be displayed with markdown."""
                
                image_id = f"{file_hash}_img_p{page_num}_i{img_idx}"
                image_metadata = {
                    "source": pdf_path,
                    "filename": filename,
                    "page": page_num,
                    "file_hash": file_hash,
                    "type": "image",
                    "has_image": True,
                    "image_path": img_info["web_path"],
                    "caption": caption
                }
                
                all_texts.append(image_text)
                all_metadatas.append(image_metadata)
                all_ids.append(image_id)
                image_chunks_added += 1
        
        if image_chunks_added > 0:
            print(f"Created {image_chunks_added} searchable image chunks")
        
        if all_texts:
            print(f"Adding {len(all_texts)} total chunks to vector store...")
            self.vector_store.add_documents(all_texts, all_metadatas, all_ids)
        
        chunks_with_images = sum(1 for m in all_metadatas if m.get('has_image'))
        
        return {
            "file_hash": file_hash,
            "filename": filename,
            "num_pages": num_pages,
            "num_chunks": len(all_texts),
            "num_images": total_images,
            "image_chunks": image_chunks_added,
            "chunks_with_images": chunks_with_images,
            "status": "success"
        }

    def process_word(self, docx_path: str) -> Dict[str, Any]:
        """Process Word document (.docx/.doc) and add to vector store"""
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise ImportError("python-docx is required. Install with: pip install python-docx")

        filename = os.path.basename(docx_path)
        file_hash = self._generate_file_hash(docx_path)

        doc = DocxDocument(docx_path)
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

        chunks = self._chunk_text(full_text)
        all_texts = []
        all_metadatas = []
        all_ids = []

        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{file_hash}_chunk_{chunk_idx}"
            metadata = {
                "source": docx_path,
                "filename": filename,
                "page": 0,
                "chunk_index": chunk_idx,
                "file_hash": file_hash,
                "type": "word"
            }
            all_texts.append(chunk)
            all_metadatas.append(metadata)
            all_ids.append(chunk_id)

        if all_texts:
            self.vector_store.add_documents(all_texts, all_metadatas, all_ids)

        return {"num_chunks": len(all_texts), "filename": filename, "status": "success"}

    def process_markdown(self, md_path: str) -> Dict[str, Any]:
        """Process Markdown file (.md) and add to vector store"""
        filename = os.path.basename(md_path)
        file_hash = self._generate_file_hash(md_path)

        with open(md_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

        chunks = self._chunk_text(full_text)
        all_texts = []
        all_metadatas = []
        all_ids = []

        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{file_hash}_chunk_{chunk_idx}"
            metadata = {
                "source": md_path,
                "filename": filename,
                "page": 0,
                "chunk_index": chunk_idx,
                "file_hash": file_hash,
                "type": "markdown"
            }
            all_texts.append(chunk)
            all_metadatas.append(metadata)
            all_ids.append(chunk_id)

        if all_texts:
            self.vector_store.add_documents(all_texts, all_metadatas, all_ids)

        return {"num_chunks": len(all_texts), "filename": filename, "status": "success"}

    def process_text(self, txt_path: str) -> Dict[str, Any]:
        """Process plain text file (.txt) and add to vector store"""
        filename = os.path.basename(txt_path)
        file_hash = self._generate_file_hash(txt_path)

        with open(txt_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

        chunks = self._chunk_text(full_text)
        all_texts = []
        all_metadatas = []
        all_ids = []

        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{file_hash}_chunk_{chunk_idx}"
            metadata = {
                "source": txt_path,
                "filename": filename,
                "page": 0,
                "chunk_index": chunk_idx,
                "file_hash": file_hash,
                "type": "text"
            }
            all_texts.append(chunk)
            all_metadatas.append(metadata)
            all_ids.append(chunk_id)

        if all_texts:
            self.vector_store.add_documents(all_texts, all_metadatas, all_ids)

        return {"num_chunks": len(all_texts), "filename": filename, "status": "success"}

    def process_rtf(self, rtf_path: str) -> Dict[str, Any]:
        """Process RTF file and add to vector store"""
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError:
            raise ImportError("striprtf is required. Install with: pip install striprtf")

        filename = os.path.basename(rtf_path)
        file_hash = self._generate_file_hash(rtf_path)

        with open(rtf_path, 'r', encoding='utf-8', errors='ignore') as f:
            rtf_content = f.read()

        full_text = rtf_to_text(rtf_content)

        chunks = self._chunk_text(full_text)
        all_texts = []
        all_metadatas = []
        all_ids = []

        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{file_hash}_chunk_{chunk_idx}"
            metadata = {
                "source": rtf_path,
                "filename": filename,
                "page": 0,
                "chunk_index": chunk_idx,
                "file_hash": file_hash,
                "type": "rtf"
            }
            all_texts.append(chunk)
            all_metadatas.append(metadata)
            all_ids.append(chunk_id)

        if all_texts:
            self.vector_store.add_documents(all_texts, all_metadatas, all_ids)

        return {"num_chunks": len(all_texts), "filename": filename, "status": "success"}

    def _generate_file_hash(self, file_path: str) -> str:
        """Generate hash for any file"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    
    def process_directory(self, directory_path: str):
        supported_extensions = ['.pdf', '.docx', '.doc', '.md', '.txt', '.rtf']
        files = [f for f in os.listdir(directory_path)
                 if any(f.lower().endswith(ext) for ext in supported_extensions)]

        results = []
        for file in files:
            file_path = os.path.join(directory_path, file)
            ext = os.path.splitext(file)[1].lower()
            try:
                if ext == '.pdf':
                    result = self.process_pdf(file_path)
                elif ext in ['.docx', '.doc']:
                    result = self.process_word(file_path)
                elif ext == '.md':
                    result = self.process_markdown(file_path)
                elif ext == '.txt':
                    result = self.process_text(file_path)
                elif ext == '.rtf':
                    result = self.process_rtf(file_path)
                else:
                    raise ValueError(f"Unsupported extension: {ext}")
                results.append(result)
            except Exception as e:
                print(f"Error processing {file}: {e}")
                results.append({"file": file, "status": "error", "error": str(e)})

        return results
