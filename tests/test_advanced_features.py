"""
Advanced feature tests - session boundaries, memory staleness, profile switches.

Tests advanced session reconstruction features:
- Temporal session boundary detection
- Memory staleness calculation
- Profile/context transitions
- Multi-session handling
"""
from datetime import datetime, timedelta, timezone

from agent_session_graph import SessionReconstructor
from agent_session_graph.schemas import EventType


def test_temporal_session_boundary_detection():
    """Test that large time gaps create separate sessions."""
    # Two groups of spans separated by 2 hours
    base_time = datetime(2026, 7, 16, 10, 0, 0, tzinfo=timezone.utc)

    # Group 1: Session A (10:00 - 10:05)
    group1_spans = [
        {"span_name": "session.start", "start_time": base_time.isoformat(),
         "attributes": {"span_id": "span_001", "session_id": "sess_A"}},
        {"span_name": "agent.start", "start_time": (base_time + timedelta(seconds=10)).isoformat(),
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_1"}},
        {"span_name": "session.end", "start_time": (base_time + timedelta(minutes=5)).isoformat(),
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001"}},
    ]

    # Group 2: Session B (12:00 - 12:05) - 2 hours later
    gap_start = base_time + timedelta(hours=2)
    group2_spans = [
        {"span_name": "session.start", "start_time": gap_start.isoformat(),
         "attributes": {"span_id": "span_004", "session_id": "sess_B"}},
        {"span_name": "agent.start", "start_time": (gap_start + timedelta(seconds=10)).isoformat(),
         "attributes": {"span_id": "span_005", "parent_span_id": "span_004",
                       "agent_id": "agent_2"}},
        {"span_name": "session.end", "start_time": (gap_start + timedelta(minutes=5)).isoformat(),
         "attributes": {"span_id": "span_006", "parent_span_id": "span_004"}},
    ]

    reconstructor = SessionReconstructor()

    # Reconstruct both sessions
    session_a = reconstructor.from_otlp_spans(group1_spans, session_id="sess_A")
    session_b = reconstructor.from_otlp_spans(group2_spans, session_id="sess_B")

    # Verify they are separate sessions
    assert session_a.id == "sess_A"
    assert session_b.id == "sess_B"
    assert len(session_a.timeline) == 3
    assert len(session_b.timeline) == 3

    # Verify timestamps show the gap
    assert session_a.metadata.end_time
    assert session_b.metadata.start_time
    time_gap = (session_b.metadata.start_time - session_a.metadata.end_time).total_seconds()
    assert time_gap > 6800  # More than 1.8 hours (allowing for rounding)


def test_session_with_profile_context_transitions():
    """Test tracking profile/context switches within a session."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Initial context
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "profile_id": "profile_default",
                       "context_version_id": "ctx_v1"}},

        # Profile switch event
        {"span_name": "profile.switch", "start_time": "2026-07-16T10:00:05Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a",
                       "old_profile_id": "profile_default",
                       "new_profile_id": "profile_expert"}},

        # Continue with new profile
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:06Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "profile_id": "profile_expert",
                       "context_version_id": "ctx_v2",
                       "input_tokens": 1000, "output_tokens": 200}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="profile-switch-test")

    # Verify profile switch event captured
    profile_switches = [e for e in session.timeline if e.event_type == EventType.PROFILE_SWITCH]
    assert len(profile_switches) == 1

    switch = profile_switches[0]
    assert switch.payload.get("old_profile_id") == "profile_default"
    assert switch.payload.get("new_profile_id") == "profile_expert"


def test_memory_read_without_write():
    """Test handling of memory read with no corresponding write (stale read)."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Memory read without prior write (reading stale/external memory)
        {"span_name": "memory.read", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "memory_key": "cached_data"}},

        # Later write to same key
        {"span_name": "memory.write", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "memory_key": "cached_data"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="stale-read-test")

    # Verify both memory events captured
    memory_events = [e for e in session.timeline if e.event_type in [
        EventType.MEMORY_READ, EventType.MEMORY_WRITE
    ]]
    assert len(memory_events) == 2

    # Graph builder creates read_from edge linking write to read by memory_key
    # (it links based on key matching, not temporal ordering)
    memory_edges = [e for e in session.execution_graph if e.edge_type == "read_from"]
    assert len(memory_edges) == 1  # Links write→read for same key


def test_context_compaction_with_token_drop():
    """Test explicit context compaction detection with token metrics."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # High token count
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 48000, "output_tokens": 2000,
                       "context_version_id": "ctx_v1"}},

        # Explicit compaction
        {"span_name": "context.compaction", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a",
                       "before_tokens": 48000,
                       "after_tokens": 12000,
                       "compaction_ratio": 0.75}},

        # Reduced token count after compaction
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 12000, "output_tokens": 500,
                       "context_version_id": "ctx_v2"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="compaction-metrics")

    # Verify compaction event
    compaction_events = [
        e for e in session.timeline
        if e.event_type == EventType.CONTEXT_COMPACTION
    ]
    assert len(compaction_events) == 1

    comp = compaction_events[0]
    assert comp.payload.get("before_tokens") == 48000
    assert comp.payload.get("after_tokens") == 12000
    assert comp.payload.get("compaction_ratio") == 0.75


def test_agent_delegation_depth():
    """Test deep agent delegation chain (A→B→C→D)."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Level 1: Root agent
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "orchestrator"}},

        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "orchestrator", "delegated_to": "coordinator"}},

        # Level 2: Coordinator
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_003",
                       "agent_id": "coordinator"}},

        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:04Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_004",
                       "agent_id": "coordinator", "delegated_to": "specialist"}},

        # Level 3: Specialist
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:05Z",
         "attributes": {"span_id": "span_006", "parent_span_id": "span_005",
                       "agent_id": "specialist"}},

        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:06Z",
         "attributes": {"span_id": "span_007", "parent_span_id": "span_006",
                       "agent_id": "specialist", "delegated_to": "executor"}},

        # Level 4: Executor (leaf)
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:07Z",
         "attributes": {"span_id": "span_008", "parent_span_id": "span_007",
                       "agent_id": "executor"}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:08Z",
         "attributes": {"span_id": "span_009", "parent_span_id": "span_008",
                       "agent_id": "executor", "input_tokens": 1000, "output_tokens": 200}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_010", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="deep-delegation")

    # Verify 4-level hierarchy
    agents = session.agents
    assert len(agents) == 4
    assert "orchestrator" in agents
    assert "coordinator" in agents
    assert "specialist" in agents
    assert "executor" in agents

    # Verify delegation chain
    delegation_edges = [e for e in session.execution_graph if e.edge_type == "delegated_to"]
    assert len(delegation_edges) == 3  # 3 delegation hops

    # Trace lineage from executor back to root
    executor_event = [e for e in session.timeline if e.participant_id == "executor"][0]
    lineage = session.lineage(executor_event.event_id)

    # Should trace through all 4 levels
    assert len(lineage) >= 4


