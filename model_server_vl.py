import os
os.environ["TRANSFORMERS_NO_TF"] = "1"

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import torch
from transformers import AutoProcessor, AutoModelForCausalLM, BitsAndBytesConfig
from PIL import Image
import io
import base64
import uvicorn
from contextlib import asynccontextmanager

class GenerationRequest(BaseModel):
    prompt: str
    images: Optional[List[str]] = None
    max_tokens: int = 512
    temperature: float = 0.7

class GenerationResponse(BaseModel):
    content: str
    success: bool

model = None
processor = None
device = None

# MiMo-VL repo with processor/tokenizer included
MODEL_ID = "XiaomiMiMo/MiMo-VL-7B-RL-2508"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    global model, processor, device

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Loading MiMo-VL model: {MODEL_ID}")
    print("This may take several minutes on first run...")

    try:
        processor = AutoProcessor.from_pretrained(
            MODEL_ID,
            trust_remote_code=True
        )

        if device == "cuda":
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )

            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.float32,
                trust_remote_code=True
            ).to(device)

        print("MiMo-VL model loaded successfully!")

    except Exception as e:
        print(f"Error loading model: {e}")
        model = None
        processor = None

    yield  # Application runs here


app = FastAPI(title="MiMo-VL Multimodal Server", lifespan=lifespan)

@app.get("/health")
async def health_check():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "status": "healthy",
        "model_loaded": True,
        "device": device
    }

@app.post("/v1/chat/completions", response_model=GenerationResponse)
async def generate_completion(request: GenerationRequest):
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        images_pil = []
        if request.images:
            for img_data in request.images:
                if img_data.startswith("data:"):
                    img_data = img_data.split(",", 1)[1]
                
                img_bytes = base64.b64decode(img_data)
                img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                images_pil.append(img)
        
        if images_pil:
            inputs = processor(
                text=request.prompt,
                images=images_pil,
                return_tensors="pt"
            )
        else:
            inputs = processor(
                text=request.prompt,
                return_tensors="pt"
            )
        
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            gen_kwargs = {
                **inputs,
                "max_new_tokens": request.max_tokens,
                "pad_token_id": processor.tokenizer.eos_token_id,
            }
            if request.temperature > 0:
                gen_kwargs["do_sample"] = True
                gen_kwargs["temperature"] = request.temperature
            else:
                gen_kwargs["do_sample"] = False
            outputs = model.generate(**gen_kwargs)
        
        input_len = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_len:]
        generated_text = processor.decode(generated_tokens, skip_special_tokens=True)
        
        return GenerationResponse(content=generated_text.strip(), success=True)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

@app.post("/completion", response_model=GenerationResponse)
async def generate_simple(request: GenerationRequest):
    return await generate_completion(request)

@app.post("/generate")
async def generate_endpoint(request: GenerationRequest):
    """Endpoint used by llm_client.generate_with_images()"""
    result = await generate_completion(request)
    return {"text": result.content, "model": "MiMo-VL-7B", "success": result.success}

if __name__ == "__main__":
    print("Starting MiMo-VL Multimodal Server on port 8082...")
    uvicorn.run(app, host="127.0.0.1", port=8082)
