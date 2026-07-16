"""
Storage backend tests.

Tests the storage protocol implementations:
- NullStorage (no-op)
- InMemoryStorage (dict-backed)
- StorageBackend protocol compliance
"""
import pytest
from agent_session_graph.storage import NullStorage, InMemoryStorage, StorageBackend
from agent_session_graph.schemas import (
    SessionEvent,
    SessionMetadata,
    ExecutionEdge,
    Finding,
    EventType,
    IngestionSource,
    TokenUsage,
    DataIntegrity,
    FindingSummary
)
from datetime import datetime, timezone


@pytest.fixture
def sample_event():
    """Create a sample SessionEvent."""
    return SessionEvent(
        event_id="evt_001",
        session_id="sess_001",
        seq=1,
        timestamp=datetime.now(timezone.utc),
        event_type=EventType.AGENT_START,
        participant_id="agent_main",
        payload={"foo": "bar"}
    )


@pytest.fixture
def sample_metadata():
    """Create sample SessionMetadata."""
    return SessionMetadata(
        session_id="sess_001",
        tenant_id="test_tenant",
        start_time=datetime.now(timezone.utc),
        status="running",
        source=IngestionSource(ingestion_type="otel_trace"),
        token_usage=TokenUsage(),
        data_integrity=DataIntegrity(),
        finding_summary=FindingSummary(),
        last_seq=1
    )


@pytest.fixture
def sample_edge():
    """Create a sample ExecutionEdge."""
    return ExecutionEdge(
        edge_id="edge_001",
        session_id="sess_001",
        source_event_id="evt_001",
        target_event_id="evt_002",
        edge_type="caused_by"
    )


@pytest.fixture
def sample_finding():
    """Create a sample Finding."""
    return Finding(
        finding_id="finding_001",
        session_id="sess_001",
        finding_class="anomaly",
        finding_type="test_finding",
        severity="medium",
        triggering_event_ids=["evt_001"],
        detected_at=datetime.now(timezone.utc),
        status="open"
    )


class TestNullStorage:
    """Test NullStorage (no-op implementation)."""

    def test_implements_protocol(self):
        """Test NullStorage implements StorageBackend protocol."""
        storage = NullStorage()
        assert isinstance(storage, StorageBackend)

    def test_write_event_no_op(self, sample_event):
        """Test write_event discards data."""
        storage = NullStorage()
        storage.write_event(sample_event)  # Should not raise

    def test_write_metadata_no_op(self, sample_metadata):
        """Test write_metadata discards data."""
        storage = NullStorage()
        storage.write_metadata(sample_metadata)  # Should not raise

    def test_write_edge_no_op(self, sample_edge):
        """Test write_edge discards data."""
        storage = NullStorage()
        storage.write_edge(sample_edge)  # Should not raise

    def test_write_finding_no_op(self, sample_finding):
        """Test write_finding discards data."""
        storage = NullStorage()
        storage.write_finding(sample_finding)  # Should not raise

    def test_get_events_returns_empty(self):
        """Test get_events_by_session returns empty list."""
        storage = NullStorage()
        events = storage.get_events_by_session("sess_001")
        assert events == []

    def test_get_metadata_returns_none(self):
        """Test get_metadata_by_session returns None."""
        storage = NullStorage()
        metadata = storage.get_metadata_by_session("sess_001")
        assert metadata is None

    def test_get_edges_returns_empty(self):
        """Test get_edges_by_session returns empty list."""
        storage = NullStorage()
        edges = storage.get_edges_by_session("sess_001")
        assert edges == []

    def test_get_findings_returns_empty(self):
        """Test get_findings_by_session returns empty list."""
        storage = NullStorage()
        findings = storage.get_findings_by_session("sess_001")
        assert findings == []


