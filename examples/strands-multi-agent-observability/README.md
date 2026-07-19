# Why Your Multi-Agent System Looks Green But Behaves Broken

## The Problem

You deploy a multi-agent orchestrator. Every span completes. Every tool call returns "success." Latency looks normal. But users report garbage outputs.

Traditional observability (OpenTelemetry, Datadog, Langfuse) tells you **what happened** — spans, latencies, error codes. It doesn't tell you:

- Why did the orchestrator route to the wrong specialist?
- Why did an agent silently re-query itself 5 times with the same input?
- Where in the delegation chain did information get lost?
- Which session burned 10x the expected tokens without any errors?

These are **session-level failures** — invisible to span-level tracing because every individual span "succeeded."

## What LexiLensAI Does Differently

LexiLensAI treats the **session** as the primary unit of observability, not the span. It reconstructs the full execution graph of a multi-agent session and detects anomalies that only become visible when you look at the whole picture:

- **Delegation graph reconstruction** — who called whom, what information flowed at each hop
- **Retry storm detection** — same agent called repeatedly with similar input (each call "succeeds" but the session is burning tokens)
- **Token explosion alerting** — a single agent response consuming disproportionate tokens
- **Context drift detection** — accumulated context from prior delegations steering future routing decisions incorrectly
- **Cost attribution per session** — not just per-span, but total cost of the session with breakdown by agent

## This Demo

This notebook instruments an [AWS Strands Agents](https://github.com/strands-agents/samples) multi-agent system (orchestrator + specialist agents) and demonstrates:

1. **Part 1:** The manual approach — ~65 lines of `emit_span()` boilerplate per tool, producing flat traces with no session awareness
2. **Part 2:** LexiLensAI auto-instrumentation — one `LexiLens.init()` call, zero code changes to agents, full session graph + anomaly detection

### Session Graph Output

![Session Graph](session_graph.png)

Orchestrator delegates to specialist agents. Token costs visible at each node. Anomalous agents highlighted in red.

### Anomaly Detection in Action

All 5 calls below returned "success." Traditional tracing sees nothing wrong:

```
ANOMALIES DETECTED: 3
  [HIGH] retry_storm: Agent called 3x in <60s with similar input
  [HIGH] retry_storm: Agent called 4x in <60s with similar input
  [HIGH] retry_storm: Agent called 5x in <60s with similar input
```

## Architecture: How This Fits Together

This demo is part of the **LexiLensAI observability stack** for multi-agent AI systems. Here's how the pieces fit:

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Your Multi-Agent Application (Strands, LangChain, etc.)    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   LexiLens SDK               │  ← This notebook demonstrates
        │   Auto-instrumentation       │
        │   • Patches Agent.__call__   │
        │   • Captures spans           │
        │   • Tracks session context   │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   Trace Output (JSONL/OTel)  │
        │   • trace_id, span_id        │
        │   • parent relationships     │
        │   • session_id, timestamps   │
        │   • token counts, metadata   │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │  agent-session-graph library │  ← Open-source library
        │  Post-processing & Analysis  │     (repo root)
        │  • Reconstructs sessions     │
        │  • Builds delegation graphs  │
        │  • Detects anomalies         │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   Observability Outputs      │
        │   • Session graphs           │
        │   • Execution timelines      │
        │   • Anomaly alerts           │
        │   • Cost attribution         │
        └──────────────────────────────┘
```

### What This Notebook Shows

**Part 1:** The baseline — manual `emit_span()` calls everywhere. Shows the pain of instrumenting agents by hand.

**Part 2:** The LexiLens SDK approach — one `LexiLens.init()` call that auto-patches the agent framework. Generates session-aware traces with:
- Automatic parent-child span relationships via call stack tracking
- Session-level context (not just span-level)
- Token accounting per agent
- Built-in anomaly detection (retry storms, token explosion)

### What the Library Does

The [`agent-session-graph` library](https://github.com/curvsort/agent-session-graph) (repo root) is a **post-processing tool**. It takes traces that already exist (from LexiLens SDK, Langfuse, Datadog, your own OTel collector) and reconstructs them into:
- Full session execution graphs
- Delegation chain visualizations
- Timeline replays showing which agent called which, when, and with what context

### The Missing Piece: Production LexiLensAI

The **production LexiLensAI platform** (not open-source) combines both:
- Real-time ingestion of session traces
- Advanced anomaly detection (context drift, governance violations, instruction decay)
- Multi-session analysis and trending
- Integration with alerting/incident management

**This notebook** is a proof-of-concept for the instrumentation layer.  
**The library** is a building block for the analysis layer.  
**LexiLensAI** is the full production platform.

### Data Flow Example

```python
# 1. Your agent code (unchanged)
@tool
def research_assistant(query: str) -> str:
    agent = Agent(model="...", system_prompt="...")
    return str(agent(query))

# 2. SDK captures automatically (via monkey-patch)
#    → generates span with session_id, parent_span_id, tokens, timing

# 3. Trace written to JSONL or OTel collector
#    {
#      "trace_id": "abc123",
#      "span_id": "def456",
#      "session_id": "session_001",
#      "agent_name": "research_agent",
#      "parent_span_id": "orchestrator_span",
#      "token_input": 234,
#      "token_output": 567
#    }

# 4. Library reconstructs the session
from agent_session_graph import SessionReconstructor
reconstructor = SessionReconstructor()
session = reconstructor.from_jsonl("traces.jsonl")
session.visualize()  # → session graph with delegation chains
```

### Why Two Layers?

**Instrumentation (SDK):** Must be lightweight, framework-specific, zero-config. Different for Strands vs LangChain vs custom agents.

**Analysis (library):** Framework-agnostic. Works on any OTel-compatible traces. Can be extended, customized, integrated into your existing observability stack.

Separating them means:
- You can swap instrumentation methods without changing analysis
- The library works with traces from any source (not just our SDK)
- Each layer can evolve independently


### Integration

```python
# One line. No changes to your agent code.
lexilens = LexiLens.init(service_name="my-app")

# Your agents work exactly as before — LexiLens observes automatically
@tool
def research_assistant(query: str) -> str:
    agent = Agent(model="...", system_prompt="...")
    return str(agent(query))
```

## Running the Notebook

**Requirements:**
- AWS Bedrock access with Claude Sonnet enabled
- Python 3.11+
- `pip install strands-agents boto3 matplotlib`

**Setup:**
```bash
git clone https://github.com/cuvsort/agent-session-graph.git
cd agent-session-graph/examples/strands-multi-agent-observability
jupyter notebook agent-as-tools-lexilens.ipynb
```

**AWS Configuration:**
- Configure credentials: `aws configure` or set `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars
- The notebook uses model ID `global.anthropic.claude-sonnet-4-5-20250929-v1:0`
- If your Bedrock setup uses a different region prefix (e.g. `us.anthropic...` or `eu.anthropic...`), update the `model=` parameter in the notebook cells

## Files

| File | Purpose |
|------|---------|
| `agent-as-tools-lexilens.ipynb` | Full demo with outputs (view without running) |
| `agent-as-tools-lexilens-clean.ipynb` | Clean version to run yourself |
| `session_graph.png` | Visualization output |
| `requirements.txt` | Python dependencies |

## Links

- **Library:** [github.com/cuvsort/agent-session-graph](https://github.com/cuvsort/agent-session-graph)
- **Product:** [curvsort.com/lexilensai](https://www.curvsort.com/lexilensai)

---

*Built by [CurvSort](https://www.curvsort.com) — Session-native runtime intelligence for enterprise AI agents.*
