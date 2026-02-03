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
    
    def _chunk_text(self, text: str) -> List[str]:
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk = ' '.join(words[i:i + self.chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
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
        filename_base = os.path.splitext(filename)[0]
        
        with open(pdf_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        
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
    
    def process_directory(self, directory_path: str):
        pdf_files = [f for f in os.listdir(directory_path) if f.endswith('.pdf')]
        
        results = []
        for pdf_file in pdf_files:
            pdf_path = os.path.join(directory_path, pdf_file)
            try:
                result = self.process_pdf(pdf_path)
                results.append(result)
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
                results.append({"file": pdf_file, "status": "error", "error": str(e)})
        
        return results
