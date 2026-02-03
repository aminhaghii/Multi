import sys
import os
import requests
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, '.')

class LLMClient:
    """LLM Client for Llama-3 GGUF model"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080", multimodal_base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url
        self.multimodal_base_url = multimodal_base_url
        self.model = None
        self._try_load_direct_model()
    
    def _try_load_direct_model(self):
        """Try to load Llama-3 model directly"""
        model_path = "./models/llama3/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
        
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
        except:
            return False
    
    def multimodal_health_check(self):
        """Check if multimodal server is available"""
        try:
            response = requests.get(f"{self.multimodal_base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def generate(self, prompt: str, max_tokens: int = 400, temperature: float = 0.6, top_p: float = 0.9, stop: list = None):
        """Generate response from LLM"""
        
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
                
                return {
                    "success": True,
                    "text": answer,
                    "model": "Llama-3-8B-Instruct (direct)"
                }
                
            except Exception as e:
                print(f"Direct generation failed: {e}")
        
        # Fallback to HTTP
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
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "text": result.get("content", ""),
                    "model": result.get("model", "unknown")
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
    
    def generate_with_images(self, prompt: str, image_paths: list, max_tokens: int = 400, temperature: float = 0.6):
        """Generate response with images (multimodal)"""
        # This still uses the multimodal server
        try:
            # Convert images to base64
            import base64
            
            images_data = []
            for img_path in image_paths:
                if os.path.exists(img_path):
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
