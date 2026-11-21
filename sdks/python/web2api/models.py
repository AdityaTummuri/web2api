"""
Data models for Web2API Python SDK.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResponse:
    response: str
    latency_seconds: float
    status: str
    extracted: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    status: str
    extension_connected: bool
    auth_required: bool
    timestamp: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
