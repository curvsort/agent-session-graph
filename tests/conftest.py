"""
Shared pytest fixtures for agent-session-graph tests.
"""
from datetime import datetime, timezone

import pytest

from agent_session_graph.schemas import EventType, SessionEvent
from agent_session_graph.storage import InMemoryStorage


@pytest.fixture
def storage():
    """Provide clean InMemoryStorage for each test."""
    return InMemoryStorage()


@pytest.fixture
def sample_session_id():
    """Standard session ID for tests."""
    return "test-session-001"


@pytest.fixture
def sample_events(sample_session_id):
    """Generate a minimal set of SessionEvents for testing."""
    return [
        SessionEvent(
            event_id="evt_001",
            session_id=sample_session_id,
            seq=1,
            timestamp=datetime(2026, 7, 16, 10, 0, 0, tzinfo=timezone.utc),
            event_type=EventType.SESSION_START,
            payload={"tenant_id": "test_tenant"}
        ),
        SessionEvent(
            event_id="evt_002",
            session_id=sample_session_id,
            seq=2,
            timestamp=datetime(2026, 7, 16, 10, 0, 1, tzinfo=timezone.utc),
            event_type=EventType.AGENT_START,
            parent_event_id="evt_001",
            participant_id="agent_main",
            payload={}
        ),
        SessionEvent(
            event_id="evt_003",
            session_id=sample_session_id,
            seq=3,
            timestamp=datetime(2026, 7, 16, 10, 0, 5, tzinfo=timezone.utc),
            event_type=EventType.SESSION_END,
            parent_event_id="evt_001",
            payload={}
        ),
    ]
