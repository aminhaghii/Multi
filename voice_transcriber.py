import whisper
import torch

class VoiceTranscriber:
    def __init__(self, model_size="tiny"):
        self.model_size = model_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading Whisper {model_size} model on {self.device}...")
        self.model = whisper.load_model(model_size, device=self.device)
        print("Whisper model loaded successfully")
    
    def transcribe(self, audio_path: str) -> str:
        try:
            result = self.model.transcribe(audio_path, fp16=(self.device=="cuda"))
            return result["text"].strip()
        except Exception as e:
            return f"Error transcribing audio: {str(e)}"
