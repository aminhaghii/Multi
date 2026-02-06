import os
import requests
import json
import time
import asyncio  # BUG-013 FIX: For async operations
from pathlib import Path

class LLMClient:
    """LLM Client for Llama-3 GGUF model"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080", multimodal_base_url: str = "http://127.0.0.1:8082"):
        self.base_url = base_url
        self.multimodal_base_url = multimodal_base_url
        self.model = None
        self._try_load_direct_model()
    
    def _try_load_direct_model(self):
        """Try to load model directly from local GGUF file"""
        # Check environment variable first, then common paths
        model_path = os.environ.get("GGUF_MODEL_PATH", "")
        if not model_path or not Path(model_path).exists():
            candidate_paths = [
                "./models/mimo-vl/MiMo-VL-7B-RL-2508.Q4_K_M.gguf",
                "./models/llama3/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
            ]
            for candidate in candidate_paths:
                if Path(candidate).exists():
                    model_path = candidate
                    break
        
        if Path(model_path).exists():
            try:
                # Try to import and load llama-cpp-python
                from llama_cpp import Llama
                
                print("Loading Llama-3 model directly...")
                self.model = Llama(
                    model_path=model_path,
                    n_ctx=8192,
                    n_gpu_layers=35,
                    temperature=0.1,
                    verbose=False
                )
                print("Llama-3 loaded successfully!")
                return True
                
            except ImportError:
                print("llama-cpp-python not available, falling back to HTTP")
            except Exception as e:
                print(f"Failed to load Llama-3 directly: {e}")
        
        return False
    
    def health_check(self):
        """Check if LLM is available"""
        if self.model:
            return True
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except (requests.RequestException, Exception):
            return False
    
    def multimodal_health_check(self):
        """Check if multimodal server is available"""
        try:
            response = requests.get(f"{self.multimodal_base_url}/health", timeout=5)
            return response.status_code == 200
        except (requests.RequestException, Exception):
            return False
    
    def generate(self, prompt: str, max_tokens: int = 400, temperature: float = 0.6, top_p: float = 0.9, stop: list = None, max_retries: int = 3):
        """Generate response from LLM with retry logic and validation"""
        
        # Use direct model if available
        if self.model:
            try:
                response = self.model(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop or ["<|eot_id|>", "<|end_of_text|>"]
                )
                
                answer = response['choices'][0]['text'].strip()
                
                # Validate response
                if not answer or len(answer) < 20:
                    raise ValueError("Empty or too short response from direct model")
                
                return {
                    "success": True,
                    "text": answer,
                    "model": "Llama-3-8B-Instruct (direct)"
                }
                
            except Exception as e:
                print(f"Direct generation failed: {e}")
        
        # Fallback to HTTP with retry logic
        
        for attempt in range(max_retries):
            try:
                payload = {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p
                }
                
                if stop:
                    payload["stop"] = stop
                
                response = requests.post(
                    f"{self.base_url}/completion",
                    json=payload,
                    timeout=60  # Increased timeout for complex reasoning
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("content", "").strip()
                    
                    # Validate response
                    if not text or len(text) < 20:
                        raise ValueError("Empty or too short response")
                    
                    return {
                        "success": True,
                        "text": text,
                        "model": result.get("model", "unknown")
                    }
                else:
                    if attempt < max_retries - 1:
                        print(f"HTTP {response.status_code} on attempt {attempt + 1}, retrying...")
                        # BUG-014 FIX: Cap sleep time at 30 seconds
                        time.sleep(min(30, 2 ** attempt))
                        continue
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
            except (requests.Timeout, requests.ConnectionError) as e:
                if attempt < max_retries - 1:
                    print(f"Connection error on attempt {attempt + 1}, retrying...")
                    # BUG-014 FIX: Cap sleep time at 30 seconds
                    time.sleep(min(30, 2 ** attempt))
                    continue
                return {
                    "success": False,
                    "error": f"Max retries exceeded: {str(e)}"
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": False,
            "error": "All retry attempts failed"
        }
    
    def generate_with_images(self, prompt: str, image_paths: list, max_tokens: int = 400, temperature: float = 0.6):
        """Generate response with images (multimodal)"""
        # This still uses the multimodal server
        try:
            # Convert images to base64
            import base64
            
            images_data = []
            for img_path in image_paths:
                if os.path.exists(img_path):
                    # BUG-015 FIX: Check file size before loading to prevent memory spike
                    file_size = os.path.getsize(img_path)
                    if file_size > 5 * 1024 * 1024:  # 5MB limit
                        raise ValueError(f"Image too large: {img_path} ({file_size / 1024 / 1024:.1f}MB > 5MB limit)")
                    with open(img_path, 'rb') as f:
                        img_data = base64.b64encode(f.read()).decode('utf-8')
                        images_data.append(img_data)
            
            payload = {
                "prompt": prompt,
                "images": images_data,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = requests.post(
                f"{self.multimodal_base_url}/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "text": result.get("text", ""),
                    "model": result.get("model", "multimodal")
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
