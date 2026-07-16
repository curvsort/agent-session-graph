"""
Basic usage: normalize OTel spans → build session → detect anomalies

This example shows the minimal end-to-end flow:
1. Normalize OTel spans into SessionEvents
2. Process events through SessionBuilder
3. Infer causal edges with GraphBuilder
4. Run anomaly detection

No external dependencies required - uses InMemoryStorage.

By default, loads data/healthy_session.json for immediate use.
"""
from agent_session_graph import (
    SessionBuilder,
    GraphBuilder,
    normalize_span,
    InMemoryStorage,
    AnomalyDetector
)
import json
from pathlib import Path

# Path to sample trace data
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRACE_FILE = DATA_DIR / "healthy_session.json"

# Load sample OTel spans from file
if DEFAULT_TRACE_FILE.exists():
    with open(DEFAULT_TRACE_FILE) as f:
        trace_data = json.load(f)
    otel_spans = trace_data["spans"]
    session_id = trace_data["session_id"]
else:
    # Fallback: inline spans if file doesn't exist
    session_id = "demo-session-001"
    otel_spans = [
    {
        "span_name": "session.start",
        "start_time": "2026-07-16T10:00:00Z",
        "attributes": {
            "span_id": "span_001",
            "tenant_id": "demo_tenant",
            "application_id": "demo_app"
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
        "span_name": "tool.call",
        "start_time": "2026-07-16T10:00:05Z",
        "attributes": {
            "span_id": "span_004",
            "parent_span_id": "span_002",
            "agent_id": "coordinator",
            "tool_name": "web_search"
        }
    },
    {
        "span_name": "tool.result",
        "start_time": "2026-07-16T10:00:08Z",
        "attributes": {
            "span_id": "span_005",
            "parent_span_id": "span_004",
            "agent_id": "coordinator",
            "status": "success"
        }
    },
    {
        "span_name": "agent.end",
        "start_time": "2026-07-16T10:00:10Z",
        "attributes": {
            "span_id": "span_006",
            "parent_span_id": "span_001",
            "agent_id": "coordinator"
        }
    },
    {
        "span_name": "session.end",
        "start_time": "2026-07-16T10:00:11Z",
        "attributes": {
            "span_id": "span_007",
            "parent_span_id": "span_001"
        }
    }
    ]

def main():
    print("=" * 70)
    print("agent-session-graph: Basic Usage Example")
    print("=" * 70)

    if DEFAULT_TRACE_FILE.exists():
        print(f"\nUsing sample data: {DEFAULT_TRACE_FILE.name}")
    else:
        print(f"\nUsing inline fallback data")

    # Step 1: Set up storage
    print("\n[1] Setting up in-memory storage...")
    storage = InMemoryStorage()
    print("    ✓ InMemoryStorage initialized")

    # Step 2: Normalize OTel spans to SessionEvents
    print(f"\n[2] Normalizing {len(otel_spans)} OTel spans...")
    events = []
    for idx, span in enumerate(otel_spans, start=1):
        event = normalize_span(span, session_id=session_id, seq=idx)
        events.append(event)
        print(f"    seq={event.seq}: {event.event_type} from {event.participant_id or 'system'}")

    # Step 3: Build session state
    print(f"\n[3] Processing events through SessionBuilder...")
    builder = SessionBuilder(storage=storage)
    for event in events:
        builder.process_event(event)

    # Get final session state
    session_metadata = builder.get_session_state(session_id)
    print(f"    ✓ Session: {session_metadata.status}")
    print(f"    ✓ Token usage: {session_metadata.token_usage.input} input, "
          f"{session_metadata.token_usage.output} output")
    print(f"    ✓ Cost: ${session_metadata.cost_usd:.4f}")

    # Step 4: Infer execution graph
    print(f"\n[4] Inferring execution graph...")
    graph_builder = GraphBuilder(storage=storage)
    edges = graph_builder.infer_edges(events)

    edge_counts = {}
    for edge in edges:
        edge_counts[edge.edge_type] = edge_counts.get(edge.edge_type, 0) + 1

    print(f"    ✓ Inferred {len(edges)} edges:")
    for edge_type, count in sorted(edge_counts.items()):
        print(f"      - {edge_type}: {count}")

    # Step 5: Run anomaly detection
    print(f"\n[5] Running anomaly detection...")
    detector = AnomalyDetector(storage=storage)

    # Check for recursive loops
    loop_findings = detector.check_recursive_loop(session_id, events, edges)
    print(f"    - Recursive loops: {len(loop_findings)} findings")

    # Check for token explosion
    explosion_findings = detector.check_token_explosion(session_id, events)
    print(f"    - Token explosions: {len(explosion_findings)} findings")

    # Check for probable compaction
    compaction_findings = detector.check_probable_compaction(session_id, events)
    print(f"    - Probable compactions: {len(compaction_findings)} findings")

    total_findings = len(loop_findings) + len(explosion_findings) + len(compaction_findings)
    print(f"\n    ✓ Total findings: {total_findings}")

    # Step 6: Query storage for verification
    print(f"\n[6] Verifying storage contents...")
    stored_events = storage.get_events_by_session(session_id)
    stored_metadata = storage.get_metadata_by_session(session_id)
    stored_edges = storage.get_edges_by_session(session_id)
    stored_findings = storage.get_findings_by_session(session_id)

    print(f"    ✓ Events stored: {len(stored_events)}")
    print(f"    ✓ Metadata stored: {'Yes' if stored_metadata else 'No'}")
    print(f"    ✓ Edges stored: {len(stored_edges)}")
    print(f"    ✓ Findings stored: {len(stored_findings)}")

    print("\n" + "=" * 70)
    print("✓ Example complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  - Try other scenarios:")
    print("    • data/recursive_loop.json - Agent delegation cycle")
    print("    • data/token_explosion.json - Exponential context growth")
    print("    • data/context_loss.json - Context compaction with instruction loss")
    print("  - See 00_high_level_api.py for the simpler SessionReconstructor API")
    print("  - See data/README.md for detailed trace file documentation")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
