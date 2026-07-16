"""
Scenario 1: Healthy Multi-Agent Workflow

A normal orchestrator session that delegates to a research agent,
performs a tool call and model call, then completes successfully.
No anomalies, clean execution.
"""

SESSION_ID = "fixture_healthy_001"

HEALTHY_SESSION_SPANS = [
    {
        "span_name": "SessionStart",
        "start_time": "2026-07-01T14:00:00Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_001",
            "tenant_id": "acme_corp",
            "application_id": "research_assistant",
            "objective": "Research AI advancements in 2026"
        }
    },
    {
        "span_name": "OrchestratorAgent.start",
        "start_time": "2026-07-01T14:00:01Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_002",
            "parent_span_id": f"span_{SESSION_ID}_001",
            "agent_id": "orchestrator",
            "agent_type": "orchestrator",
            "harness": "claude_agent_sdk",
            "harness_version": "0.3.1"
        }
    },
    {
        "span_name": "OrchestratorAgent.delegate",
        "start_time": "2026-07-01T14:00:02Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_003",
            "parent_span_id": f"span_{SESSION_ID}_002",
            "agent_id": "orchestrator",
            "delegated_to": "research_agent",
            "task": "Find latest AI research papers"
        }
    },
    {
        "span_name": "ResearchAgent.start",
        "start_time": "2026-07-01T14:00:03Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_004",
            "parent_span_id": f"span_{SESSION_ID}_003",
            "agent_id": "research_agent",
            "agent_type": "specialist"
        }
    },
    {
        "span_name": "WebSearch",
        "start_time": "2026-07-01T14:00:04Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_005",
            "parent_span_id": f"span_{SESSION_ID}_004",
            "agent_id": "research_agent",
            "tool_name": "web_search",
            "query": "AI breakthroughs 2026",
            "results_count": 15
        }
    },
    {
        "span_name": "Claude.Sonnet.Call",
        "start_time": "2026-07-01T14:00:08Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_006",
            "parent_span_id": f"span_{SESSION_ID}_004",
            "agent_id": "research_agent",
            "model": "claude-sonnet-4-6",
            "input_tokens": 2200,
            "output_tokens": 380,
            "temperature": 0.7
        }
    },
    {
        "span_name": "ResearchAgent.complete",
        "start_time": "2026-07-01T14:00:12Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_007",
            "parent_span_id": f"span_{SESSION_ID}_003",
            "agent_id": "research_agent",
            "status": "success",
            "result_summary": "Found 15 relevant papers on AI advancements"
        }
    },
    {
        "span_name": "OrchestratorAgent.complete",
        "start_time": "2026-07-01T14:00:13Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_008",
            "parent_span_id": f"span_{SESSION_ID}_001",
            "agent_id": "orchestrator",
            "status": "success"
        }
    },
    {
        "span_name": "SessionEnd",
        "start_time": "2026-07-01T14:00:14Z",
        "attributes": {
            "span_id": f"span_{SESSION_ID}_009",
            "parent_span_id": f"span_{SESSION_ID}_001",
            "status": "completed",
            "duration_ms": 14000
        }
    }
]
