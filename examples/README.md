# Examples

Runnable examples demonstrating agent-session-graph usage patterns.

All examples work out-of-the-box by loading realistic OTel trace files from the `data/` directory — no setup required!

## Quick Start

### 00_high_level_api.py
**High-level SessionReconstructor API**

Shows:
- Simple, ergonomic API that matches the README
- Loading traces from JSON files
- Reconstructing from in-memory spans
- Exploring sessions with rich query methods
- No manual builder wiring

Run: `python examples/00_high_level_api.py`

### 01_basic_usage.py
**Low-level API with full control**

Shows:
- Normalizing OTel spans to SessionEvents
- Processing events through SessionBuilder
- Inferring causal edges with GraphBuilder
- Running anomaly detection
- Using InMemoryStorage

Run: `python examples/01_basic_usage.py`

### test_all_traces.py
**Validate all sample trace files**

Shows:
- Loading and validating each trace file
- Verifying expected anomalies are detected
- Summary statistics for each scenario

Run: `python examples/test_all_traces.py`

### 02_custom_storage.py (TODO)
**Implementing StorageBackend for SQLite**

Shows:
- Defining custom storage backend
- Persisting to SQLite database
- Querying sessions across restarts

### 03_graph_analysis.py (TODO)
**Traversing the execution graph**

Shows:
- Finding delegation chains
- Tracing back causality ("why did X happen?")
- Analyzing tool interaction patterns

### 04_replay_debugging.py (TODO)
**Time-travel replay**

Shows:
- Replaying session to specific sequence number
- Reconstructing point-in-time state
- Debugging state evolution

### 05_instrumentation.py (TODO)
**Setting up OTel tracing**

Shows:
- Instrumenting agent code with OTel SDK
- Emitting spans that agent-session-graph can consume
- Best practices for span naming

### 06_custom_detector.py (TODO)
**Writing your own detector**

Shows:
- Building custom anomaly detection on the primitives
- Iterating over events
- Emitting findings
- Integration with storage backend

## Sample Data

The `data/` directory contains realistic OTel trace files ready to use:

| File | Scenario | Purpose |
|------|----------|---------|
| **healthy_session.json** | Normal multi-agent workflow | Baseline for testing, clean execution |
| **recursive_loop.json** | Agent delegation cycle (A↔B) | Demonstrates recursive loop detection |
| **token_explosion.json** | Exponential context growth | Shows cost amplification across agents |
| **context_loss.json** | Context compaction + instruction loss | Illustrates policy violations after compaction |

See [data/README.md](data/README.md) for detailed documentation of each trace file.

### Using Sample Data

```python
from agent_session_graph import SessionReconstructor

# High-level API
reconstructor = SessionReconstructor()
session = reconstructor.from_otlp_json("examples/data/healthy_session.json")

# Explore
print(f"Agents: {', '.join(session.agents)}")
print(f"Total tokens: {session.total_tokens:,}")
print(f"Cost: ${session.metadata.cost_usd:.4f}")
```

## Fixtures (for programmatic use)

The `fixtures/` directory contains Python modules with span data for testing:
- `healthy_session.py` - Normal execution (programmatic access)

Use these when you need to import spans directly into your test code rather than loading from JSON files.

## Running Examples

All examples are standalone Python scripts. Install agent-session-graph first:

```bash
pip install -e .
```

Then run any example:

```bash
python examples/01_basic_usage.py
```

For examples requiring optional dependencies (e.g., instrumentation):

```bash
pip install -e ".[instrumentation]"
python examples/05_instrumentation.py
```
