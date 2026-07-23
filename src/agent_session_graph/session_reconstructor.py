"""
SessionReconstructor - High-level convenience API for session reconstruction.

Provides an ergonomic interface that wraps the low-level primitives
(SessionBuilder, GraphBuilder, normalize_trace) into a simple workflow.

Usage:
    from agent_session_graph import SessionReconstructor

    reconstructor = SessionReconstructor()

    # From JSON file
    session = reconstructor.from_otlp_json("traces.json")

    # From in-memory spans
    session = reconstructor.from_otlp_spans(spans)

    # Explore the session
    print(session.execution_graph)
    print(session.timeline)
    print(session.lineage("event_42"))
    print(session.cost_attribution)
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

from agent_session_graph.graph import GraphBuilder
from agent_session_graph.ingestion import normalize_trace
from agent_session_graph.schemas import (
    ExecutionEdge,
    SessionEvent,
    SessionMetadata,
)
from agent_session_graph.session import SessionBuilder
from agent_session_graph.storage import InMemoryStorage, StorageBackend


class Session:
    """
    Reconstructed session with high-level query interface.

    Properties:
        id: Session identifier
        metadata: SessionMetadata object
        execution_graph: List of ExecutionEdges (causal graph)
        timeline: Chronologically ordered events

    Methods:
        lineage(event_id): Trace causal chain back from event
        cost_attribution: Cost breakdown by agent
        tool_lifecycle: Tool invocations and outcomes
    """

    def __init__(
        self,
        session_id: str,
        metadata: SessionMetadata,
        events: list[SessionEvent],
        edges: list[ExecutionEdge]
    ):
        self.id = session_id
        self.metadata = metadata
        self._events = events
        self._edges = edges

        # Build indexes for fast lookups
        self._events_by_id = {e.event_id: e for e in events}
        self._edges_by_target = defaultdict(list)
        for edge in edges:
            self._edges_by_target[edge.target_event_id].append(edge)

    @property
    def execution_graph(self) -> list[ExecutionEdge]:
        """Full causal execution graph as list of edges."""
        return self._edges

    @property
    def timeline(self) -> list[SessionEvent]:
        """Chronologically ordered list of events."""
        return sorted(self._events, key=lambda e: e.timestamp)

    def lineage(self, event_id: str) -> list[str]:
        """
        Trace causal lineage back from an event.

        Returns list of event IDs in reverse-chronological order
        (most recent first) showing the causal chain.

        Args:
            event_id: Event to trace lineage for

        Returns:
            List of event IDs in causal chain

        Example:
            >>> session.lineage("event_42")
            ['event_42', 'event_30', 'event_15', 'event_1']
        """
        lineage = [event_id]
        current = event_id

        # Walk up the causal graph following "caused_by" edges
        visited = set()
        while current and current not in visited:
            visited.add(current)

            # Find edges where current is the target (caused by something)
            parent_edges = [
                e for e in self._edges_by_target.get(current, [])
                if e.edge_type == "caused_by"
            ]

            if parent_edges:
                # Take the first parent (most events have single parent)
                parent = parent_edges[0].source_event_id
                lineage.append(parent)
                current = parent
            else:
                break

        return lineage

    @property
    def cost_attribution(self) -> dict[str, float]:
        """
        Cost breakdown by agent/participant.

        Returns:
            Dict mapping participant_id to cumulative cost in USD

        Example:
            >>> session.cost_attribution
            {'coordinator': 0.0045, 'researcher': 0.0120, 'writer': 0.0025}
        """
        costs = defaultdict(float)

        for event in self._events:
            if event.participant_id and event.event_type == "MODEL_CALL":
                # Extract token counts and calculate cost
                input_tokens = event.payload.get("input_tokens", 0)
                output_tokens = event.payload.get("output_tokens", 0)

                # Simplified pricing: $3/MTok input, $15/MTok output
                # Real implementations should use model-specific pricing
                cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
                costs[event.participant_id] += cost

        return dict(costs)

    @property
    def tool_lifecycle(self) -> list[dict[str, Any]]:
        """
        Tool invocations and their outcomes.

        Returns:
            List of dicts with keys: tool_name, status, duration_ms, agent

        Example:
            >>> session.tool_lifecycle
            [
                {'tool_name': 'web_search', 'status': 'success',
                 'duration_ms': 1234, 'agent': 'researcher'},
                {'tool_name': 'code_exec', 'status': 'error',
                 'duration_ms': 567, 'agent': 'coder'}
            ]
        """
        tools = []

        # Build map of tool calls to results
        tool_calls = {}
        for event in self._events:
            if event.event_type == "TOOL_CALL":
                tool_calls[event.event_id] = {
                    "tool_name": event.payload.get("tool_name", "unknown"),
                    "agent": event.participant_id,
                    "start_time": event.timestamp,
                    "call_event_id": event.event_id
                }

        # Find corresponding results via "invoked" edges
        for edge in self._edges:
            if edge.edge_type == "invoked" and edge.source_event_id in tool_calls:
                tool_call = tool_calls[edge.source_event_id]
                result_event = self._events_by_id.get(edge.target_event_id)

                if result_event:
                    status = "success" if result_event.event_type == "TOOL_RESULT" else "error"
                    duration_ms = int(
                        (result_event.timestamp - tool_call["start_time"])
                        .total_seconds() * 1000
                    )

                    tools.append({
                        "tool_name": tool_call["tool_name"],
                        "status": status,
                        "duration_ms": duration_ms,
                        "agent": tool_call["agent"]
                    })

        return tools

    @property
    def total_tokens(self) -> int:
        """Total token count (input + output) across all model calls."""
        return self.metadata.token_usage.input + self.metadata.token_usage.output

    @property
    def agents(self) -> list[str]:
        """List of unique agent/participant IDs in the session."""
        return list(set(
            e.participant_id for e in self._events
            if e.participant_id
        ))

    def __repr__(self) -> str:
        return (
            f"Session(id='{self.id}', "
            f"status='{self.metadata.status}', "
            f"events={len(self._events)}, "
            f"edges={len(self._edges)}, "
            f"cost=${self.metadata.cost_usd:.4f})"
        )


class SessionReconstructor:
    """
    High-level session reconstruction API.

    Wraps SessionBuilder, GraphBuilder, and storage into a simple interface.

    Usage:
        reconstructor = SessionReconstructor()

        # From JSON file
        session = reconstructor.from_otlp_json("traces.json")

        # From in-memory spans
        session = reconstructor.from_otlp_spans(otel_spans)

        # Explore
        print(session.execution_graph)
        print(session.timeline)
        print(session.cost_attribution)
    """

    def __init__(self, storage: StorageBackend | None = None):
        """
        Initialize SessionReconstructor.

        Args:
            storage: Storage backend for persistence. If None, uses InMemoryStorage.
        """
        self._storage = storage or InMemoryStorage()
        self._session_builder = SessionBuilder(storage=self._storage)
        self._graph_builder = GraphBuilder(storage=self._storage)

    def from_otlp_json(self, filepath: str | Path) -> Session:
        """
        Reconstruct session from OTel trace JSON file.

        Expected JSON format:
        {
            "session_id": "sess_001",
            "spans": [
                {
                    "span_name": "agent.start",
                    "start_time": "2026-07-16T10:00:00Z",
                    "attributes": {...}
                },
                ...
            ]
        }

        Args:
            filepath: Path to JSON file containing OTel spans

        Returns:
            Session object with reconstructed session data

        Example:
            >>> reconstructor = SessionReconstructor()
            >>> session = reconstructor.from_otlp_json("traces.json")
            >>> print(session.execution_graph)
        """
        filepath = Path(filepath)

        with open(filepath, 'r') as f:
            data = json.load(f)

        session_id = data.get("session_id")
        if not session_id:
            raise ValueError("JSON must contain 'session_id' field")

        spans = data.get("spans", [])
        if not spans:
            raise ValueError("JSON must contain non-empty 'spans' array")

        return self.from_otlp_spans(spans, session_id=session_id)

    def from_otlp_spans(
        self,
        spans: list[dict[str, Any]],
        session_id: str | None = None
    ) -> Session:
        """
        Reconstruct session from list of OTel span dicts.

        Args:
            spans: List of OTel span dictionaries
            session_id: Session identifier. If None, extracted from first span.

        Returns:
            Session object with reconstructed session data

        Example:
            >>> spans = [
            ...     {"span_name": "agent.start", "start_time": "...", "attributes": {...}},
            ...     {"span_name": "model.call", "start_time": "...", "attributes": {...}},
            ... ]
            >>> session = reconstructor.from_otlp_spans(spans, session_id="sess_001")
        """
        if not spans:
            raise ValueError("spans list cannot be empty")

        # Auto-generate session_id if not provided
        if not session_id:
            session_id = spans[0].get("attributes", {}).get("session_id", "session_default")

        # Normalize spans to SessionEvents
        events = normalize_trace(spans, session_id)

        # Process events through SessionBuilder
        for event in events:
            self._session_builder.process_event(event)

        # Infer causal edges
        edges = self._graph_builder.infer_edges(events)

        # Get final session metadata
        metadata = self._session_builder.get_session_state(session_id)
        if not metadata:
            raise RuntimeError(f"Failed to build session metadata for {session_id}")

        # Return high-level Session object
        return Session(
            session_id=session_id,
            metadata=metadata,
            events=events,
            edges=edges
        )

    def stream(self) -> Iterator[Session]:
        """
        Stream sessions as they arrive in real-time.

        This is a placeholder for future real-time ingestion support.
        Would integrate with OTel collectors, Kinesis streams, etc.

        Raises:
            NotImplementedError: Real-time streaming not yet implemented

        Example (future):
            >>> for session in reconstructor.stream():
            ...     print(f"New session: {session.id}")
            ...     if session.metadata.finding_summary.anomalies > 0:
            ...         print(f"  Anomalies detected!")
        """
        raise NotImplementedError(
            "Real-time streaming not yet implemented. "
            "Use from_otlp_json() or from_otlp_spans() for batch processing."
        )
