import os
import torch

class VoiceTranscriber:
    def __init__(self, model_size="tiny"):
        self.model_size = model_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        try:
            import whisper
            print(f"Loading Whisper {model_size} model on {self.device}...")
            self.model = whisper.load_model(model_size, device=self.device)
            print("Whisper model loaded successfully")
        except ImportError:
            print("Warning: openai-whisper not installed. Install with: pip install openai-whisper")
        except Exception as e:
            print(f"Warning: Failed to load Whisper model: {e}")
    
    def transcribe(self, audio_path: str) -> str:
        if not os.path.exists(audio_path):
            return f"Error transcribing audio: File not found: {audio_path}"
        
        if self.model is None:
            return "Error transcribing audio: Whisper model not loaded. Install openai-whisper."
        
        try:
            result = self.model.transcribe(audio_path, fp16=(self.device == "cuda"))
            text = result.get("text", "").strip()
            if not text:
                return "Error transcribing audio: No speech detected in audio file."
            return text
        except Exception as e:
            return f"Error transcribing audio: {str(e)}"
