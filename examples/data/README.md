# Sample OTel Trace Data

This directory contains realistic OpenTelemetry trace files that demonstrate different agent execution scenarios. These files are used by the example scripts and can be used for testing your own integrations.

All traces use a consistent span structure compatible with `agent-session-graph` ingestion:
- `span_name`: Event type identifier
- `start_time`: ISO 8601 timestamp
- `attributes`: Span metadata (span_id, parent_span_id, agent_id, etc.)

## Trace Files

### 1. healthy_session.json
**Normal multi-agent workflow with successful completion**

A clean execution showing:
- Orchestrator agent starts and delegates to a research agent
- Research agent performs a web search tool call
- Model calls with realistic token counts
- All operations complete successfully
- No anomalies detected

**Use for:**
- Verifying basic ingestion pipeline
- Testing graph reconstruction
- Baseline for comparing anomalous sessions
- Integration testing with successful outcomes

**Stats:**
- Duration: ~5 seconds
- Agents: 2 (orchestrator, researcher)
- Total tokens: 5,330 (input: 4,700, output: 630)
- Tool calls: 1 (web_search, success)
- Model calls: 2
- Status: completed

---

### 2. recursive_loop.json
**Agent delegation cycle (A → B → A → B...)**

Demonstrates a pathological case where two agents repeatedly delegate to each other:
- Agent A delegates to Agent B for "validation"
- Agent B delegates back to Agent A for "reprocessing"
- Loop continues 5 times before session terminates
- Should trigger `RECURSIVE_LOOP` anomaly detection

**Use for:**
- Testing anomaly detection (recursive loops)
- Demonstrating cycle detection in execution graphs
- Illustrating agent delegation anti-patterns
- Debugging infinite delegation scenarios

**Stats:**
- Duration: ~5 seconds
- Agents: 2 (agent_a, agent_b)
- Delegation cycles: 5 complete loops
- Termination: max_recursion_depth_exceeded
- Anomalies: 1 (RECURSIVE_LOOP expected)

**Anomaly Pattern:**
```
agent_a → agent_b (needs_validation)
       ↓ ↑
agent_b → agent_a (needs_reprocessing)
```

---

### 3. token_explosion.json
**Exponential context growth through parallel delegation**

Shows cost amplification as context compounds across sub-agents:
- Coordinator spawns 5 research agents in sequence
- Each inherits cumulative context from prior agents
- Token usage: 800 → 1,500 → 3,200 → 6,500 → 12,000 → 24,000 → 48,000
- Final coordinator call uses 48K input tokens
- Should trigger `TOKEN_EXPLOSION` anomaly detection

**Use for:**
- Testing cost explosion detection
- Demonstrating context compounding issues
- Analyzing fan-out delegation patterns
- Identifying token growth rates

**Stats:**
- Duration: ~8 seconds
- Agents: 6 (1 coordinator, 5 researchers)
- Total tokens: 132,770 (input: 105,000, output: 11,770, cache: 12,000)
- Model calls: 6
- Token growth factor: 60x from first to last call
- Anomalies: 1 (TOKEN_EXPLOSION expected)

**Token Progression:**
```
Coordinator:   800 input tokens
Researcher 1:  1,500 → cumulative context grows
Researcher 2:  3,200 → 2.1x growth
Researcher 3:  6,500 → 2.0x growth  
Researcher 4:  12,000 → 1.8x growth
Researcher 5:  24,000 → 2.0x growth
Final call:    48,000 → 2.0x growth
```

---

### 4. context_loss.json
**Context compaction with critical instruction removal**

Multi-turn conversation that hits context limits:
- Support agent handles customer interaction over 5 turns
- Token usage grows: 2,500 → 4,800 → 8,200 → 15,000 → 28,000
- Context compaction triggered at turn 5 (28K → 8.5K tokens)
- Critical instructions removed: refund approval limits, identity verification
- Turn 6: agent approves $1,200 refund (violates $500 limit)
- Policy violation detected post-action
- Should trigger `PROBABLE_COMPACTION` anomaly detection

**Use for:**
- Testing context compaction detection
- Demonstrating instruction loss scenarios
- Illustrating policy violation correlation with context loss
- Debugging compliance failures in long sessions

**Stats:**
- Duration: ~30 seconds
- Agents: 1 (support_agent)
- Turns: 6 model calls
- Context versions: 2 (ctx_v1, ctx_v2)
- Compaction ratio: 70% reduction (28K → 8.5K)
- Policy violations: 1 (refund_approval_limit)
- Anomalies: 1 (PROBABLE_COMPACTION expected)

**Critical Loss:**
```
Instructions removed during compaction:
1. "Never approve refunds over $500 without manager approval"
2. "Always verify customer identity before discussing account details"

Result: Agent approved $1,200 refund → policy violation
```

