# High-Level API: SessionReconstructor

## Overview

The `SessionReconstructor` class provides an ergonomic high-level API that matches the README examples. It wraps the low-level primitives (`SessionBuilder`, `GraphBuilder`, storage) into a simple workflow.

## Why Two APIs?

**High-level API (SessionReconstructor)** - Recommended for most users:
- ✅ Simple, fewer lines of code
- ✅ Returns rich `Session` objects with query methods
- ✅ No manual wiring of builders and storage
- ✅ Matches README examples

**Low-level API (SessionBuilder + GraphBuilder)** - For advanced use:
- ✅ Full control over storage backend
- ✅ Custom event processing logic
- ✅ Integration with existing systems
- ✅ Building custom higher-level abstractions

## Quick Start

```python
from agent_session_graph import SessionReconstructor

# Create reconstructor (uses InMemoryStorage by default)
reconstructor = SessionReconstructor()

# Method 1: From JSON file
session = reconstructor.from_otlp_json("traces.json")

# Method 2: From in-memory spans (more common)
session = reconstructor.from_otlp_spans(otel_spans, session_id="sess_001")

# Explore the session
print(session.execution_graph)       # Full causal graph
print(session.timeline)              # Chronological events
print(session.lineage("event_42"))   # Why did this happen?
print(session.cost_attribution)      # Cost by agent
print(session.tool_lifecycle)        # Tool invocations
```

## Session Object Properties

### Basic Info
```python
session.id                    # Session identifier
session.metadata              # SessionMetadata object
session.agents                # List of participant IDs
session.total_tokens          # Total input + output tokens
```

### Queries
```python
session.execution_graph       # List[ExecutionEdge] - causal graph
session.timeline              # List[SessionEvent] - chronological
session.lineage(event_id)     # List[str] - causal chain
session.cost_attribution      # Dict[str, float] - cost by agent
session.tool_lifecycle        # List[dict] - tool invocations
```

## Examples

### Example 1: Analyze Multi-Agent Session

```python
from agent_session_graph import SessionReconstructor

reconstructor = SessionReconstructor()
session = reconstructor.from_otlp_json("multi_agent_trace.json")

# Who did what?
print(f"Agents: {', '.join(session.agents)}")
print(f"Total cost: ${session.metadata.cost_usd:.4f}")

# Cost breakdown
for agent_id, cost in session.cost_attribution.items():
    print(f"  {agent_id}: ${cost:.4f}")

# Find most expensive event
events_by_cost = []
for event in session.timeline:
    if event.event_type == "MODEL_CALL":
        tokens = event.payload.get("input_tokens", 0) + event.payload.get("output_tokens", 0)
        events_by_cost.append((event, tokens))

most_expensive = max(events_by_cost, key=lambda x: x[1])
print(f"Most expensive call: {most_expensive[0].participant_id} ({most_expensive[1]} tokens)")
```

### Example 2: Trace Failure Back to Root Cause

```python
from agent_session_graph import SessionReconstructor

reconstructor = SessionReconstructor()
session = reconstructor.from_otlp_json("failed_session.json")

# Find the error
error_events = [e for e in session.timeline if e.event_type == "TOOL_ERROR"]

for error in error_events:
    print(f"Error: {error.event_id}")
    print(f"  Agent: {error.participant_id}")
    print(f"  Tool: {error.payload.get('tool_name')}")
    
    # Trace back to find what triggered this
    lineage = session.lineage(error.event_id)
    print(f"  Caused by chain:")
    for event_id in lineage[:5]:  # Show first 5
        event = next(e for e in session.timeline if e.event_id == event_id)
        print(f"    → {event.event_type} at seq={event.seq}")
```

### Example 3: Analyze Tool Usage Patterns

```python
from agent_session_graph import SessionReconstructor

reconstructor = SessionReconstructor()
session = reconstructor.from_otlp_json("session.json")

# Tool success rate
tools = session.tool_lifecycle
total = len(tools)
successes = sum(1 for t in tools if t["status"] == "success")
print(f"Tool success rate: {successes}/{total} ({100*successes/total:.1f}%)")

# Average latency by tool
from collections import defaultdict
tool_latencies = defaultdict(list)
for tool in tools:
    tool_latencies[tool["tool_name"]].append(tool["duration_ms"])

for tool_name, latencies in tool_latencies.items():
    avg = sum(latencies) / len(latencies)
    print(f"{tool_name}: {avg:.0f}ms avg (n={len(latencies)})")
```

## Using Custom Storage

```python
from agent_session_graph import SessionReconstructor
from agent_session_graph.storage import InMemoryStorage

# Custom storage (e.g., your own SQLite backend)
storage = InMemoryStorage()  # Or your custom implementation

reconstructor = SessionReconstructor(storage=storage)
session = reconstructor.from_otlp_spans(spans)

# Session data persists in your storage backend
events = storage.get_events_by_session(session.id)
```

## Low-Level API Alternative

For comparison, here's the equivalent low-level code:

```python
from agent_session_graph import SessionBuilder, GraphBuilder
from agent_session_graph.ingestion import normalize_trace
from agent_session_graph.storage import InMemoryStorage

# High-level (1 line)
session = reconstructor.from_otlp_spans(spans, session_id="sess_001")

# Low-level (6+ lines)
storage = InMemoryStorage()
builder = SessionBuilder(storage=storage)
graph_builder = GraphBuilder(storage=storage)

events = normalize_trace(spans, session_id="sess_001")
for event in events:
    builder.process_event(event)
edges = graph_builder.infer_edges(events)
metadata = builder.get_session_state("sess_001")

# Then manually construct result object
# ...
```

## API Reference

### SessionReconstructor

```python
class SessionReconstructor:
    def __init__(self, storage: StorageBackend | None = None) -> None:
        """Initialize with optional storage backend."""

    def from_otlp_json(self, filepath: str | Path) -> Session:
        """Reconstruct from JSON file."""

    def from_otlp_spans(
        self,
        spans: list[dict[str, Any]],
        session_id: str | None = None
    ) -> Session:
        """Reconstruct from span list."""

    def stream(self) -> Iterator[Session]:
        """Real-time streaming (not yet implemented)."""
```

### Session

```python
class Session:
    # Properties
    id: str
    metadata: SessionMetadata
    execution_graph: list[ExecutionEdge]
    timeline: list[SessionEvent]
    agents: list[str]
    total_tokens: int

    # Methods
    def lineage(self, event_id: str) -> list[str]:
        """Trace causal chain."""

    @property
    def cost_attribution(self) -> dict[str, float]:
        """Cost breakdown by agent."""

    @property
    def tool_lifecycle(self) -> list[dict[str, Any]]:
        """Tool invocations and outcomes."""
```

## Testing

Run the high-level API example:
```bash
python examples/00_high_level_api.py
```

Run tests:
```bash
pytest tests/test_session_reconstructor.py -v
```

## Files

- Implementation: `src/agent_session_graph/session_reconstructor.py`
- Example: `examples/00_high_level_api.py`
- Tests: `tests/test_session_reconstructor.py`