class TestInMemoryStorage:
    """Test InMemoryStorage (dict-backed implementation)."""

    def test_implements_protocol(self):
        """Test InMemoryStorage implements StorageBackend protocol."""
        storage = InMemoryStorage()
        assert isinstance(storage, StorageBackend)

    def test_write_and_get_event(self, sample_event):
        """Test write and retrieve event."""
        storage = InMemoryStorage()
        storage.write_event(sample_event)

        events = storage.get_events_by_session("sess_001")
        assert len(events) == 1
        assert events[0].event_id == "evt_001"

    def test_write_multiple_events_sorted(self):
        """Test events are stored in sequence order."""
        storage = InMemoryStorage()

        # Write out of order
        event2 = SessionEvent(
            event_id="evt_002", session_id="sess_001", seq=2,
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_END, payload={}
        )
        event1 = SessionEvent(
            event_id="evt_001", session_id="sess_001", seq=1,
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_START, payload={}
        )

        storage.write_event(event2)
        storage.write_event(event1)

        events = storage.get_events_by_session("sess_001")
        assert len(events) == 2
        assert events[0].seq == 1  # Sorted by seq
        assert events[1].seq == 2

    def test_write_and_get_metadata(self, sample_metadata):
        """Test write and retrieve metadata."""
        storage = InMemoryStorage()
        storage.write_metadata(sample_metadata)

        metadata = storage.get_metadata_by_session("sess_001")
        assert metadata is not None
        assert metadata.session_id == "sess_001"

    def test_write_and_get_edge(self, sample_edge):
        """Test write and retrieve edge."""
        storage = InMemoryStorage()
        storage.write_edge(sample_edge)

        edges = storage.get_edges_by_session("sess_001")
        assert len(edges) == 1
        assert edges[0].edge_id == "edge_001"

    def test_write_and_get_finding(self, sample_finding):
        """Test write and retrieve finding."""
        storage = InMemoryStorage()
        storage.write_finding(sample_finding)

        findings = storage.get_findings_by_session("sess_001")
        assert len(findings) == 1
        assert findings[0].finding_id == "finding_001"

    def test_multiple_sessions_isolated(self):
        """Test data isolation between sessions."""
        storage = InMemoryStorage()

        event1 = SessionEvent(
            event_id="evt_001", session_id="sess_001", seq=1,
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_START, payload={}
        )
        event2 = SessionEvent(
            event_id="evt_002", session_id="sess_002", seq=1,
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_START, payload={}
        )

        storage.write_event(event1)
        storage.write_event(event2)

        # Each session should only see its own events
        events1 = storage.get_events_by_session("sess_001")
        events2 = storage.get_events_by_session("sess_002")

        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].event_id == "evt_001"
        assert events2[0].event_id == "evt_002"

    def test_clear_method(self, sample_event, sample_metadata):
        """Test clear() removes all data."""
        storage = InMemoryStorage()

        storage.write_event(sample_event)
        storage.write_metadata(sample_metadata)

        # Verify data exists
        assert len(storage.get_events_by_session("sess_001")) == 1
        assert storage.get_metadata_by_session("sess_001") is not None

        # Clear
        storage.clear()

        # Verify data removed
        assert len(storage.get_events_by_session("sess_001")) == 0
        assert storage.get_metadata_by_session("sess_001") is None

    def test_get_nonexistent_session(self):
        """Test querying non-existent session returns empty."""
        storage = InMemoryStorage()

        events = storage.get_events_by_session("nonexistent")
        metadata = storage.get_metadata_by_session("nonexistent")
        edges = storage.get_edges_by_session("nonexistent")
        findings = storage.get_findings_by_session("nonexistent")

        assert events == []
        assert metadata is None
        assert edges == []
        assert findings == []

    def test_overwrite_metadata(self):
        """Test metadata can be overwritten."""
        storage = InMemoryStorage()

        meta1 = SessionMetadata(
            session_id="sess_001", tenant_id="tenant1",
            start_time=datetime.now(timezone.utc), status="running",
            source=IngestionSource(ingestion_type="otel_trace"),
            token_usage=TokenUsage(), data_integrity=DataIntegrity(),
            finding_summary=FindingSummary(), last_seq=1
        )
        meta2 = SessionMetadata(
            session_id="sess_001", tenant_id="tenant1",
            start_time=datetime.now(timezone.utc), status="completed",
            source=IngestionSource(ingestion_type="otel_trace"),
            token_usage=TokenUsage(), data_integrity=DataIntegrity(),
            finding_summary=FindingSummary(), last_seq=10
        )

        storage.write_metadata(meta1)
        storage.write_metadata(meta2)

        # Should return most recent write
        metadata = storage.get_metadata_by_session("sess_001")
        assert metadata.status == "completed"
        assert metadata.last_seq == 10