**Turn Timeline:**
- Turns 1-5: Normal operation with ctx_v1
- Turn 5: 28K input tokens (approaching limit)
- Compaction event: ctx_v1 → ctx_v2 (instructions lost)
- Turn 6: Only 8.5K tokens, but behavioral guardrails removed
- Tool call: approve_refund($1,200) — would have been blocked pre-compaction

---

## Data Format

All files follow the same structure:

```json
{
  "session_id": "sess_<scenario>_001",
  "spans": [
    {
      "span_name": "session.start | agent.start | model.call | tool.call | etc.",
      "start_time": "2026-07-16T14:30:00.000Z",
      "attributes": {
        "span_id": "span_NNN",
        "parent_span_id": "span_NNN",
        "agent_id": "agent_name",
        ... // scenario-specific attributes
      }
    }
  ]
}
```

### Common Span Types

| Span Name | Purpose | Key Attributes |
|-----------|---------|----------------|
| `session.start` | Session initialization | tenant_id, application_id, objective |
| `session.end` | Session completion | status (completed, terminated, etc.) |
| `agent.start` | Agent begins execution | agent_id, agent_type |
| `agent.end` | Agent completes | agent_id, status |
| `agent.delegate` | Agent spawns sub-agent | agent_id, delegated_to, reason |
| `model.call` | LLM invocation | model, input_tokens, output_tokens, turn |
| `tool.call` | Tool invocation start | tool_name, agent_id, input params |
| `tool.result` | Tool invocation result | status (success/failure), results |
| `context.compaction` | Context window reduction | before_tokens, after_tokens, compaction_ratio, instructions_removed |
| `policy.violation` | Governance violation | policy, violation, severity |

### Attribute Conventions

- **span_id**: Unique identifier for this span (format: `span_NNN`)
- **parent_span_id**: Links spans into hierarchy
- **agent_id**: Which agent generated this span
- **session_id**: Top-level session identifier
- **tenant_id**: Multi-tenant isolation key
- **application_id**: Which application/workflow generated the session
- **context_version_id**: Tracks context evolution (ctx_v1, ctx_v2, etc.)

## Usage in Examples

Load a trace file:

```python
from agent_session_graph import SessionReconstructor
import json

# Method 1: High-level API with file path
reconstructor = SessionReconstructor()
session = reconstructor.from_otlp_json("examples/data/healthy_session.json")

# Method 2: High-level API with in-memory spans
with open("examples/data/healthy_session.json") as f:
    trace = json.load(f)
session = reconstructor.from_otlp_spans(trace["spans"], session_id=trace["session_id"])

# Method 3: Low-level API (full control)
from agent_session_graph import SessionBuilder, GraphBuilder, normalize_span, InMemoryStorage

storage = InMemoryStorage()
builder = SessionBuilder(storage=storage)

events = []
for idx, span in enumerate(trace["spans"], start=1):
    event = normalize_span(span, session_id=trace["session_id"], seq=idx)
    events.append(event)
    builder.process_event(event)

graph_builder = GraphBuilder(storage=storage)
edges = graph_builder.infer_edges(events)
```

## Testing with These Traces

Run the examples:

```bash
# High-level API (automatically loads data/healthy_session.json)
python examples/00_high_level_api.py

# Low-level API (shows all primitives)
python examples/01_basic_usage.py

# Test all scenarios
python examples/00_high_level_api.py
# Then manually test each .json file
```

## Creating Your Own Traces

To create custom trace files for testing:

1. **Copy a template:** Start with `healthy_session.json` as a base
2. **Modify spans:** Add/remove/modify spans to match your scenario
3. **Maintain consistency:**
   - Keep `span_id` values unique
   - Ensure `parent_span_id` references exist
   - Use realistic timestamps (sequential, with appropriate gaps)
   - Include required attributes per span type
4. **Test ingestion:**
   ```python
   session = reconstructor.from_otlp_json("your_trace.json")
   print(f"Events: {len(session.timeline)}")
   print(f"Edges: {len(session.execution_graph)}")
   ```

## Expected Anomalies Summary

| File | Anomaly Type | Detector | Trigger Condition |
|------|-------------|----------|-------------------|
| `healthy_session.json` | None | — | Clean execution |
| `recursive_loop.json` | RECURSIVE_LOOP | `check_recursive_loop` | Agent A ↔ Agent B cycle (5+ iterations) |
| `token_explosion.json` | TOKEN_EXPLOSION | `check_token_explosion` | 60x token growth (800 → 48,000) |
| `context_loss.json` | PROBABLE_COMPACTION | `check_probable_compaction` | 70% token drop (28K → 8.5K) + policy violation |

## Attribution

These trace files are synthetic examples created for demonstration purposes. They represent realistic patterns observed in production multi-agent systems but do not contain actual customer data.

Token counts, model names, and timing patterns are based on typical AWS Bedrock / Claude API usage as of July 2026.

## Questions?

See the main [README](../../README.md) for full documentation or explore the [examples](../README.md) for usage patterns.
