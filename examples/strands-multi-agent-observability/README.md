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

Configure AWS credentials (`aws configure` or env vars) and update the model ID in the notebook if needed.

## Files

+---------------------------------------+-----------------------------------------------+
| File                                  | Purpose                                       |
+---------------------------------------+-----------------------------------------------+
| `agent-as-tools-lexilens.ipynb`       | Full demo with outputs (view without running) |
| `agent-as-tools-lexilens-clean.ipynb` | Clean version to run yourself                 |
| `session_graph.png`                   | Visualization output                          |
| `requirements.txt`                    | Python dependencies                           |
+---------------------------------------+-----------------------------------------------+

## Links

- **Library:** [github.com/cuvsort/agent-session-graph](https://github.com/cuvsort/agent-session-graph)
- **Product:** [curvsort.com/lexilensai](https://www.curvsort.com/lexilensai)

---

*Built by [CurvSort](https://www.curvsort.com) — Session-native runtime intelligence for enterprise AI agents.*
