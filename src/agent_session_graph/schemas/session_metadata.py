"""
SessionMetadata schema — aggregate state for a multi-agent session.

Tracks runtime state: participants, token usage, cost, data integrity,
and finding summaries.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class IngestionSource(BaseModel):
    """
    Metadata about how this session was ingested.
    """
    ingestion_type: Literal["native_session_log", "otel_trace"]
    harness: Optional[str] = None
    harness_version: Optional[str] = None


class TokenUsage(BaseModel):
    """
    Cumulative token usage across all model calls in a session.
    """
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


class DataIntegrity(BaseModel):
    """
    Data quality indicators for session reconstruction.

    Tracks whether all events arrived in order, if there were sequence gaps,
    and confidence in the reconstruction.
    """
    status: Literal["complete", "partial", "gaps_detected"] = "complete"
    gap_ranges: list[list[int]] = Field(default_factory=list)
    confidence: Literal["high", "degraded"] = "high"


class FindingSummary(BaseModel):
    """
    Summary of anomaly detection findings for a session.
    """
    anomalies: int = 0
    governance: int = 0
    max_severity: Optional[str] = None


class SessionMetadata(BaseModel):
    """
    Aggregate metadata for a multi-agent session.

    Maintained by SessionBuilder and finalized when the session ends.
    Tracks runtime state, participants, token usage, cost, and data integrity.
    """
    session_id: str
    tenant_id: str = Field(default="default", description="Multi-tenancy identifier")
    application_id: Optional[str] = None
    root_agent: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: Literal["running", "completed", "failed"] = "running"
    objective: Optional[str] = None
    source: IngestionSource
    cost_usd: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    data_integrity: DataIntegrity = Field(default_factory=DataIntegrity)
    finding_summary: FindingSummary = Field(default_factory=FindingSummary)
    last_seq: int = 0
