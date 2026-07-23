"""
Replay Engine for reconstructing session state at any point in time.

This module provides time-travel debugging capabilities: given a session_id and
a target sequence number, it replays events from the beginning to reconstruct
the exact state at that point. This enables "what did the agent know at seq=N?"
queries and historical state inspection.

The replay engine is designed to be:
- Pure (no side effects during replay)
- Incremental (apply events one at a time)
- Extensible (easy to add new event type handlers)

For production use with high event volumes, consider implementing checkpoint
optimization to avoid replaying from session start every time.

Example usage:
    from agent_session_graph.replay import replay_session_to
    from agent_session_graph.storage import PostgresStorage

    storage = PostgresStorage(connection_string)

    # Reconstruct state at seq=42
    state = replay_session_to(session_id="sess_123", target_seq=42, storage=storage)

    print(f"Participants: {state.current_participants}")
    print(f"Cost: ${state.current_cost_usd:.2f}")
    print(f"Tokens: {state.current_token_usage}")
"""
from dataclasses import dataclass, field
from typing import Any

from agent_session_graph.schemas.session_event import EventType, SessionEvent


@dataclass
class SessionState:
    """
    Point-in-time state of a session, reconstructed by replaying events.

    This is a lightweight structure tracking just the key runtime metrics
    and participants. Full context/memory reconstruction would require
    additional fields and blob storage fetching.

    Attributes:
        session_id: Session identifier
        events_applied: List of event_ids in order
        current_participants: Set of active agent/participant IDs
        current_cost_usd: Cumulative cost in USD
        current_token_usage: Token counts by type (input, output, cache_read, cache_write)
        last_event_type: Most recent event type processed
        last_seq: Most recent sequence number processed
    """
    session_id: str
    events_applied: list[str] = field(default_factory=list)  # event_ids in order
    current_participants: set[str] = field(default_factory=set)  # active agent/participant IDs
    current_cost_usd: float = 0.0
    current_token_usage: dict[str, int] = field(default_factory=lambda: {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0
    })
    last_event_type: str | None = None
    last_seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to JSON-serializable dict for API responses.

        Returns:
            Dictionary representation with stats summary
        """
        return {
            "session_id": self.session_id,
            "events_applied": self.events_applied,
            "current_participants": list(self.current_participants),  # set -> list for JSON
            "current_cost_usd": self.current_cost_usd,
            "current_token_usage": self.current_token_usage,
            "last_event_type": self.last_event_type,
            "last_seq": self.last_seq,
            "stats": {
                "total_events": len(self.events_applied),
                "active_participants": len(self.current_participants),
                "total_tokens": sum(self.current_token_usage.values())
            }
        }


def apply_event(state: SessionState, event: SessionEvent) -> SessionState:
    """
    Pure function: apply a single event to the session state.

    Updates state based on event_type semantics (e.g. AGENT_START adds to
    current_participants, COST_UPDATE adds to current_cost_usd, etc.).

    This is a REFERENCE IMPLEMENTATION. Users should extend this function
    to handle additional event types or compute additional derived state
    relevant to their agent architecture.

    Args:
        state: Current session state
        event: Event to apply

    Returns:
        Updated session state (new instance, not mutated)
    """
    # Create a new state instance (pure function, no mutation)
    new_state = SessionState(
        session_id=state.session_id,
        events_applied=state.events_applied.copy(),
        current_participants=state.current_participants.copy(),
        current_cost_usd=state.current_cost_usd,
        current_token_usage=state.current_token_usage.copy(),
        last_event_type=(
            event.event_type.value
            if isinstance(event.event_type, EventType)
            else event.event_type
        ),
        last_seq=event.seq
    )

    # Record that we applied this event
    new_state.events_applied.append(event.event_id)

    # Apply state changes based on event type
    if event.event_type in (EventType.AGENT_START, "AGENT_START"):
        # Add participant to active set
        if event.participant_id:
            new_state.current_participants.add(event.participant_id)

    elif event.event_type in (EventType.AGENT_END, "AGENT_END"):
        # Keep participant in set (they were active during this session)
        # In a more sophisticated version, we might track "currently running" vs "ever participated"
        if event.participant_id:
            new_state.current_participants.add(event.participant_id)

    elif event.event_type in (EventType.COST_UPDATE, "COST_UPDATE"):
        # Add to cumulative cost
        cost_delta = event.payload.get("cost_usd", 0.0)
        new_state.current_cost_usd += cost_delta

    elif event.event_type in (EventType.MODEL_RESPONSE, "MODEL_RESPONSE"):
        # Update token usage from model response
        usage = event.payload.get("usage", {})
        if usage:
            new_state.current_token_usage["input"] += usage.get("input_tokens", 0)
            new_state.current_token_usage["output"] += usage.get("output_tokens", 0)
            new_state.current_token_usage["cache_read"] += usage.get("cache_read_tokens", 0)
            new_state.current_token_usage["cache_write"] += usage.get("cache_write_tokens", 0)

    elif event.event_type in (EventType.TOOL_CALL, "TOOL_CALL"):
        # Track tool usage (could add tool_calls_count, etc.)
        pass

    elif event.event_type in (
        EventType.MEMORY_WRITE, "MEMORY_WRITE",
        EventType.MEMORY_UPDATE, "MEMORY_UPDATE",
    ):
        # Track memory operations (could add memory_keys_written set, etc.)
        pass

    # Add more event type handlers as needed for richer state reconstruction

    return new_state


def replay_session_to(session_id: str, target_seq: int, storage) -> SessionState:
    """
    Replay a session from the beginning up to a target sequence number.

    Fetches all events with seq <= target_seq from storage, applies them
    in order, and returns the reconstructed state at that point in time.

    Args:
        session_id: Session identifier
        target_seq: Replay up to and including this sequence number
        storage: Storage backend with get_events_by_session(session_id) method

    Returns:
        SessionState at the target sequence number

    Raises:
        ValueError: If session has no events or target_seq is invalid
    """
    # Fetch all events for the session (ordered by seq)
    all_events_dict = storage.get_events_by_session(session_id)

    if not all_events_dict:
        raise ValueError(f"Session {session_id} has no events")

    # Filter to events up to target_seq
    events_to_replay = [e for e in all_events_dict if e["seq"] <= target_seq]

    if not events_to_replay:
        raise ValueError(f"No events found with seq <= {target_seq} for session {session_id}")

    # Initialize empty state
    state = SessionState(session_id=session_id)

    # Apply events in sequence
    for event_dict in events_to_replay:
        # Convert dict to SessionEvent for type safety
        event = SessionEvent(
            event_id=event_dict["event_id"],
            session_id=event_dict["session_id"],
            seq=event_dict["seq"],
            timestamp=event_dict["timestamp"],
            event_type=event_dict["event_type"],
            parent_event_id=event_dict.get("parent_event_id"),
            participant_id=event_dict.get("participant_id"),
            profile_snapshot_id=event_dict.get("profile_snapshot_id"),
            context_version_id=event_dict.get("context_version_id"),
            payload=event_dict.get("payload", {})
        )

        state = apply_event(state, event)

    return state
