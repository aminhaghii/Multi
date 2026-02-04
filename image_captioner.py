import os
os.environ["TRANSFORMERS_NO_TF"] = "1"

from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

class ImageCaptioner:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading BLIP image captioning model on {self.device}...")
        
        # Use local cache for offline operation
        import os
        cache_dir = os.path.join(os.path.dirname(__file__), 'model_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        self.processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=cache_dir
        )
        self.model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=cache_dir,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        ).to(self.device)
        
        print("BLIP model loaded successfully")
    
    def _clean_caption(self, caption: str) -> str:
        """
        Remove excessive repetition (e.g., 'neural neural neural ...').
        """
        words = caption.strip().split()
        cleaned = []
        prev = None
        repeat_count = 0
        for w in words:
            if w == prev:
                repeat_count += 1
                if repeat_count >= 2:
                    continue
            else:
                repeat_count = 0
            cleaned.append(w)
            prev = w
        return " ".join(cleaned)

    def caption_image(self, image_path: str) -> str:
        try:
            image = Image.open(image_path).convert('RGB')
            
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=40,
                    num_beams=3,
                    no_repeat_ngram_size=3,
                    repetition_penalty=1.2
                )
            
            caption = self.processor.decode(outputs[0], skip_special_tokens=True)
            caption = self._clean_caption(caption)
            
            return caption
        except Exception as e:
            return f"Error captioning image: {str(e)}"
    
    def caption_multiple(self, image_paths: list) -> list:
        captions = []
        for path in image_paths:
            caption = self.caption_image(path)
            captions.append(caption)
        return captions
