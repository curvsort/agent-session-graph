"""
OTel span normalization to SessionEvent schema.

Maps vendor-specific span patterns to the 24-type EventType taxonomy.
Works with any OTel-instrumented multi-agent system.
"""
import json
from datetime import datetime
from typing import Any

from agent_session_graph.schemas import SessionEvent, EventType


def normalize_span(span: dict, session_id: str, seq: int) -> SessionEvent:
    """
    Normalize a single OTel span to SessionEvent.

    Maps span_name patterns to EventType taxonomy:
    - Agent start/end patterns → AGENT_START/AGENT_END
    - Model/Claude/Bedrock patterns → MODEL_CALL
    - Known tool patterns → TOOL_CALL
    - Default fallback → TOOL_CALL with original span preserved

    Args:
        span: OTel span dict with keys: span_name, start_time, attributes
        session_id: Session identifier for grouping
        seq: Monotonic sequence number

    Returns:
        Normalized SessionEvent
    """
    span_name = span.get("span_name", "")
    start_time = span.get("start_time")
    attributes = span.get("attributes", {})

    # Parse timestamp
    if isinstance(start_time, str):
        timestamp = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    elif isinstance(start_time, datetime):
        timestamp = start_time
    else:
        timestamp = datetime.utcnow()

    # Determine EventType from span_name patterns
    event_type = _infer_event_type(span_name)

    # Extract parent relationship from attributes
    parent_event_id = attributes.get("parent_span_id") or attributes.get("parent_event_id")
    participant_id = attributes.get("agent_id") or attributes.get("participant_id")

    # Build payload from attributes
    payload = {
        "original_span_name": span_name,
        **attributes
    }

    # Generate event_id from span_id or create one
    event_id = attributes.get("span_id", f"evt_{session_id}_{seq}")

    return SessionEvent(
        event_id=event_id,
        session_id=session_id,
        seq=seq,
        timestamp=timestamp,
        event_type=event_type,
        parent_event_id=parent_event_id,
        participant_id=participant_id,
        profile_snapshot_id=attributes.get("profile_id"),
        context_version_id=attributes.get("context_version_id"),
        payload=payload
    )


def _infer_event_type(span_name: str) -> EventType:
    """
    Infer EventType from OTel span_name using pattern matching.

    Pattern hierarchy (checked in order):
    1. Session lifecycle patterns
    2. Agent lifecycle patterns
    3. Model/LLM call patterns
    4. Tool call patterns
    5. Memory operation patterns
    6. Context operation patterns
    7. Fallback to TOOL_CALL

    Args:
        span_name: OTel span name string

    Returns:
        Mapped EventType
    """
    span_lower = span_name.lower()

    # Session lifecycle
    if "session" in span_lower:
        if any(term in span_lower for term in ["start", "begin", "init"]):
            return EventType.SESSION_START
        elif any(term in span_lower for term in ["end", "complete", "finish"]):
            return EventType.SESSION_END

    # Agent lifecycle
    if "agent" in span_lower:
        if any(term in span_lower for term in ["delegate"]):
            return EventType.AGENT_DELEGATE
        elif any(term in span_lower for term in ["start", "begin", "init"]):
            return EventType.AGENT_START
        elif any(term in span_lower for term in ["end", "complete", "finish"]):
            return EventType.AGENT_END

    # Model/LLM calls
    if any(term in span_lower for term in ["model", "claude", "bedrock", "llm", "anthropic"]):
        if any(term in span_lower for term in ["response", "completion", "result"]):
            return EventType.MODEL_RESPONSE
        else:
            return EventType.MODEL_CALL

    # Tool operations
    if any(term in span_lower for term in ["tool", "websearch", "web_search", "search", "api_call"]):
        if "error" in span_lower:
            return EventType.TOOL_ERROR
        elif any(term in span_lower for term in ["result", "response", "completion"]):
            return EventType.TOOL_RESULT
        else:
            return EventType.TOOL_CALL

    # Memory operations
    if "memory" in span_lower:
        if any(term in span_lower for term in ["write", "set", "update"]):
            return EventType.MEMORY_WRITE
        elif "read" in span_lower or "get" in span_lower:
            return EventType.MEMORY_READ
        else:
            return EventType.MEMORY_UPDATE

    # Context operations
    if "context" in span_lower:
        if "compaction" in span_lower or "compact" in span_lower:
            return EventType.CONTEXT_COMPACTION
        elif "trim" in span_lower:
            return EventType.CONTEXT_TRIM

    # Profile/Policy/Sandbox operations
    if "profile" in span_lower and "switch" in span_lower:
        return EventType.PROFILE_SWITCH
    if "escalation" in span_lower or "human" in span_lower:
        return EventType.HUMAN_ESCALATION
    if "policy" in span_lower and "violation" in span_lower:
        return EventType.POLICY_VIOLATION
    if "cost" in span_lower:
        return EventType.COST_UPDATE
    if "sandbox" in span_lower:
        if "start" in span_lower:
            return EventType.SANDBOX_START
        elif "timeout" in span_lower:
            return EventType.SANDBOX_TIMEOUT
        elif "end" in span_lower:
            return EventType.SANDBOX_END

    # Anomaly/Governance findings
    if "anomaly" in span_lower:
        return EventType.ANOMALY_DETECTED
    if "governance" in span_lower or "finding" in span_lower:
        return EventType.GOVERNANCE_FINDING

    # Default fallback - treat unknown spans as tool calls
    return EventType.TOOL_CALL


def normalize_trace(spans: list[dict], session_id: str) -> list[SessionEvent]:
    """
    Normalize a full OTel trace (list of spans) to SessionEvent list.

    Processes spans in order, assigning incrementing sequence numbers.

    Args:
        spans: List of OTel span dicts
        session_id: Session identifier for all events

    Returns:
        List of normalized SessionEvent objects
    """
    events = []

    for idx, span in enumerate(spans, start=1):
        event = normalize_span(span, session_id, seq=idx)
        events.append(event)

    return events
