"""
Test SessionReconstructor high-level API.
"""
import json
import tempfile
from pathlib import Path

from agent_session_graph import Session, SessionReconstructor


def test_session_reconstructor_from_spans():
    """Test SessionReconstructor with in-memory spans."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {"span_id": "span_001", "tenant_id": "test"}
        },
        {
            "span_name": "agent.start",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {
                "span_id": "span_002",
                "parent_span_id": "span_001",
                "agent_id": "coordinator"
            }
        },
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:02Z",
            "attributes": {
                "span_id": "span_003",
                "parent_span_id": "span_002",
                "agent_id": "coordinator",
                "input_tokens": 1000,
                "output_tokens": 200
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:05Z",
            "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="test-session-001")

    assert isinstance(session, Session)
    assert session.id == "test-session-001"
    assert session.metadata.status == "completed"
    assert len(session.timeline) == 4
    assert len(session.execution_graph) > 0


def test_session_reconstructor_from_json():
    """Test SessionReconstructor with JSON file."""
    trace_data = {
        "session_id": "test-json-session",
        "spans": [
            {
                "span_name": "session.start",
                "start_time": "2026-07-16T10:00:00Z",
                "attributes": {"span_id": "span_001"}
            },
            {
                "span_name": "session.end",
                "start_time": "2026-07-16T10:00:01Z",
                "attributes": {"span_id": "span_002", "parent_span_id": "span_001"}
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(trace_data, f)
        temp_path = f.name

    try:
        reconstructor = SessionReconstructor()
        session = reconstructor.from_otlp_json(temp_path)

        assert session.id == "test-json-session"
        assert len(session.timeline) == 2
    finally:
        Path(temp_path).unlink()


def test_session_properties():
    """Test Session object properties."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {"span_id": "span_001", "tenant_id": "test"}
        },
        {
            "span_name": "agent.start",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {
                "span_id": "span_002",
                "parent_span_id": "span_001",
                "agent_id": "agent_a"
            }
        },
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:02Z",
            "attributes": {
                "span_id": "span_003",
                "parent_span_id": "span_002",
                "agent_id": "agent_a",
                "input_tokens": 1500,
                "output_tokens": 300
            }
        },
        {
            "span_name": "tool.call",
            "start_time": "2026-07-16T10:00:03Z",
            "attributes": {
                "span_id": "span_004",
                "parent_span_id": "span_002",
                "agent_id": "agent_a",
                "tool_name": "web_search"
            }
        },
        {
            "span_name": "tool.result",
            "start_time": "2026-07-16T10:00:05Z",
            "attributes": {
                "span_id": "span_005",
                "parent_span_id": "span_004",
                "agent_id": "agent_a"
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:06Z",
            "attributes": {"span_id": "span_006", "parent_span_id": "span_001"}
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="test-props")

    # Test timeline
    assert len(session.timeline) == 6
    assert session.timeline[0].seq == 1
    assert session.timeline[-1].seq == 6

    # Test execution_graph
    assert len(session.execution_graph) > 0
    assert any(e.edge_type == "caused_by" for e in session.execution_graph)
    assert any(e.edge_type == "invoked" for e in session.execution_graph)

    # Test agents
    assert "agent_a" in session.agents

    # Test total_tokens
    assert session.total_tokens == 1800  # 1500 + 300

    # Test cost_attribution
    cost_attr = session.cost_attribution
    assert "agent_a" in cost_attr
    assert cost_attr["agent_a"] > 0

    # Test tool_lifecycle
    tools = session.tool_lifecycle
    assert len(tools) == 1
    assert tools[0]["tool_name"] == "web_search"
    assert tools[0]["status"] == "success"
    assert tools[0]["agent"] == "agent_a"


def test_session_lineage():
    """Test Session lineage tracing."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {"span_id": "span_001"}
        },
        {
            "span_name": "agent.start",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {
                "span_id": "span_002",
                "parent_span_id": "span_001",
                "agent_id": "root"
            }
        },
        {
            "span_name": "tool.call",
            "start_time": "2026-07-16T10:00:02Z",
            "attributes": {
                "span_id": "span_003",
                "parent_span_id": "span_002",
                "agent_id": "root"
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:03Z",
            "attributes": {
                "span_id": "span_004",
                "parent_span_id": "span_001"
            }
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="test-lineage")

    # Find the tool call event
    tool_event = next(e for e in session.timeline if e.event_type == "TOOL_CALL")

    # Trace lineage
    lineage = session.lineage(tool_event.event_id)

    # Should trace back through parent edges
    assert len(lineage) >= 2
    assert tool_event.event_id in lineage
