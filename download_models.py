"""
Pre-download all required models for offline usage.
Run this ONCE with internet connection before going offline.
"""

import os
from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

def download_models():
    print("=" * 70)
    print("DOWNLOADING ALL MODELS FOR OFFLINE USE")
    print("=" * 70)
    print("\nThis will download ~500MB of models.")
    print("Run this ONCE with internet, then you can go fully offline.\n")
    
    # Create cache directory
    cache_dir = "./model_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # 1. Download Sentence Transformer (Embedding Model)
    print("\n[1/2] Downloading Sentence Transformer (all-MiniLM-L6-v2)...")
    try:
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', cache_folder=cache_dir)
        print("✅ Sentence Transformer downloaded successfully")
    except Exception as e:
        print(f"❌ Failed to download Sentence Transformer: {e}")
    
    # 2. Download BLIP Image Captioning Model
    print("\n[2/2] Downloading BLIP Image Captioning Model...")
    try:
        processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=cache_dir
        )
        model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=cache_dir,
            torch_dtype=torch.float32
        )
        print("✅ BLIP Model downloaded successfully")
    except Exception as e:
        print(f"❌ Failed to download BLIP: {e}")
    
    print("\n" + "=" * 70)
    print("✅ ALL MODELS DOWNLOADED!")
    print("=" * 70)
    print("\nYou can now run the project OFFLINE.")
    print("Models are cached in: ./model_cache and ~/.cache/huggingface/\n")

if __name__ == "__main__":
    download_models()
