"""
Data models for Web2API Python SDK with Tool Calling support.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class FunctionCall:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str = "function"
    function: Optional[FunctionCall] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToolCall":
        fn_dict = d.get("function", {})
        return cls(
            id=d.get("id", ""),
            type=d.get("type", "function"),
            function=FunctionCall(
                name=fn_dict.get("name", ""),
                arguments=fn_dict.get("arguments", "{}")
            ) if fn_dict else None
        )


@dataclass
class ChatMessage:
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.name is not None:
            d["name"] = self.name
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        return d


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
