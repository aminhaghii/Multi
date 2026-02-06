"""
Application Settings
Central configuration for the Agentic Research Assistant
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = BASE_DIR / "agent_workspace"
EXPORTS_DIR = BASE_DIR / "exports"
STATIC_DIR = BASE_DIR / "static"


class Settings:
    """Application settings manager"""
    
    def __init__(self):
        self.base_dir = BASE_DIR
        self.config_dir = CONFIG_DIR
        self.data_dir = DATA_DIR
        self.workspace_dir = WORKSPACE_DIR
        self.exports_dir = EXPORTS_DIR
        self.static_dir = STATIC_DIR
        
        self.llm_server_url = os.getenv("LLM_SERVER_URL", "http://127.0.0.1:8080")
        self.api_server_host = os.getenv("API_HOST", "127.0.0.1")
        self.api_server_port = int(os.getenv("API_PORT", "8000"))
        
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/assistant.db")
        
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.vector_db_path = DATA_DIR / "faiss_db"
        
        self.max_context_length = 4096
        self.confidence_threshold = 0.7
        self.max_refinements = 3
        self.top_k_retrieval = 10
        
        self._capabilities: Optional[Dict] = None
        self._rules: Optional[Dict] = None
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        """Load capabilities from YAML"""
        if self._capabilities is None:
            caps_file = self.config_dir / "capabilities.yaml"
            if caps_file.exists():
                with open(caps_file, 'r') as f:
                    self._capabilities = yaml.safe_load(f)
            else:
                self._capabilities = {}
        return self._capabilities
    
    @property
    def rules(self) -> Dict[str, Any]:
        """Load rules from YAML"""
        if self._rules is None:
            rules_file = self.config_dir / "agent_rules.yaml"
            if rules_file.exists():
                with open(rules_file, 'r') as f:
                    self._rules = yaml.safe_load(f)
            else:
                self._rules = {}
        return self._rules
    
    def ensure_directories(self):
        """Create necessary directories"""
        for directory in [
            self.data_dir,
            self.workspace_dir,
            self.workspace_dir / "data",
            self.workspace_dir / "output",
            self.workspace_dir / "temp",
            self.exports_dir,
            self.static_dir / "images"
        ]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_capability(self, category: str, name: str) -> Dict[str, Any]:
        """Get specific capability config"""
        caps = self.capabilities.get("capabilities", {})
        return caps.get(category, {}).get(name, {})
    
    def is_capability_enabled(self, category: str, name: str) -> bool:
        """Check if capability is enabled"""
        cap = self.get_capability(category, name)
        return cap.get("enabled", False)


settings = Settings()
settings.ensure_directories()
