"""
Reference detector integration tests.

Tests the actual detection logic with realistic patterns:
- Recursive loops
- Token explosions
- Context compaction inference
"""
import pytest
from agent_session_graph import SessionReconstructor
from agent_session_graph.detection import AnomalyDetector
from agent_session_graph.storage import InMemoryStorage


def test_recursive_loop_detection():
    """Test detection of recursive agent delegation loop."""
    # Pattern: Agent A delegates to Agent B repeatedly
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # First delegation
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "delegated_to": "agent_b"}},
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_002",
                       "agent_id": "agent_b"}},

        # Second delegation (same pattern)
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "delegated_to": "agent_b"}},
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:04Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_004",
                       "agent_id": "agent_b"}},

        # Third delegation (triggers threshold)
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:05Z",
         "attributes": {"span_id": "span_006", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "delegated_to": "agent_b"}},
        {"span_name": "agent.start", "start_time": "2026-07-16T10:00:06Z",
         "attributes": {"span_id": "span_007", "parent_span_id": "span_006",
                       "agent_id": "agent_b"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_008", "parent_span_id": "span_001"}},
    ]

    # Reconstruct session
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="loop-test")

    # Run detection
    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_recursive_loop(
        session.id,
        session.timeline,
        session.execution_graph,
        threshold=3
    )

    # Should detect the loop
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "recursive_agent_loop"
    assert finding.severity == "critical"
    assert "agent_a" in finding.root_cause_summary
    assert "agent_b" in finding.root_cause_summary
    assert len(finding.triggering_event_ids) == 3  # Three delegate events


def test_no_recursive_loop_below_threshold():
    """Test that below-threshold delegations don't trigger detection."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Only 2 delegations (below default threshold of 3)
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "delegated_to": "agent_b"}},
        {"span_name": "agent.delegate", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "delegated_to": "agent_b"}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="no-loop")

    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_recursive_loop(
        session.id,
        session.timeline,
        session.execution_graph
    )

    assert len(findings) == 0


def test_token_explosion_detection():
    """Test detection of token count explosion."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Escalating token usage (3x growth)
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 1000, "output_tokens": 200}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 2000, "output_tokens": 500}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 8000, "output_tokens": 1500}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="explosion-test")

    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_token_explosion(
        session.id,
        session.timeline,
        growth_threshold=3.0
    )

    # Should detect explosion (1200 → 2500 → 9500, growth > 3x)
    assert len(findings) >= 1
    finding = findings[0]
    assert finding.finding_type == "token_explosion"
    assert finding.severity in ["medium", "high"]
    assert "growth" in finding.root_cause_summary.lower()


def test_no_token_explosion_steady_growth():
    """Test that steady growth doesn't trigger explosion detection."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # Steady growth (< 3x)
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 1000, "output_tokens": 200}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 1500, "output_tokens": 300}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 2000, "output_tokens": 400}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="steady-growth")

    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_token_explosion(
        session.id,
        session.timeline,
        growth_threshold=3.0
    )

    assert len(findings) == 0


def test_probable_compaction_detection():
    """Test detection of inferred context compaction (token drop)."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        # High token count
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 50000, "output_tokens": 1000}},

        # Sudden drop (>40%) without explicit CONTEXT_COMPACTION event
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 10000, "output_tokens": 500}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="compaction-test")

    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_probable_compaction(
        session.id,
        session.timeline
    )

    # Should detect probable compaction (80% drop)
    assert len(findings) >= 1
    finding = findings[0]
    assert finding.finding_type == "probable_compaction_inferred"
    assert finding.severity == "medium"
    assert "40%" in finding.root_cause_summary or "drop" in finding.root_cause_summary.lower()


def test_no_compaction_with_explicit_event():
    """Test that explicit CONTEXT_COMPACTION event prevents false positive."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},

        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 50000, "output_tokens": 1000}},

        # Explicit compaction event
        {"span_name": "context.compaction", "start_time": "2026-07-16T10:00:02Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001",
                       "agent_id": "agent_a"}},

        # Drop after explicit event
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:03Z",
         "attributes": {"span_id": "span_004", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 10000, "output_tokens": 500}},

        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_005", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="explicit-compaction")

    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)
    findings = detector.check_probable_compaction(
        session.id,
        session.timeline
    )

    # Should not flag as "probable" since there was an explicit event
    assert len(findings) == 0


def test_run_all_checks():
    """Test running all detection rules together."""
    spans = [
        {"span_name": "session.start", "start_time": "2026-07-16T10:00:00Z",
         "attributes": {"span_id": "span_001"}},
        {"span_name": "model.call", "start_time": "2026-07-16T10:00:01Z",
         "attributes": {"span_id": "span_002", "parent_span_id": "span_001",
                       "agent_id": "agent_a", "input_tokens": 1000, "output_tokens": 200}},
        {"span_name": "session.end", "start_time": "2026-07-16T10:00:10Z",
         "attributes": {"span_id": "span_003", "parent_span_id": "span_001"}},
    ]

    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(spans, session_id="all-checks")

    storage = InMemoryStorage()
    detector = AnomalyDetector(storage=storage)

    # Run all checks
    all_findings = detector.run_all_checks(
        session.id,
        session.timeline,
        session.execution_graph
    )

    # Healthy session should have no findings
    assert len(all_findings) == 0
