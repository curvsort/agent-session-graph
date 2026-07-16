"""
High-level API: SessionReconstructor convenience interface

This example demonstrates the ergonomic high-level API that matches
the README examples. Uses SessionReconstructor to wrap the low-level
primitives into a simple workflow.

Compare to 01_basic_usage.py which shows the low-level API.

By default, loads data/healthy_session.json for immediate use.
"""
from agent_session_graph import SessionReconstructor
import json
from pathlib import Path

# Path to sample trace data
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TRACE_FILE = DATA_DIR / "healthy_session.json"

# Load sample OTel trace data from file
if DEFAULT_TRACE_FILE.exists():
    with open(DEFAULT_TRACE_FILE) as f:
        trace_data = json.load(f)
else:
    # Fallback: inline data if file doesn't exist
    trace_data = {
        "session_id": "demo-high-level-001",
        "spans": [
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
                "input_tokens": 2000,
                "output_tokens": 500
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
            "span_name": "model.call",
            "start_time": "2026-07-16T10:00:11Z",
            "attributes": {
                "span_id": "span_008",
                "parent_span_id": "span_005",
                "agent_id": "researcher",
                "model": "claude-3.5-sonnet",
                "input_tokens": 3000,
                "output_tokens": 800
            }
        },
        {
            "span_name": "agent.end",
            "start_time": "2026-07-16T10:00:15Z",
            "attributes": {
                "span_id": "span_009",
                "parent_span_id": "span_004",
                "agent_id": "researcher"
            }
        },
        {
            "span_name": "agent.end",
            "start_time": "2026-07-16T10:00:16Z",
            "attributes": {
                "span_id": "span_010",
                "parent_span_id": "span_001",
                "agent_id": "coordinator"
            }
        },
        {
            "span_name": "session.end",
            "start_time": "2026-07-16T10:00:17Z",
            "attributes": {
                "span_id": "span_011",
                "parent_span_id": "span_001"
            }
        }
    ]
    }

def main():
    print("=" * 70)
    print("agent-session-graph: High-Level API Example")
    print("=" * 70)

    # Method 1: From JSON file (using included sample data)
    print("\n[1] Reconstructing from JSON file...")
    if DEFAULT_TRACE_FILE.exists():
        print(f"    Loading: {DEFAULT_TRACE_FILE.name}")
        reconstructor = SessionReconstructor()
        session = reconstructor.from_otlp_json(str(DEFAULT_TRACE_FILE))
        print(f"    ✓ Session reconstructed: {session}")
    else:
        print(f"    ⚠ Sample data not found at {DEFAULT_TRACE_FILE}")
        print(f"    Skipping file-based loading...")

    # Method 2: From in-memory spans (more common)
    print("\n[2] Reconstructing from in-memory spans...")
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_spans(
        trace_data["spans"],
        session_id=trace_data["session_id"]
    )
    print(f"    ✓ Session: {session}")

    # Explore the session with high-level API
    print("\n[3] Exploring the session...")

    print(f"\n  Basic info:")
    print(f"    - Session ID: {session.id}")
    print(f"    - Status: {session.metadata.status}")
    print(f"    - Agents: {', '.join(session.agents)}")
    print(f"    - Total tokens: {session.total_tokens:,}")
    print(f"    - Cost: ${session.metadata.cost_usd:.4f}")

    print(f"\n  Execution graph:")
    print(f"    - {len(session.execution_graph)} edges")
    edge_counts = {}
    for edge in session.execution_graph:
        edge_counts[edge.edge_type] = edge_counts.get(edge.edge_type, 0) + 1
    for edge_type, count in sorted(edge_counts.items()):
        print(f"      • {edge_type}: {count}")

    print(f"\n  Timeline:")
    print(f"    - {len(session.timeline)} events")
    for event in session.timeline[:3]:  # Show first 3
        print(f"      • seq={event.seq}: {event.event_type}")
    if len(session.timeline) > 3:
        print(f"      • ... and {len(session.timeline) - 3} more")

    # Lineage tracing (WHY did this event happen?)
    print(f"\n  Lineage tracing:")
    last_event_id = session.timeline[-1].event_id
    lineage = session.lineage(last_event_id)
    print(f"    - Tracing back from: {last_event_id}")
    print(f"    - Causal chain ({len(lineage)} steps):")
    for i, event_id in enumerate(lineage[:5], 1):  # Show first 5
        event = next(e for e in session.timeline if e.event_id == event_id)
        print(f"      {i}. {event_id} ({event.event_type})")
    if len(lineage) > 5:
        print(f"      ... and {len(lineage) - 5} more")

    # Cost attribution by agent
    print(f"\n  Cost attribution:")
    for agent_id, cost in session.cost_attribution.items():
        print(f"    - {agent_id}: ${cost:.4f}")

    # Tool lifecycle
    print(f"\n  Tool invocations:")
    for tool in session.tool_lifecycle:
        print(f"    - {tool['tool_name']} by {tool['agent']}: "
              f"{tool['status']} ({tool['duration_ms']}ms)")

    print("\n" + "=" * 70)
    print("✓ High-level API demonstration complete!")
    print("=" * 70)
    print("\nKey benefits of SessionReconstructor:")
    print("  1. Simple, ergonomic API (fewer lines of code)")
    print("  2. Returns rich Session objects with query methods")
    print("  3. No manual wiring of builders and storage")
    print("  4. Matches the README examples")
    print("\nNext steps:")
    print("  - Try other scenarios: data/recursive_loop.json, data/token_explosion.json")
    print("  - See 01_basic_usage.py for the low-level API")
    print("  - See data/README.md for trace file documentation")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
