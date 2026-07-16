"""
Edge case tests - error handling and boundary conditions.

Tests unusual inputs, missing data, malformed data, and error recovery.
"""
import pytest
from datetime import datetime
from agent_session_graph import SessionReconstructor
from agent_session_graph.ingestion import normalize_span, normalize_trace


def test_empty_span_list():
    """Test handling of empty span list."""
    reconstructor = SessionReconstructor()

    with pytest.raises(ValueError, match="spans list cannot be empty"):
        reconstructor.from_otlp_spans([], session_id="empty")


def test_single_span_session():
    """Test minimal session with single span."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {"span_id": "span_001"}
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="single-span")

    assert session.id == "single-span"
    assert len(session.timeline) == 1
    assert len(session.execution_graph) == 0  # No edges with single event
    assert session.metadata.status == "running"  # Never ended


def test_missing_session_id_in_json():
    """Test JSON without session_id field."""
    import json
    import tempfile
    from pathlib import Path

    trace_data = {
        "spans": [
            {"span_name": "test", "start_time": "2026-07-16T10:00:00Z", "attributes": {}}
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(trace_data, f)
        temp_path = f.name

    try:
        reconstructor = SessionReconstructor()
        with pytest.raises(ValueError, match="JSON must contain 'session_id' field"):
            reconstructor.from_otlp_json(temp_path)
    finally:
        Path(temp_path).unlink()


def test_missing_spans_in_json():
    """Test JSON without spans array."""
    import json
    import tempfile
    from pathlib import Path

    trace_data = {"session_id": "test"}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(trace_data, f)
        temp_path = f.name

    try:
        reconstructor = SessionReconstructor()
        with pytest.raises(ValueError, match="JSON must contain non-empty 'spans' array"):
            reconstructor.from_otlp_json(temp_path)
    finally:
        Path(temp_path).unlink()


def test_missing_span_attributes():
    """Test spans with missing optional attributes."""
    spans = [
        {
            "span_name": "agent.start",
            "start_time": "2026-07-16T10:00:00Z",
            # Missing attributes dict
        },
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {}  # Empty attributes
        }
    ]

    # Should not crash - normalizer handles missing attributes
    events = normalize_trace(spans, session_id="missing-attrs")

    assert len(events) == 2
    assert events[0].event_id  # Generated fallback ID
    assert events[0].participant_id is None
    assert events[1].participant_id is None


def test_malformed_timestamp_iso_string():
    """Test handling of ISO timestamp string."""
    span = {
        "span_name": "test",
        "start_time": "2026-07-16T10:00:00Z",
        "attributes": {}
    }

    event = normalize_span(span, session_id="ts-test", seq=1)
    assert event.timestamp.year == 2026
    assert event.timestamp.month == 7
    assert event.timestamp.day == 16


def test_malformed_timestamp_datetime_object():
    """Test handling of datetime object."""
    span = {
        "span_name": "test",
        "start_time": datetime(2026, 7, 16, 10, 0, 0),
        "attributes": {}
    }

    event = normalize_span(span, session_id="ts-test", seq=1)
    assert event.timestamp.year == 2026


def test_malformed_timestamp_missing():
    """Test handling of missing timestamp (uses current time)."""
    span = {
        "span_name": "test",
        # start_time missing
        "attributes": {}
    }

    event = normalize_span(span, session_id="ts-test", seq=1)
    assert event.timestamp is not None
    # Should be recent (within last minute)
    now = datetime.utcnow()
    delta = abs((now - event.timestamp.replace(tzinfo=None)).total_seconds())
    assert delta < 60


def test_missing_parent_span_id():
    """Test event without parent (root event)."""
    spans = [
        {
            "span_name": "agent.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {
                "span_id": "span_001",
                # No parent_span_id - this is a root
            }
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="no-parent")

    # Should work fine - no parent edges created
    assert len(session.timeline) == 1
    assert session.timeline[0].parent_event_id is None
    # No caused_by edges since no parent relationships
    caused_by_edges = [e for e in session.execution_graph if e.edge_type == "caused_by"]
    assert len(caused_by_edges) == 0


def test_circular_parent_references():
    """Test handling of circular parent references (shouldn't happen, but defensive)."""
    spans = [
        {
            "span_name": "event_a",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {
                "span_id": "span_001",
                "parent_span_id": "span_002"  # References next span
            }
        },
        {
            "span_name": "event_b",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {
                "span_id": "span_002",
                "parent_span_id": "span_001"  # Circular reference
            }
        }
    ]

    # Should not crash - lineage tracing has cycle detection
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="circular")

    # Lineage should stop at cycles
    lineage = session.lineage("span_001")
    assert len(lineage) < 10  # Didn't infinite loop


def test_tool_call_without_result():
    """Test incomplete tool lifecycle (call but no result)."""
    spans = [
        {
            "span_name": "tool.call",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {
                "span_id": "span_001",
                "agent_id": "agent_a",
                "tool_name": "web_search"
            }
        }
        # No corresponding tool.result
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="incomplete-tool")

    # Tool lifecycle should be empty (no matched call→result)
    tools = session.tool_lifecycle
    assert len(tools) == 0


def test_auto_generate_session_id():
    """Test session_id auto-generation from spans."""
    spans = [
        {
            "span_name": "test",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {}
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans)  # No session_id provided

    # Should use default
    assert session.id == "session_default"


def test_model_call_without_token_counts():
    """Test model call with missing token information."""
    spans = [
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {
                "span_id": "span_001",
                "agent_id": "agent_a",
                "model": "claude"
                # No input_tokens or output_tokens
            }
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="no-tokens")

    # Should handle gracefully - tokens default to 0
    assert session.total_tokens == 0
    cost_attr = session.cost_attribution
    assert "agent_a" in cost_attr
    assert cost_attr["agent_a"] == 0.0
