"""
Test schema models for serialization and validation.
"""
import pytest
from datetime import datetime, timezone
from agent_session_graph.schemas import (
    SessionEvent,
    EventType,
    SessionMetadata,
    ExecutionEdge,
    Finding,
)


def test_session_event_creation():
    """Test SessionEvent model creation and validation."""
    event = SessionEvent(
        event_id="evt_001",
        session_id="sess_001",
        seq=1,
        timestamp=datetime.now(timezone.utc),
        event_type=EventType.SESSION_START,
        payload={"tenant_id": "test"}
    )

    assert event.event_id == "evt_001"
    assert event.session_id == "sess_001"
    assert event.seq == 1
    assert event.event_type == EventType.SESSION_START


def test_session_event_serialization():
    """Test SessionEvent JSON serialization round-trip."""
    event = SessionEvent(
        event_id="evt_001",
        session_id="sess_001",
        seq=1,
        timestamp=datetime(2026, 7, 16, 10, 0, 0, tzinfo=timezone.utc),
        event_type=EventType.AGENT_START,
        participant_id="agent_main",
        payload={"foo": "bar"}
    )

    # Serialize to dict
    data = event.model_dump()
    assert data["event_id"] == "evt_001"
    assert data["event_type"] == "AGENT_START"

    # Deserialize from dict
    event2 = SessionEvent(**data)
    assert event2.event_id == event.event_id
    assert event2.event_type == event.event_type


def test_execution_edge_creation():
    """Test ExecutionEdge model creation."""
    edge = ExecutionEdge(
        edge_id="edge_001",
        session_id="sess_001",
        source_event_id="evt_001",
        target_event_id="evt_002",
        edge_type="caused_by"
    )

    assert edge.edge_id == "edge_001"
    assert edge.edge_type == "caused_by"


def test_finding_creation():
    """Test Finding model creation."""
    finding = Finding(
        finding_id="finding_001",
        session_id="sess_001",
        finding_class="anomaly",
        finding_type="recursive_agent_loop",
        severity="critical",
        triggering_event_ids=["evt_003", "evt_007"],
        root_cause_summary="Agent recursively delegated 5 times",
        detected_at=datetime.now(timezone.utc),
        status="open"
    )

    assert finding.finding_class == "anomaly"
    assert finding.severity == "critical"
    assert len(finding.triggering_event_ids) == 2
