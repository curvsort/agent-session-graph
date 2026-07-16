"""
SessionBuilder — runtime state engine for session reconstruction.

Maintains live session state by processing events one at a time.
Detects sequence gaps, accumulates token usage and cost, tracks participants,
and finalizes session metadata on completion.

In production systems, this would be backed by Redis/Valkey for sub-ms reads.
For development/testing, in-memory state works fine.
"""
from datetime import datetime, timezone
from typing import Optional

from agent_session_graph.schemas import (
    SessionEvent,
    EventType,
    SessionMetadata,
    IngestionSource,
    TokenUsage,
    DataIntegrity,
    FindingSummary
)
from agent_session_graph.storage import StorageBackend, NullStorage


class SessionBuilder:
    """
    Runtime state engine for building and tracking sessions.

    Maintains in-memory session state (simulating Redis/ElastiCache in production).
    Detects sequence gaps and updates data integrity status.
    Optionally persists events and metadata via pluggable storage backend.

    Usage:
        from agent_session_graph.session import SessionBuilder
        from agent_session_graph.storage import InMemoryStorage

        storage = InMemoryStorage()
        builder = SessionBuilder(storage=storage)

        for event in events:
            builder.process_event(event)

        # Get final session state
        metadata = builder.get_session_state(session_id)
    """

    def __init__(self, storage: StorageBackend | None = None):
        """
        Initialize SessionBuilder with optional storage backend.

        Args:
            storage: StorageBackend implementation for persistence.
                     If None, uses NullStorage (no persistence).
        """
        # Active session metadata, keyed by session_id
        self._sessions: dict[str, SessionMetadata] = {}

        # Track last seen sequence number per session
        self._last_seq: dict[str, int] = {}

        # Storage backend for persistence
        self._storage = storage or NullStorage()

    def process_event(self, event: SessionEvent) -> None:
        """
        Process a SessionEvent and update session state.

        Workflow:
        1. Create session metadata if new session_id
        2. Detect sequence gaps and update data_integrity
        3. Update last_seq tracker
        4. Update token usage and cost if MODEL_CALL event
        5. If SESSION_END: finalize metadata and persist
        6. Always persist event via storage backend

        Args:
            event: SessionEvent to process
        """
        session_id = event.session_id

        # Step 1: Initialize session if new
        if session_id not in self._sessions:
            self._init_session(event)

        session = self._sessions[session_id]

        # Step 2: Detect sequence gaps
        expected_seq = self._last_seq.get(session_id, 0) + 1
        if event.seq > expected_seq:
            # Gap detected!
            gap_start = expected_seq
            gap_end = event.seq - 1
            self._record_gap(session, gap_start, gap_end)

        # Step 3: Update last_seq tracker
        self._last_seq[session_id] = max(self._last_seq.get(session_id, 0), event.seq)
        session.last_seq = self._last_seq[session_id]

        # Step 4: Update token usage and cost for MODEL_CALL events
        if event.event_type == EventType.MODEL_CALL:
            self._update_token_usage(session, event)

        # Step 5: Handle SESSION_END
        if event.event_type == EventType.SESSION_END:
            session.status = "completed"
            session.end_time = event.timestamp
            # Persist final metadata
            self._storage.write_metadata(session)

        # Step 6: Always persist event
        self._storage.write_event(event)

    def get_session_state(self, session_id: str) -> Optional[SessionMetadata]:
        """
        Retrieve current in-memory session state.

        Args:
            session_id: Session identifier

        Returns:
            SessionMetadata if session exists, None otherwise
        """
        return self._sessions.get(session_id)

    def _init_session(self, event: SessionEvent) -> None:
        """
        Initialize a new session from the first event.

        Args:
            event: First event for this session
        """
        # Extract metadata from event payload
        tenant_id = event.payload.get("tenant_id", "default")
        application_id = event.payload.get("application_id")
        root_agent = event.participant_id

        # Create SessionMetadata
        metadata = SessionMetadata(
            session_id=event.session_id,
            tenant_id=tenant_id,
            application_id=application_id,
            root_agent=root_agent,
            start_time=event.timestamp,
            status="running",
            objective=event.payload.get("objective"),
            source=IngestionSource(
                ingestion_type=event.payload.get("ingestion_type", "otel_trace"),
                harness=event.payload.get("harness"),
                harness_version=event.payload.get("harness_version")
            ),
            cost_usd=0.0,
            token_usage=TokenUsage(),
            data_integrity=DataIntegrity(
                status="complete",
                gap_ranges=[],
                confidence="high"
            ),
            finding_summary=FindingSummary(),
            last_seq=0
        )

        self._sessions[event.session_id] = metadata
        self._last_seq[event.session_id] = 0

    def _record_gap(self, session: SessionMetadata, gap_start: int, gap_end: int) -> None:
        """
        Record a sequence gap in session metadata.

        Updates data_integrity status to "gaps_detected" and appends
        the gap range [start, end] to the gap_ranges list.

        Args:
            session: SessionMetadata to update
            gap_start: First missing sequence number
            gap_end: Last missing sequence number
        """
        session.data_integrity.status = "gaps_detected"
        session.data_integrity.confidence = "degraded"
        session.data_integrity.gap_ranges.append([gap_start, gap_end])

    def _update_token_usage(self, session: SessionMetadata, event: SessionEvent) -> None:
        """
        Update cumulative token usage and cost from a MODEL_CALL event.

        Args:
            session: SessionMetadata to update
            event: MODEL_CALL event with token information in payload
        """
        payload = event.payload

        # Extract token usage from event payload
        input_tokens = payload.get("input_tokens", 0)
        output_tokens = payload.get("output_tokens", 0)
        cache_read_tokens = payload.get("cache_read_tokens", 0)
        cache_write_tokens = payload.get("cache_write_tokens", 0)

        # Accumulate
        session.token_usage.input += input_tokens
        session.token_usage.output += output_tokens
        session.token_usage.cache_read += cache_read_tokens
        session.token_usage.cache_write += cache_write_tokens

        # Update cost (simplified calculation - $3/MTok input, $15/MTok output)
        # Real implementations should use model-specific pricing
        cost_input = input_tokens * 3.0 / 1_000_000
        cost_output = output_tokens * 15.0 / 1_000_000
        session.cost_usd += cost_input + cost_output
