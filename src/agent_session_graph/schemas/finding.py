"""
Finding — output of anomaly detection and governance checks.

Represents a detected issue or insight from analysis:
anomaly detection, governance violations, cost warnings, etc.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class Finding(BaseModel):
    """
    A detected anomaly, governance violation, or analysis result.

    Emitted by detectors (AnomalyDetector, ContextDiffEngine, etc.) when
    they identify patterns worth flagging.

    Fields:
    - finding_id: Unique identifier (usually hash-based)
    - session_id: Which session this finding applies to
    - finding_class: High-level category (anomaly, governance, cost, etc.)
    - finding_type: Specific detection rule (e.g., "recursive_agent_loop")
    - severity: low | medium | high | critical
    - triggering_event_ids: Events that triggered this finding
    - root_cause_summary: Human-readable explanation
    - why_reasoning_text: LLM-generated explanation (if applicable)
    - context_diff_ref: Reference to context diff (if relevant)
    - related_finding_ids: Other findings in this session
    - detected_at: When this was detected
    - status: open | acknowledged | resolved
    """
    finding_id: str
    session_id: str
    finding_class: Literal["anomaly", "governance", "cost", "why_reasoning"]
    finding_type: str
    severity: Literal["low", "medium", "high", "critical"]
    triggering_event_ids: list[str]
    root_cause_summary: Optional[str] = None
    why_reasoning_text: Optional[str] = None
    context_diff_ref: Optional[str] = Field(
        None,
        description="Reference to context diff that may have caused this finding"
    )
    related_finding_ids: list[str] = Field(default_factory=list)
    detected_at: datetime
    status: Literal["open", "acknowledged", "resolved"] = "open"
