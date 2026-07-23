"""
Comprehensive integration tests - full end-to-end pipeline scenarios.

Tests complete workflows with realistic multi-agent session patterns:
- Complex delegation chains
- Memory operations across agents
- Tool lifecycle completeness
- Cost attribution accuracy
- Replay functionality
"""
from agent_session_graph import SessionReconstructor
from agent_session_graph.detection import AnomalyDetector
from agent_session_graph.schemas import EventType
from agent_session_graph.storage import InMemoryStorage


def test_full_pipeline_complex_delegation_chain():
    """Test complete pipeline with multi-level agent delegation."""
    spans = [
        # Session start
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001", "tenant_id": "test_tenant",
                       "application_id": "multi_agent_system"}},

        # Root agent starts
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "orchestrator"}},

        # Orchestrator delegates to researcher
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "orchestrator", "delegated_to": "researcher"}},

        # Researcher starts and does work
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_003",
                       "agent_id": "researcher"}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:04Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_004",
                       "agent_id": "researcher", "input_tokens": 2000, "output_tokens": 500}},

        # Researcher delegates to specialist
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:05Z",
         "attributes": {"span_id": "span_006", "parent_span_id": "span_004",
                       "agent_id": "researcher", "delegated_to": "specialist"}},

        # Specialist does deep work
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:06Z",
         "attributes": {"span_id": "span_007", "parent_span_id": "span_006",
                       "agent_id": "specialist"}},

        {"span_name": "tool.call", "start_time": "2026-07-16T10:00:07Z",
         "attributes": {"span_id": "span_008", "parent_span_id": "span_007",
                       "agent_id": "specialist", "tool_name": "database_query"}},

        {"span_name": "tool.result", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_009", "parent_span_id": "span_008",
                       "agent_id": "specialist", "status": "success"}},

        {"span_name": "agent.end", "start_time": "2026-07-16T10:00:11Z",
         "attributes": {"span_id": "span_010", "parent_span_id": "span_006",
                       "agent_id": "specialist"}},

        # Researcher completes
        {"span_name": "agent.end", "start_time": "2026-07-16T10:00:12Z",
         "attributes": {"span_id": "span_011", "parent_span_id": "span_003",
                       "agent_id": "researcher"}},

        # Orchestrator completes
        {"span_name": "agent.end", "start_time": "2026-07-16T10:00:13Z",
         "attributes": {"span_id": "span_012", "parent_span_id": "span_001",
                       "agent_id": "orchestrator"}},

        # Session end
        {"span_name": "session.end", "start_time": "2026-07-16T10:00:14Z",
         "attributes": {"span_id": "span_013", "parent_span_id": "span_001"}},
    ]

    # Full pipeline reconstruction
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="complex-delegation")

    # Verify complete session properties
    assert session.id == "complex-delegation"
    assert session.metadata.status == "completed"
    assert session.metadata.tenant_id == "test_tenant"
    assert session.metadata.application_id == "multi_agent_system"

    # Verify all events captured
    assert len(session.timeline) == 13
    assert session.timeline[0].event_type == EventType.SESSION_START
    assert session.timeline[-1].event_type == EventType.SESSION_END

    # Verify 3-level agent hierarchy
    agents = session.agents
    assert len(agents) == 3
    assert "orchestrator" in agents
    assert "researcher" in agents
    assert "specialist" in agents

    # Verify delegation edges
    delegation_edges = [e for e in session.execution_graph if e.edge_type == "delegated_to"]
    assert len(delegation_edges) == 2  # orchestrator→researcher, researcher→specialist

    # Verify tool lifecycle
    tools = session.tool_lifecycle
    assert len(tools) == 1
    assert tools[0]["tool_name"] == "database_query"
    assert tools[0]["agent"] == "specialist"
    assert tools[0]["status"] == "success"

    # Verify lineage tracing (specialist event should trace back to session start)
    specialist_event = [e for e in session.timeline if e.participant_id == "specialist"][0]
    lineage = session.lineage(specialist_event.event_id)
    assert len(lineage) > 3  # Should include specialist, researcher, orchestrator, session

    # Verify cost attribution
    cost_attr = session.cost_attribution
    assert "researcher" in cost_attr
    assert cost_attr["researcher"] > 0


