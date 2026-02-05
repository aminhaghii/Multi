import os
os.environ["TRANSFORMERS_NO_TF"] = "1"

from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from pathlib import Path

class ImageCaptioner:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading BLIP image captioning model on {self.device}...")
        
        # Use local cache for offline operation
        cache_dir = os.path.join(os.path.dirname(__file__), 'model_cache')
        os.makedirs(cache_dir, exist_ok=True)

        local_path = self._resolve_local_snapshot(
            cache_dir,
            'Salesforce/blip-image-captioning-base'
        )
        model_source = local_path if local_path else "Salesforce/blip-image-captioning-base"
        load_kwargs = {}
        if not local_path:
            load_kwargs["cache_dir"] = cache_dir
        
        self.processor = BlipProcessor.from_pretrained(
            model_source,
            **load_kwargs
        )
        self.model = BlipForConditionalGeneration.from_pretrained(
            model_source,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            **load_kwargs
        ).to(self.device)
        
        print("BLIP model loaded successfully")

    def _resolve_local_snapshot(self, cache_dir: str, repo_id: str) -> str:
        """Return path to first local snapshot of a HF repo if exists."""
        safe_repo = repo_id.replace('/', '--')
        repo_root = Path(cache_dir) / f"models--{safe_repo}"
        snapshots_dir = repo_root / "snapshots"
        if snapshots_dir.is_dir():
            for snap in snapshots_dir.iterdir():
                if snap.is_dir():
                    return str(snap)
        return ""
    
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
