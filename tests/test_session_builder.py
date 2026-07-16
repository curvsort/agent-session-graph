"""
Test SessionBuilder session reconstruction logic.
"""
import pytest
from agent_session_graph.session import SessionBuilder
from agent_session_graph.schemas import EventType


def test_session_initialization(storage, sample_events):
    """Test SessionBuilder initializes session on first event."""
    builder = SessionBuilder(storage=storage)

    # Process first event
    builder.process_event(sample_events[0])

    # Check session was created
    metadata = builder.get_session_state(sample_events[0].session_id)
    assert metadata is not None
    assert metadata.status == "running"
    assert metadata.tenant_id == "test_tenant"


def test_sequence_gap_detection(storage, sample_session_id):
    """Test SessionBuilder detects sequence gaps."""
    from agent_session_graph.schemas import SessionEvent
    from datetime import datetime, timezone

    builder = SessionBuilder(storage=storage)

    # Create events with a gap (seq 1, 2, 5 - missing 3, 4)
    events = [
        SessionEvent(
            event_id="evt_001",
            session_id=sample_session_id,
            seq=1,
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.SESSION_START,
            payload={"tenant_id": "test"}
        ),
        SessionEvent(
            event_id="evt_002",
            session_id=sample_session_id,
            seq=2,
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_START,
            payload={}
        ),
        SessionEvent(
            event_id="evt_005",
            session_id=sample_session_id,
            seq=5,  # Gap: missing seq 3 and 4
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_END,
            payload={}
        ),
    ]

    for event in events:
        builder.process_event(event)

    # Check gap was detected
    metadata = builder.get_session_state(sample_session_id)
    assert metadata.data_integrity.status == "gaps_detected"
    assert metadata.data_integrity.confidence == "degraded"
    assert len(metadata.data_integrity.gap_ranges) == 1
    assert metadata.data_integrity.gap_ranges[0] == [3, 4]


def test_session_end_finalization(storage, sample_events):
    """Test SessionBuilder finalizes on SESSION_END."""
    builder = SessionBuilder(storage=storage)

    # Process all events including SESSION_END
    for event in sample_events:
        builder.process_event(event)

    # Check session status
    metadata = builder.get_session_state(sample_events[0].session_id)
    assert metadata.status == "completed"
    assert metadata.end_time is not None

    # Check metadata was persisted
    stored_metadata = storage.get_metadata_by_session(sample_events[0].session_id)
    assert stored_metadata is not None
    assert stored_metadata.status == "completed"