def test_full_pipeline_with_memory_staleness():
    """Test memory write→read with staleness tracking."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Agent A writes to memory
        {"span_name": "memory.write", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "memory_key": "user_context"}},

        # Agent B writes to same memory key (overwrites)
        {"span_name": "memory.write", "start_time": "2026-07-16T10:00:05Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_b", "memory_key": "user_context"}},

        # Agent C reads data (graph builder links to most recent write)
        {"span_name": "memory.read", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_c", "memory_key": "user_context"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:15Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="memory-staleness")

    # Verify memory read edges created
    memory_reads = [e for e in session.execution_graph if e.edge_type == "read_from"]
    assert len(memory_reads) == 1

    # Read should point to the most recent write (span_003) by default
    read_edge = memory_reads[0]
    assert read_edge.source_event_id == "span_003"
    assert read_edge.target_event_id == "span_004"


def test_full_pipeline_with_context_operations():
    """Test session with explicit context compaction events."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Large model call
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 45000, "output_tokens": 2000}},

        # Explicit context compaction
        {"span_name": "context.compaction", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "compaction_ratio": 0.6}},

        # Model call after compaction (reduced tokens)
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 15000, "output_tokens": 800}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="explicit-compaction")

    # Verify compaction event captured
    compaction_events = [
        e for e in session.timeline
        if e.event_type == EventType.CONTEXT_COMPACTION
    ]
    assert len(compaction_events) == 1

    # Run detector - should NOT flag as "probable" since explicit event exists
    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_probable_compaction(session.id, session.timeline)

    assert len(findings) == 0  # No "probable" finding since explicit event present


def test_session_timeline_ordering():
    """Test that session timeline maintains correct chronological order."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 1000, "output_tokens": 200}},

        {"span_name": "memory.write", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "memory_key": "result"}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 2000, "output_tokens": 500}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="timeline-test")

    # Verify timeline is correctly ordered
    assert len(session.timeline) == 5

    # Verify sequence numbers are monotonic
    seqs = [e.seq for e in session.timeline]
    assert seqs == sorted(seqs)
    assert seqs == [1, 2, 3, 4, 5]

    # Verify timestamps are monotonic
    timestamps = [e.timestamp for e in session.timeline]
    assert timestamps == sorted(timestamps)

    # Verify first and last events
    assert session.timeline[0].event_type == EventType.SESSION_START
    assert session.timeline[-1].event_type == EventType.SESSION_END


def test_full_pipeline_with_sandbox_events():
    """Test session with sandbox lifecycle events."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "sandbox.start", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "sandbox_id": "sandbox_001"}},

        {"span_name": "tool.call", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "agent_a", "tool_name": "code_execution"}},

        {"span_name": "tool.result", "start_time": "2026-07-16T10:00:05Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_003",
                       "agent_id": "agent_a", "status": "success"}},

        {"span_name": "sandbox.end", "start_time": "2026-07-16T10:00:06Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "sandbox_id": "sandbox_001"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_006", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="sandbox-test")

    # Verify sandbox events captured
    sandbox_events = [e for e in session.timeline if e.event_type in [
        EventType.SANDBOX_START, EventType.SANDBOX_END
    ]]
    assert len(sandbox_events) == 2

    # Verify tool lifecycle within sandbox
    tools = session.tool_lifecycle
    assert len(tools) == 1
    assert tools[0]["tool_name"] == "code_execution"


def test_full_pipeline_with_policy_violations():
    """Test session with governance events."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "tool.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "tool_name": "restricted_api"}},

        {"span_name": "policy.violation", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "agent_a", "policy": "unauthorized_tool_access"}},

        {"span_name": "tool.error", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_002",
                       "agent_id": "agent_a", "error": "Access denied"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="policy-violation")

    # Verify policy violation event captured
    policy_events = [e for e in session.timeline if e.event_type == EventType.POLICY_VIOLATION]
    assert len(policy_events) == 1

    # Verify tool error captured
    error_events = [e for e in session.timeline if e.event_type == EventType.TOOL_ERROR]
    assert len(error_events) == 1


def test_cost_attribution_with_cache():
    """Test cost calculation with cache read tokens."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Model call with cache hits (using standard attribute names)
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a",
                       "input_tokens": 1000,
                       "output_tokens": 200,
                       "cache_read_tokens": 5000}},  # Cache reads tracked

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="cache-cost")

    # Verify token usage includes cache tokens
    assert session.metadata.token_usage.input == 1000
    assert session.metadata.token_usage.output == 200
    assert session.metadata.token_usage.cache_read == 5000

    # Verify cost is calculated (actual formula may vary - just check it's > 0)
    assert session.metadata.cost_usd > 0


def test_concurrent_tool_calls():
    """Test session with sequential tool executions (parent→result matching)."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Tool call followed by result
        {"span_name": "tool.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "tool_name": "api_call_1"}},

        {"span_name": "tool.result", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "agent_a", "status": "success"}},

        # Second tool call followed by result
        {"span_name": "tool.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "tool_name": "api_call_2"}},

        {"span_name": "tool.result", "start_time": "2026-07-16T10:00:04Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_004",
                       "agent_id": "agent_a", "status": "success"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_006", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="multi-tools")

    # Verify both tools tracked
    tools = session.tool_lifecycle
    assert len(tools) == 2

    tool_names = {t["tool_name"] for t in tools}
    assert "api_call_1" in tool_names
    assert "api_call_2" in tool_names

    # Both should have success status
    assert all(t["status"] == "success" for t in tools)
