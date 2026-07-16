"""
Storage protocol and built-in implementations for agent-session-graph.

The StorageBackend protocol allows pluggable persistence:
- NullStorage: Discard everything (logic-only mode)
- InMemoryStorage: Dict-backed storage for testing and exploration
- Custom implementations: SQLite, PostgreSQL, cloud storage, etc.
"""
from typing import Protocol, runtime_checkable
from collections import defaultdict


@runtime_checkable
class StorageBackend(Protocol):
    """
    Protocol for pluggable storage backends.

    Implement this interface to persist session data to your storage system
    (database, file system, cloud storage, etc.).
    """

    def write_event(self, event: "SessionEvent") -> None:
        """
        Persist a single session event.

        Args:
            event: SessionEvent to persist
        """
        ...

    def write_metadata(self, metadata: "SessionMetadata") -> None:
        """
        Persist session metadata (usually called once at session end).

        Args:
            metadata: SessionMetadata to persist
        """
        ...

    def write_edge(self, edge: "ExecutionEdge") -> None:
        """
        Persist an execution graph edge.

        Args:
            edge: ExecutionEdge to persist
        """
        ...

    def write_finding(self, finding: "Finding") -> None:
        """
        Persist an anomaly detection finding.

        Args:
            finding: Finding to persist
        """
        ...

    def get_events_by_session(self, session_id: str) -> list["SessionEvent"]:
        """
        Retrieve all events for a session, ordered by sequence number.

        Args:
            session_id: Session identifier

        Returns:
            List of SessionEvents ordered by seq
        """
        ...

    def get_metadata_by_session(self, session_id: str) -> "SessionMetadata | None":
        """
        Retrieve session metadata.

        Args:
            session_id: Session identifier

        Returns:
            SessionMetadata if found, None otherwise
        """
        ...

    def get_edges_by_session(self, session_id: str) -> list["ExecutionEdge"]:
        """
        Retrieve all execution edges for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of ExecutionEdges
        """
        ...

    def get_findings_by_session(self, session_id: str) -> list["Finding"]:
        """
        Retrieve all findings for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of Findings
        """
        ...


class NullStorage:
    """
    No-op storage backend that discards all writes.

    Use this when you only need the session reconstruction logic
    without persistence (e.g., streaming analysis, one-time processing).
    """

    def write_event(self, event: "SessionEvent") -> None:
        pass

    def write_metadata(self, metadata: "SessionMetadata") -> None:
        pass

    def write_edge(self, edge: "ExecutionEdge") -> None:
        pass

    def write_finding(self, finding: "Finding") -> None:
        pass

    def get_events_by_session(self, session_id: str) -> list["SessionEvent"]:
        return []

    def get_metadata_by_session(self, session_id: str) -> "SessionMetadata | None":
        return None

    def get_edges_by_session(self, session_id: str) -> list["ExecutionEdge"]:
        return []

    def get_findings_by_session(self, session_id: str) -> list["Finding"]:
        return []


class InMemoryStorage:
    """
    In-memory storage backend backed by Python dicts.

    Useful for:
    - Testing and development
    - Exploring small sessions without database setup
    - Building custom pipelines that process data in-memory

    Not suitable for:
    - Large sessions (no memory limits)
    - Production persistence (data lost on process exit)
    - Concurrent access (not thread-safe)
    """

    def __init__(self):
        # Store events grouped by session_id
        self.events: dict[str, list["SessionEvent"]] = defaultdict(list)
        # Store metadata keyed by session_id
        self.metadata: dict[str, "SessionMetadata"] = {}
        # Store edges grouped by session_id
        self.edges: dict[str, list["ExecutionEdge"]] = defaultdict(list)
        # Store findings grouped by session_id
        self.findings: dict[str, list["Finding"]] = defaultdict(list)

    def write_event(self, event: "SessionEvent") -> None:
        """Append event to session's event list."""
        self.events[event.session_id].append(event)
        # Keep events sorted by sequence number
        self.events[event.session_id].sort(key=lambda e: e.seq)

    def write_metadata(self, metadata: "SessionMetadata") -> None:
        """Store or update session metadata."""
        self.metadata[metadata.session_id] = metadata

    def write_edge(self, edge: "ExecutionEdge") -> None:
        """Append edge to session's edge list."""
        self.edges[edge.session_id].append(edge)

    def write_finding(self, finding: "Finding") -> None:
        """Append finding to session's finding list."""
        self.findings[finding.session_id].append(finding)

    def get_events_by_session(self, session_id: str) -> list["SessionEvent"]:
        """Return all events for session, already sorted by seq."""
        return self.events.get(session_id, [])

    def get_metadata_by_session(self, session_id: str) -> "SessionMetadata | None":
        """Return session metadata if it exists."""
        return self.metadata.get(session_id)

    def get_edges_by_session(self, session_id: str) -> list["ExecutionEdge"]:
        """Return all edges for session."""
        return self.edges.get(session_id, [])

    def get_findings_by_session(self, session_id: str) -> list["Finding"]:
        """Return all findings for session."""
        return self.findings.get(session_id, [])

    def clear(self) -> None:
        """Clear all stored data (useful for testing)."""
        self.events.clear()
        self.metadata.clear()
        self.edges.clear()
        self.findings.clear()


# Type stubs for forward references (actual imports happen in __init__.py)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agent_session_graph.schemas import (
        SessionEvent,
        SessionMetadata,
        ExecutionEdge,
        Finding
    )
