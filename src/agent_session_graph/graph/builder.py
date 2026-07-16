"""
GraphBuilder — infers ExecutionEdge relationships from SessionEvents.

Builds the causal graph that answers "why did X happen?" by applying
inference rules to detect patterns in event sequences.
"""
import hashlib

from agent_session_graph.schemas import SessionEvent, EventType, ExecutionEdge
from agent_session_graph.storage import StorageBackend, NullStorage


class GraphBuilder:
    """
    Infers and manages ExecutionEdge relationships between SessionEvents.

    Creates a causal graph where edges answer "why" questions:
    - Why did this event happen? (caused_by)
    - How did agents delegate? (delegated_to)
    - What did this tool call produce? (invoked)
    - What memory was read? (read_from)

    Inference rules:
    1. Parent relationship: event.parent_event_id → caused_by edge
    2. Agent delegation: AGENT_DELEGATE followed by AGENT_START → delegated_to
    3. Tool invocation: TOOL_CALL followed by TOOL_RESULT → invoked
    4. Memory read: MEMORY_WRITE key matches MEMORY_READ key → read_from

    Usage:
        from agent_session_graph.graph import GraphBuilder
        from agent_session_graph.storage import InMemoryStorage

        storage = InMemoryStorage()
        builder = GraphBuilder(storage=storage)

        # Infer edges from events
        edges = builder.infer_edges(events)

        # Edges are automatically persisted via storage backend
    """

    def __init__(self, storage: StorageBackend | None = None):
        """
        Initialize GraphBuilder with optional storage backend.

        Args:
            storage: StorageBackend implementation for persistence.
                     If None, uses NullStorage (no persistence).
        """
        self._storage = storage or NullStorage()

    def infer_edges(self, events: list[SessionEvent]) -> list[ExecutionEdge]:
        """
        Infer ExecutionEdge relationships from chronologically ordered events.

        Rules:
        1. Parent relationship: If event.parent_event_id is set,
           create edge (parent -> event, type="caused_by")

        2. Agent delegation: If AGENT_DELEGATE immediately followed by
           AGENT_START, create edge (delegate -> start, type="delegated_to")

        3. Tool invocation: If TOOL_CALL immediately followed by
           TOOL_RESULT or TOOL_ERROR with same participant_id,
           create edge (call -> result, type="invoked")

        4. Memory read: If MEMORY_WRITE's payload.memory_key matches
           later MEMORY_READ's payload.memory_key,
           create edge (write -> read, type="read_from")

        Args:
            events: Chronologically ordered list of SessionEvents (one session)

        Returns:
            List of inferred ExecutionEdge objects
        """
        if not events:
            return []

        edges = []
        session_id = events[0].session_id

        # Rule 1: Parent relationships (caused_by)
        for event in events:
            if event.parent_event_id:
                edge = self._create_edge(
                    session_id=session_id,
                    source_event_id=event.parent_event_id,
                    target_event_id=event.event_id,
                    edge_type="caused_by"
                )
                edges.append(edge)
                self._storage.write_edge(edge)

        # Rule 2: Agent delegation (delegated_to)
        # Look for AGENT_DELEGATE immediately followed by AGENT_START
        for i in range(len(events) - 1):
            current = events[i]
            next_event = events[i + 1]

            if (current.event_type == EventType.AGENT_DELEGATE and
                next_event.event_type == EventType.AGENT_START):
                edge = self._create_edge(
                    session_id=session_id,
                    source_event_id=current.event_id,
                    target_event_id=next_event.event_id,
                    edge_type="delegated_to"
                )
                edges.append(edge)
                self._storage.write_edge(edge)

        # Rule 3: Tool invocation (invoked)
        # Look for TOOL_CALL followed by TOOL_RESULT/TOOL_ERROR with same participant
        for i in range(len(events) - 1):
            current = events[i]
            next_event = events[i + 1]

            if (current.event_type == EventType.TOOL_CALL and
                next_event.event_type in [EventType.TOOL_RESULT, EventType.TOOL_ERROR] and
                current.participant_id == next_event.participant_id):
                edge = self._create_edge(
                    session_id=session_id,
                    source_event_id=current.event_id,
                    target_event_id=next_event.event_id,
                    edge_type="invoked"
                )
                edges.append(edge)
                self._storage.write_edge(edge)

        # Rule 4: Memory read (read_from)
        # Build index of memory writes by key
        memory_writes = {}
        for event in events:
            if event.event_type == EventType.MEMORY_WRITE:
                memory_key = event.payload.get("memory_key")
                if memory_key:
                    memory_writes[memory_key] = event.event_id

        # Find memory reads that match previous writes
        for event in events:
            if event.event_type == EventType.MEMORY_READ:
                memory_key = event.payload.get("memory_key")
                if memory_key and memory_key in memory_writes:
                    edge = self._create_edge(
                        session_id=session_id,
                        source_event_id=memory_writes[memory_key],
                        target_event_id=event.event_id,
                        edge_type="read_from"
                    )
                    edges.append(edge)
                    self._storage.write_edge(edge)

        return edges

    def _create_edge(
        self,
        session_id: str,
        source_event_id: str,
        target_event_id: str,
        edge_type: str
    ) -> ExecutionEdge:
        """
        Create an ExecutionEdge with a deterministic edge_id.

        The edge_id is a hash of (session_id, source, target, type)
        to ensure idempotency.

        Args:
            session_id: Session identifier
            source_event_id: Source event ID
            target_event_id: Target event ID
            edge_type: Edge type

        Returns:
            ExecutionEdge object
        """
        # Generate deterministic edge_id from components
        edge_key = f"{session_id}:{source_event_id}:{target_event_id}:{edge_type}"
        edge_hash = hashlib.sha256(edge_key.encode()).hexdigest()[:16]
        edge_id = f"edge_{session_id}_{edge_hash}"

        return ExecutionEdge(
            edge_id=edge_id,
            session_id=session_id,
            source_event_id=source_event_id,
            target_event_id=target_event_id,
            edge_type=edge_type
        )
