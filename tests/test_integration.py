"""
Integration tests - full pipeline end-to-end.

Tests the complete workflow: OTel spans → normalization → session building →
graph inference → detection → query interface.
"""
import pytest
from agent_session_graph import SessionReconstructor
from agent_session_graph.schemas import EventType


def test_full_pipeline_healthy_session():
    """Test complete pipeline with healthy multi-agent session."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {
                "span_id": "span_001",
                "tenant_id": "integration_test",
                "application_id": "test_app"
            }
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
                "model": "claude-3.5-sonnet",
                "input_tokens": 1500,
                "output_tokens": 300
            }
        },
        {
            "span_name": "agent.delegate",
            "start_time": "2026-07-16T10:00:05Z",
            "attributes": {
                "span_id": "span_004",
                "parent_span_id": "span_002",
                "agent_id": "coordinator",
                "delegated_to": "researcher"
            }
        },
        {
            "span_name": "agent.start",
            "start_time": "2026-07-16T10:00:06Z",
            "attributes": {
                "span_id": "span_005",
                "parent_span_id": "span_004",
                "agent_id": "researcher"
            }
        },
        {
            "span_name": "tool.call",
            "start_time": "2026-07-16T10:00:07Z",
            "attributes": {
                "span_id": "span_006",
                "parent_span_id": "span_005",
                "agent_id": "researcher",
                "tool_name": "web_search"
            }
        },
        {
            "span_name": "tool.result",
            "start_time": "2026-07-16T10:00:10Z",
            "attributes": {
                "span_id": "span_007",
                "parent_span_id": "span_006",
                "agent_id": "researcher",
                "status": "success"
            }
        },
        {
            "span_name": "agent.end",
            "start_time": "2026-07-16T10:00:15Z",
            "attributes": {
                "span_id": "span_008",
                "parent_span_id": "span_004",
                "agent_id": "researcher"
            }
        },
        {
            "span_name": "agent.end",
            "start_time": "2026-07-16T10:00:16Z",
            "attributes": {
                "span_id": "span_009",
                "parent_span_id": "span_001",
                "agent_id": "coordinator"
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:17Z",
            "attributes": {
                "span_id": "span_010",
                "parent_span_id": "span_001"
            }
        }
    ]

    # Full pipeline
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="integration-001")

    # Verify all components populated
    assert session.id == "integration-001"
    assert session.metadata is not None
    assert session.metadata.status == "completed"
    assert session.metadata.tenant_id == "integration_test"

    # Timeline verification
    assert len(session.timeline) == 10
    assert session.timeline[0].event_type == EventType.SESSION_START
    assert session.timeline[-1].event_type == EventType.SESSION_END

    # Execution graph verification
    assert len(session.execution_graph) > 0
    edge_types = {e.edge_type for e in session.execution_graph}
    assert "caused_by" in edge_types  # Parent relationships
    assert "delegated_to" in edge_types  # Agent delegation
    assert "invoked" in edge_types  # Tool invocation

    # Cost attribution verification
    cost_attr = session.cost_attribution
    assert "coordinator" in cost_attr
    assert cost_attr["coordinator"] > 0
    assert session.metadata.cost_usd > 0

    # Tool lifecycle verification
    tools = session.tool_lifecycle
    assert len(tools) == 1
    assert tools[0]["tool_name"] == "web_search"
    assert tools[0]["status"] == "success"
    assert tools[0]["agent"] == "researcher"
    assert tools[0]["duration_ms"] > 0

    # Lineage verification
    last_event = session.timeline[-1]
    lineage = session.lineage(last_event.event_id)
    assert len(lineage) > 1
    assert last_event.event_id in lineage

    # Agents verification
    assert "coordinator" in session.agents
    assert "researcher" in session.agents
    assert len(session.agents) == 2

    # Token tracking
    assert session.total_tokens == 1800  # 1500 + 300


def test_full_pipeline_with_memory_operations():
    """Test pipeline with memory read/write patterns."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {"span_id": "span_001"}
        },
        {
            "span_name": "memory.write",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {
                "span_id": "span_002",
                "parent_span_id": "span_001",
                "agent_id": "agent_a",
                "memory_key": "user_preference"
            }
        },
        {
            "span_name": "memory.read",
            "start_time": "2026-07-16T10:00:02Z",
            "attributes": {
                "span_id": "span_003",
                "parent_span_id": "span_001",
                "agent_id": "agent_b",
                "memory_key": "user_preference"
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:03Z",
            "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="memory-test")

    # Verify memory read edge created
    memory_edges = [e for e in session.execution_graph if e.edge_type == "read_from"]
    assert len(memory_edges) == 1
    assert memory_edges[0].source_event_id == "span_002"  # Write
    assert memory_edges[0].target_event_id == "span_003"  # Read


def test_full_pipeline_with_multiple_model_calls():
    """Test cost attribution with multiple model calls."""
    spans = [
        {
            "span_name": "session.start",
            "start_time": "2026-07-16T10:00:00Z",
            "attributes": {"span_id": "span_001"}
        },
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:01Z",
            "attributes": {
                "span_id": "span_002",
                "parent_span_id": "span_001",
                "agent_id": "agent_a",
                "input_tokens": 1000,
                "output_tokens": 200
            }
        },
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:02Z",
            "attributes": {
                "span_id": "span_003",
                "parent_span_id": "span_001",
                "agent_id": "agent_b",
                "input_tokens": 2000,
                "output_tokens": 500
            }
        },
        {
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:03Z",
            "attributes": {
                "span_id": "span_004",
                "parent_span_id": "span_001",
                "agent_id": "agent_a",
                "input_tokens": 500,
                "output_tokens": 100
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:04Z",
            "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}
        }
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="multi-model")

    # Verify cost attribution
    cost_attr = session.cost_attribution
    assert "agent_a" in cost_attr
    assert "agent_b" in cost_attr

    # Agent A: (1000 * 3 / 1M) + (200 * 15 / 1M) + (500 * 3 / 1M) + (100 * 15 / 1M)
    expected_a = (1000 * 3 + 200 * 15 + 500 * 3 + 100 * 15) / 1_000_000
    # Agent B: (2000 * 3 / 1M) + (500 * 15 / 1M)
    expected_b = (2000 * 3 + 500 * 15) / 1_000_000

    assert abs(cost_attr["agent_a"] - expected_a) < 0.0001
    assert abs(cost_attr["agent_b"] - expected_b) < 0.0001

    # Verify total tokens
    assert session.total_tokens == 4300  # 1000+200+2000+500+500+100