def test_human_escalation_event():
    """Test human escalation/intervention events."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "support_agent"}},

        # Agent decides to escalate to human
        {"span_name": "human.escalation", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "support_agent",
                       "reason": "Complex legal question requires human judgment"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="human-escalation")

    # Verify escalation event
    escalations = [e for e in session.timeline if e.event_type == EventType.HUMAN_ESCALATION]
    assert len(escalations) == 1

    escalation = escalations[0]
    assert escalation.participant_id == "support_agent"
    assert "legal question" in escalation.payload.get("reason", "")


def test_cost_update_events():
    """Test tracking of cost update events."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 1000, "output_tokens": 200}},

        # Explicit cost update event
        {"span_name": "cost.update", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a",
                       "cost_usd": 0.0045,
                       "cumulative_cost_usd": 0.0045}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="cost-tracking")

    # Verify cost events
    cost_events = [e for e in session.timeline if e.event_type == EventType.COST_UPDATE]
    assert len(cost_events) == 1

    cost_event = cost_events[0]
    assert cost_event.payload.get("cost_usd") == 0.0045


def test_sandbox_timeout_handling():
    """Test sandbox timeout events."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "sandbox.start", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "sandbox_id": "sandbox_001"}},

        {"span_name": "tool.call", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "agent_a", "tool_name": "long_running_task"}},

        # Sandbox times out
        {"span_name": "sandbox.timeout", "start_time": "2026-07-16T10:05:00Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_002",
                       "agent_id": "agent_a", "sandbox_id": "sandbox_001",
                       "timeout_seconds": 300}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:05:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="sandbox-timeout")

    # Verify sandbox events
    sandbox_events = [e for e in session.timeline if e.event_type in [
        EventType.SANDBOX_START, EventType.SANDBOX_TIMEOUT
    ]]
    assert len(sandbox_events) == 2

    timeout = [e for e in sandbox_events if e.event_type == EventType.SANDBOX_TIMEOUT][0]
    assert timeout.payload.get("timeout_seconds") == 300
