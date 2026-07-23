"""
agent-session-graph

Session reconstruction and causal graph engine for multi-agent AI systems.

Core primitives for building session-aware observability:
- Ingest OTel spans → structured SessionEvents
- Build causal ExecutionGraphs (why did X happen?)
- Replay sessions to any point in time
- Reference implementations for anomaly detection

Quick start:
    from agent_session_graph import SessionReconstructor

    # High-level API (recommended)
    reconstructor = SessionReconstructor()
    session = reconstructor.from_otlp_json("traces.json")

    # Explore the session
    print(session.execution_graph)       # Causal graph
    print(session.timeline)              # Ordered events
    print(session.lineage("event_42"))   # Why did this happen?
    print(session.cost_attribution)      # Cost by agent

    # Or use low-level primitives for advanced usage
    from agent_session_graph import SessionBuilder, GraphBuilder
    from agent_session_graph.storage import InMemoryStorage

    storage = InMemoryStorage()
    builder = SessionBuilder(storage=storage)
    graph = GraphBuilder(storage=storage)

See examples/ directory for complete usage patterns.
"""

__version__ = "0.1.0"

from agent_session_graph.detection import AnomalyDetector, ContextDiffEngine
from agent_session_graph.graph import GraphBuilder
from agent_session_graph.ingestion import normalize_span, normalize_trace
from agent_session_graph.replay import SessionState, replay_session_to
from agent_session_graph.schemas import (
    ContextVersion,
    EventType,
    ExecutionEdge,
    Finding,
    MemoryVersion,
    SessionEvent,
    SessionMetadata,
)
from agent_session_graph.session import SessionBuilder
from agent_session_graph.session_reconstructor import Session, SessionReconstructor
from agent_session_graph.storage import InMemoryStorage, NullStorage, StorageBackend

__all__ = [
    # Version
    "__version__",
    # High-level API
    "SessionReconstructor",
    "Session",
    # Core primitives
    "SessionBuilder",
    "GraphBuilder",
    "normalize_span",
    "normalize_trace",
    # Storage
    "StorageBackend",
    "NullStorage",
    "InMemoryStorage",
    # Schemas
    "SessionEvent",
    "EventType",
    "SessionMetadata",
    "ExecutionEdge",
    "Finding",
    "ContextVersion",
    "MemoryVersion",
    # Reference implementations
    "AnomalyDetector",
    "ContextDiffEngine",
    # Replay
    "replay_session_to",
    "SessionState",
]
