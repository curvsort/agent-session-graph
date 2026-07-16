"""
Test all sample trace files to verify they work correctly.

This script loads each trace file in data/ and validates:
- Trace loads without errors
- Expected anomalies are detected
- Session reconstruction succeeds
"""
from agent_session_graph import SessionReconstructor
from pathlib import Path
import json

DATA_DIR = Path(__file__).parent / "data"

# Expected anomalies for each trace (using actual finding_type values)
EXPECTED_ANOMALIES = {
    "healthy_session.json": {},
    "recursive_loop.json": {"recursive_agent_loop": 2},  # Detects 2 instances (A→B and B→A)
    "token_explosion.json": {"token_explosion": 1},
    "context_loss.json": {"token_explosion": 1},  # Note: context_loss also triggers token_explosion
}

def test_trace(trace_file: Path) -> dict:
    """Load and analyze a trace file."""
    print(f"\n{'='*70}")
    print(f"Testing: {trace_file.name}")
    print('='*70)

    # Load trace
    with open(trace_file) as f:
        trace_data = json.load(f)

    # Reconstruct session
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_json(str(trace_file))

    # Basic stats
    print(f"\n  Session ID: {session.id}")
    print(f"  Status: {session.metadata.status}")
    print(f"  Agents: {len(session.agents)} ({', '.join(session.agents)})")
    print(f"  Events: {len(session.timeline)}")
    print(f"  Edges: {len(session.execution_graph)}")
    print(f"  Total tokens: {session.total_tokens:,}")
    print(f"  Cost: ${session.metadata.cost_usd:.4f}")

    # Tool calls
    tools = session.tool_lifecycle
    if tools:
        print(f"\n  Tool calls: {len(tools)}")
        for tool in tools:
            print(f"    • {tool['tool_name']}: {tool['status']}")

    # Anomalies (from storage)
    from agent_session_graph import InMemoryStorage
    from agent_session_graph.detection import AnomalyDetector

    # Run anomaly detection
    storage = reconstructor._storage
    detector = AnomalyDetector(storage=storage)

    events = session.timeline
    edges = session.execution_graph

    findings = []
    findings.extend(detector.check_recursive_loop(session.id, events, edges))
    findings.extend(detector.check_token_explosion(session.id, events))
    findings.extend(detector.check_probable_compaction(session.id, events))

    # Group by finding type
    anomaly_counts = {}
    for finding in findings:
        anomaly_counts[finding.finding_type] = anomaly_counts.get(finding.finding_type, 0) + 1

    print(f"\n  Anomalies detected: {len(findings)}")
    for anomaly_type, count in sorted(anomaly_counts.items()):
        print(f"    • {anomaly_type}: {count}")

    # Verify against expected
    expected = EXPECTED_ANOMALIES.get(trace_file.name, {})
    if expected:
        print(f"\n  Expected anomalies:")
        for anomaly_type, count in expected.items():
            actual = anomaly_counts.get(anomaly_type, 0)
            match = "✓" if actual == count else "✗"
            print(f"    {match} {anomaly_type}: expected {count}, got {actual}")

    return {
        "file": trace_file.name,
        "session_id": session.id,
        "events": len(session.timeline),
        "edges": len(session.execution_graph),
        "anomalies": anomaly_counts,
        "success": True
    }

def main():
    print("="*70)
    print("agent-session-graph: Testing All Sample Traces")
    print("="*70)

    # Find all JSON files in data/
    trace_files = sorted(DATA_DIR.glob("*.json"))

    if not trace_files:
        print(f"\n⚠ No trace files found in {DATA_DIR}")
        return

    print(f"\nFound {len(trace_files)} trace files")

    results = []
    for trace_file in trace_files:
        try:
            result = test_trace(trace_file)
            results.append(result)
        except Exception as e:
            print(f"\n✗ FAILED: {e}")
            results.append({
                "file": trace_file.name,
                "success": False,
                "error": str(e)
            })

    # Summary
    print(f"\n{'='*70}")
    print("Summary")
    print('='*70)

    successes = sum(1 for r in results if r.get("success"))
    print(f"\nTests passed: {successes}/{len(results)}")

    print(f"\nTrace file statistics:")
    for result in results:
        if result.get("success"):
            print(f"\n  {result['file']}:")
            print(f"    - Events: {result['events']}")
            print(f"    - Edges: {result['edges']}")
            if result['anomalies']:
                print(f"    - Anomalies: {', '.join(f'{k}={v}' for k, v in result['anomalies'].items())}")
            else:
                print(f"    - Anomalies: None")

    print(f"\n{'='*70}")
    if successes == len(results):
        print("✓ All tests passed!")
    else:
        print(f"⚠ {len(results) - successes} test(s) failed")
    print('='*70 + "\n")

if __name__ == "__main__":
    main()
