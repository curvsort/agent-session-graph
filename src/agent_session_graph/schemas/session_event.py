"""
Core SessionEvent schema — the atomic unit of session reconstruction.

Every event in a multi-agent session (from OTel spans or native logs)
is normalized into this shape before processing.
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Any
from enum import Enum


class EventType(str, Enum):
    """
    Event type taxonomy for multi-agent sessions.

    Covers agent lifecycle, model interactions, tools, memory, context,
    governance, and infrastructure events.
    """
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    AGENT_START = "AGENT_START"
    AGENT_END = "AGENT_END"
    AGENT_DELEGATE = "AGENT_DELEGATE"
    MODEL_CALL = "MODEL_CALL"
    MODEL_RESPONSE = "MODEL_RESPONSE"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    TOOL_ERROR = "TOOL_ERROR"
    MEMORY_READ = "MEMORY_READ"
    MEMORY_WRITE = "MEMORY_WRITE"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    CONTEXT_COMPACTION = "CONTEXT_COMPACTION"
    CONTEXT_TRIM = "CONTEXT_TRIM"
    PROFILE_SWITCH = "PROFILE_SWITCH"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    COST_UPDATE = "COST_UPDATE"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    GOVERNANCE_FINDING = "GOVERNANCE_FINDING"
    SANDBOX_START = "SANDBOX_START"
    SANDBOX_END = "SANDBOX_END"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"
    INGESTION_GAP_DETECTED = "INGESTION_GAP_DETECTED"


class SessionEvent(BaseModel):
    """
    Atomic event in a multi-agent session.

    Every action (agent starts, model calls, tool invocations, memory operations,
    context changes, etc.) is represented as a SessionEvent with:
    - Unique event_id (deterministic from content hash)
    - session_id (groups events into sessions)
    - seq (monotonic sequence number for ordering)
    - timestamp (when the event occurred)
    - event_type (one of 24 types in EventType enum)
    - parent_event_id (causal parent, if any)
    - participant_id (which agent/component emitted this)
    - payload (type-specific data)
    """
    event_id: str
    session_id: str
    seq: int = Field(..., description="Monotonic sequence number, assigned at emission")
    timestamp: datetime
    event_type: EventType
    parent_event_id: Optional[str] = None
    participant_id: Optional[str] = None
    profile_snapshot_id: Optional[str] = None
    context_version_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)

    @property
    def payload_json(self) -> str:
        """Serialize payload to JSON string."""
        import json
        return json.dumps(self.payload)
