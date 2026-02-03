"""
Capability Registry
Manages agent capabilities, permissions, and tool availability
"""
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class CapabilityStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    RESTRICTED = "restricted"


@dataclass
class Capability:
    """Represents a single capability"""
    name: str
    category: str
    enabled: bool
    config: Dict[str, Any]
    
    def is_allowed(self, action: str = None) -> bool:
        if not self.enabled:
            return False
        if action and "allowed_operations" in self.config:
            return action in self.config["allowed_operations"]
        return True


class CapabilityRegistry:
    """Registry for managing agent capabilities"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.capabilities: Dict[str, Dict[str, Capability]] = {}
        self._config_path = config_path
        self._raw_config: Dict = {}
        
        if config_path and config_path.exists():
            self.load_from_yaml(config_path)
    
    def load_from_yaml(self, path: Path):
        """Load capabilities from YAML file"""
        with open(path, 'r') as f:
            self._raw_config = yaml.safe_load(f)
        
        caps = self._raw_config.get("capabilities", {})
        for category, items in caps.items():
            if category not in self.capabilities:
                self.capabilities[category] = {}
            
            for name, config in items.items():
                self.capabilities[category][name] = Capability(
                    name=name,
                    category=category,
                    enabled=config.get("enabled", False),
                    config=config
                )
    
    def get_capability(self, category: str, name: str) -> Optional[Capability]:
        """Get a specific capability"""
        return self.capabilities.get(category, {}).get(name)
    
    def is_enabled(self, category: str, name: str) -> bool:
        """Check if capability is enabled"""
        cap = self.get_capability(category, name)
        return cap.enabled if cap else False
    
    def get_config(self, category: str, name: str, key: str, default: Any = None) -> Any:
        """Get capability config value"""
        cap = self.get_capability(category, name)
        if cap:
            return cap.config.get(key, default)
        return default
    
    def list_enabled(self) -> List[str]:
        """List all enabled capabilities"""
        enabled = []
        for category, caps in self.capabilities.items():
            for name, cap in caps.items():
                if cap.enabled:
                    enabled.append(f"{category}.{name}")
        return enabled
    
    def list_all(self) -> Dict[str, List[str]]:
        """List all capabilities by category"""
        result = {}
        for category, caps in self.capabilities.items():
            result[category] = list(caps.keys())
        return result
    
    def check_permission(self, category: str, name: str, **kwargs) -> tuple[bool, str]:
        """
        Check if an action is permitted
        Returns (allowed, reason)
        """
        cap = self.get_capability(category, name)
        
        if not cap:
            return False, f"Unknown capability: {category}.{name}"
        
        if not cap.enabled:
            reason = cap.config.get("reason", "Capability is disabled")
            return False, reason
        
        if "max_file_size" in cap.config and "file_size" in kwargs:
            max_size = self._parse_size(cap.config["max_file_size"])
            if kwargs["file_size"] > max_size:
                return False, f"File size exceeds limit of {cap.config['max_file_size']}"
        
        if "allowed_extensions" in cap.config and "extension" in kwargs:
            if kwargs["extension"] not in cap.config["allowed_extensions"]:
                return False, f"Extension {kwargs['extension']} not allowed"
        
        if "timeout_seconds" in cap.config and "duration" in kwargs:
            if kwargs["duration"] > cap.config["timeout_seconds"]:
                return False, f"Operation would exceed timeout of {cap.config['timeout_seconds']}s"
        
        return True, "Allowed"
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes"""
        size_str = size_str.upper()
        if size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        return int(size_str)
    
    def get_allowed_imports(self) -> List[str]:
        """Get list of allowed Python imports"""
        return self.get_config("code_execution", "python", "allowed_imports", [])
    
    def get_blocked_imports(self) -> List[str]:
        """Get list of blocked Python imports"""
        return self.get_config("code_execution", "python", "blocked_imports", [])
    
    def get_allowed_extensions(self, operation: str) -> List[str]:
        """Get allowed file extensions for operation"""
        return self.get_config("file_operations", operation, "allowed_extensions", [])
    
    def to_prompt_context(self) -> str:
        """Generate capability context for system prompt"""
        lines = ["=== AVAILABLE CAPABILITIES ==="]
        
        for category, caps in self.capabilities.items():
            enabled_caps = [c for c in caps.values() if c.enabled]
            if enabled_caps:
                lines.append(f"\n{category.upper().replace('_', ' ')}:")
                for cap in enabled_caps:
                    config_info = []
                    if "timeout_seconds" in cap.config:
                        config_info.append(f"timeout: {cap.config['timeout_seconds']}s")
                    if "max_file_size" in cap.config:
                        config_info.append(f"max size: {cap.config['max_file_size']}")
                    if "max_rows" in cap.config:
                        config_info.append(f"max rows: {cap.config['max_rows']}")
                    
                    info = f" ({', '.join(config_info)})" if config_info else ""
                    lines.append(f"  - {cap.name}{info}")
        
        return "\n".join(lines)
