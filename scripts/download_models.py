<<<<<<< C:/Users/aminh/OneDrive/Desktop/Multi_agent/scripts/download_models.py
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
=======
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
    
    # 0. Download DeepSeek-R1 IQ4_XS GGUF (optimized for RTX 4050 6GB VRAM)
    print("\n[0/2] Downloading DeepSeek-R1-Distill-Qwen-14B-IQ4_XS GGUF...")
    try:
        gguf_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "deepseek")
        os.makedirs(gguf_dir, exist_ok=True)
        gguf_path = os.path.join(gguf_dir, "DeepSeek-R1-Distill-Qwen-14B-IQ4_XS.gguf")
        if os.path.exists(gguf_path):
            size_gb = os.path.getsize(gguf_path) / (1024**3)
            print(f"\u2705 IQ4_XS GGUF already exists ({size_gb:.2f} GB)")
        else:
            print(f"Downloading to {gguf_dir}...")
            print("Run manually: huggingface-cli download bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF "
                  '--include "DeepSeek-R1-Distill-Qwen-14B-IQ4_XS.gguf" '
                  f'--local-dir "{gguf_dir}"')
            import subprocess
            subprocess.run([
                "huggingface-cli", "download",
                "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
                "--include", "DeepSeek-R1-Distill-Qwen-14B-IQ4_XS.gguf",
                "--local-dir", gguf_dir
            ], check=True)
            print("\u2705 IQ4_XS GGUF downloaded successfully")
    except Exception as e:
        print(f"\u274c Failed to download IQ4_XS GGUF: {e}")
        print("You can download manually from: https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF")
    
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
>>>>>>> C:/Users/aminh/.windsurf/worktrees/Multi_agent/Multi_agent-b3f5a2b7/scripts/download_models.py
