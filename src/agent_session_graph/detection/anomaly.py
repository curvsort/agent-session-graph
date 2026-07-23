"""
Reference implementation of anomaly detection rules for agent sessions.

This module provides three core detection methods for common runtime anomalies:
- Recursive agent loops (uncontrolled delegation cycles)
- Token explosion (rapidly growing context windows)
- Probable context compaction (inferred from token drops)

These are REFERENCE IMPLEMENTATIONS that demonstrate detection patterns. Users
should extend or replace these with domain-specific rules. The detector is
designed to be cheap to run (hash-based comparison on every event) with expensive
LLM-based explanation deferred to confirmed findings.

Example usage:
    from agent_session_graph.detection import AnomalyDetector
    from agent_session_graph.storage import PostgresStorage

    storage = PostgresStorage(connection_string)
    detector = AnomalyDetector(storage=storage)

    findings = detector.run_all_checks(session_id, events, edges)
    for finding in findings:
        storage.write_finding(finding)
"""
import hashlib
from datetime import datetime, timezone

from agent_session_graph.schemas.execution_edge import ExecutionEdge
from agent_session_graph.schemas.finding import Finding
from agent_session_graph.schemas.session_event import EventType, SessionEvent


class AnomalyDetector:
    """
    Detects runtime anomalies in agent execution sessions.

    Implements rules-based, fast anomaly detection:
    - Recursive agent loops
    - Token explosion
    - Probable context compaction (inferred from token drops)

    These detection rules are reference implementations. Users should
    extend this class or implement custom detectors for their specific
    agent architectures and failure modes.

    Args:
        storage: Optional storage backend for persisting findings.
                 If provided, should implement write_finding(finding).
                 Defaults to None (detection only, no persistence).
    """

    def __init__(self, storage=None):
        """
        Initialize the anomaly detector.

        Args:
            storage: Optional storage backend with write_finding() method
        """
        self.storage = storage

    def check_recursive_loop(
        self,
        session_id: str,
        events: list[SessionEvent],
        edges: list[ExecutionEdge],
        threshold: int = 3
    ) -> list[Finding]:
        """
        Detect recursive agent loops.

        Checks if the same participant_id appears in 3+ AGENT_DELEGATE events
        with similar payload structure (delegating to the same target agent).

        Args:
            session_id: Session identifier
            events: List of SessionEvents
            edges: List of ExecutionEdges (not used currently, reserved for future)
            threshold: Minimum number of recursive delegations to trigger (default: 3)

        Returns:
            List of Finding objects (empty if no anomaly detected)
        """
        findings = []

        # Find all AGENT_DELEGATE events
        delegate_events = [
            e for e in events
            if e.event_type == EventType.AGENT_DELEGATE
        ]

        if len(delegate_events) < threshold:
            return findings

        # Group by participant_id and delegated_to target
        recursion_patterns = {}
        for event in delegate_events:
            participant = event.participant_id
            delegated_to = event.payload.get("delegated_to")

            if not participant or not delegated_to:
                continue

            # Key is (participant, target)
            key = (participant, delegated_to)

            if key not in recursion_patterns:
                recursion_patterns[key] = []

            recursion_patterns[key].append(event.event_id)

        # Check for patterns that exceed threshold
        for (participant, target), event_ids in recursion_patterns.items():
            if len(event_ids) >= threshold:
                # Recursive loop detected!
                finding_id = self._generate_finding_id(
                    session_id,
                    "recursive_agent_loop",
                    event_ids[0]
                )

                finding = Finding(
                    finding_id=finding_id,
                    session_id=session_id,
                    finding_class="anomaly",
                    finding_type="recursive_agent_loop",
                    severity="critical",
                    triggering_event_ids=event_ids,
                    root_cause_summary=(
                        f"Agent '{participant}' recursively delegated to '{target}' "
                        f"{len(event_ids)} times. This indicates an uncontrolled "
                        f"recursion loop that will exhaust resources."
                    ),
                    detected_at=datetime.now(timezone.utc),
                    status="open"
                )

                findings.append(finding)

        return findings

    def check_token_explosion(
        self,
        session_id: str,
        events: list[SessionEvent],
        growth_threshold: float = 3.0
    ) -> list[Finding]:
        """
        Detect token explosion in model calls.

        Analyzes consecutive MODEL_CALL/MODEL_RESPONSE events for rapidly
        growing token counts. Uses a rolling window of 5 events to detect
        growth ratios exceeding the threshold.

        Args:
            session_id: Session identifier
            events: List of SessionEvents
            growth_threshold: Minimum growth ratio to trigger (default: 3.0x)

        Returns:
            List of Finding objects (empty if no anomaly detected)
        """
        findings = []

        # Find all MODEL_CALL events with token counts
        model_events = []
        for event in events:
            if event.event_type in [EventType.MODEL_CALL, EventType.MODEL_RESPONSE]:
                # Extract token count from payload
                # Check multiple possible field names
                input_tokens = event.payload.get("input_tokens") or event.payload.get("tokens") or 0
                output_tokens = event.payload.get("output_tokens", 0)
                total_tokens = input_tokens + output_tokens

                if total_tokens > 0:
                    model_events.append({
                        "event_id": event.event_id,
                        "tokens": total_tokens,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens
                    })

        if len(model_events) < 2:
            return findings

        # Check for token explosion using rolling window
        window_size = min(5, len(model_events))

        for i in range(window_size - 1, len(model_events)):
            # Get window of events
            window_start = max(0, i - window_size + 1)
            window = model_events[window_start:i + 1]

            # Calculate growth ratio (latest / earliest in window)
            earliest_tokens = window[0]["tokens"]
            latest_tokens = window[-1]["tokens"]

            if earliest_tokens == 0:
                continue

            growth_ratio = latest_tokens / earliest_tokens

            if growth_ratio >= growth_threshold:
                # Token explosion detected!
                triggering_event_ids = [e["event_id"] for e in window]

                finding_id = self._generate_finding_id(
                    session_id,
                    "token_explosion",
                    triggering_event_ids[0]
                )

                # Determine severity based on growth ratio
                if growth_ratio >= 5.0:
                    severity = "high"
                else:
                    severity = "medium"

                finding = Finding(
                    finding_id=finding_id,
                    session_id=session_id,
                    finding_class="anomaly",
                    finding_type="token_explosion",
                    severity=severity,
                    triggering_event_ids=triggering_event_ids,
                    root_cause_summary=(
                        f"Token count exploded from {earliest_tokens:,} to {latest_tokens:,} "
                        f"(growth ratio: {growth_ratio:.1f}x) over {len(window)} model calls. "
                        f"This indicates uncontrolled context growth that will lead to "
                        f"performance degradation and increased costs."
                    ),
                    detected_at=datetime.now(timezone.utc),
                    status="open"
                )

                findings.append(finding)

                # Only report the first detected explosion to avoid duplicates
                break

        return findings

    def check_probable_compaction(
        self,
        session_id: str,
        events: list[SessionEvent]
    ) -> list[Finding]:
        """
        Infers probable context compaction from token count patterns when
        no explicit CONTEXT_COMPACTION event was emitted by the harness.

        Detection logic:
        - Collect all MODEL_CALL events with token counts in payload
        - If tokens drop by >40% between consecutive MODEL_CALL events
          (e.g. 45000 tokens -> 8000 tokens) without a preceding
          CONTEXT_COMPACTION event, emit a Finding with:
          finding_type="probable_compaction_inferred"
          severity="medium"
          root_cause_summary describing the token drop percentage
          and noting this is inferred (no explicit compaction signal)

        This covers the case where agent harnesses compact context without
        emitting an explicit OTel compaction span.

        For explicit compaction detection (higher confidence), the
        harness must emit a CONTEXT_COMPACTION span/event.

        Args:
            session_id: Session identifier
            events: List of SessionEvents

        Returns:
            List of Finding objects (empty if no probable compaction detected)
        """
        findings = []

        # Track MODEL_CALL events with token counts and CONTEXT_COMPACTION events
        model_call_tokens = []
        compaction_event_seqs = set()

        for event in events:
            if event.event_type == EventType.CONTEXT_COMPACTION:
                compaction_event_seqs.add(event.seq)
            elif event.event_type == EventType.MODEL_CALL:
                # Extract token count from payload
                input_tokens = event.payload.get("input_tokens") or event.payload.get("tokens") or 0
                if input_tokens > 0:
                    model_call_tokens.append({
                        "event_id": event.event_id,
                        "seq": event.seq,
                        "tokens": input_tokens
                    })

        # Need at least 2 MODEL_CALL events to detect a drop
        if len(model_call_tokens) < 2:
            return findings

        # Check consecutive MODEL_CALL events for significant token drops
        for i in range(1, len(model_call_tokens)):
            prev = model_call_tokens[i - 1]
            curr = model_call_tokens[i]

            # Calculate token drop percentage
            if prev["tokens"] == 0:
                continue

            drop_ratio = (prev["tokens"] - curr["tokens"]) / prev["tokens"]

            # Detect >40% drop without an explicit CONTEXT_COMPACTION between these events
            if drop_ratio > 0.4:
                # Check if there was an explicit CONTEXT_COMPACTION event between prev and curr
                has_explicit_compaction = any(
                    prev["seq"] < comp_seq < curr["seq"]
                    for comp_seq in compaction_event_seqs
                )

                if not has_explicit_compaction:
                    # Probable compaction detected!
                    finding_id = self._generate_finding_id(
                        session_id,
                        "probable_compaction_inferred",
                        prev["event_id"]
                    )

                    drop_percentage = int(drop_ratio * 100)

                    finding = Finding(
                        finding_id=finding_id,
                        session_id=session_id,
                        finding_class="anomaly",
                        finding_type="probable_compaction_inferred",
                        severity="medium",
                        triggering_event_ids=[prev["event_id"], curr["event_id"]],
                        root_cause_summary=(
                            f"Probable context compaction inferred: "
                            f"token count dropped {drop_percentage}% "
                            f"from {prev['tokens']:,} to "
                            f"{curr['tokens']:,} tokens between "
                            f"seq={prev['seq']} "
                            f"and seq={curr['seq']} without an explicit "
                            f"CONTEXT_COMPACTION event. "
                            f"This suggests the agent framework performed "
                            f"context compression internally "
                            f"without emitting telemetry. For "
                            f"higher-confidence detection, instrument "
                            f"the harness to emit "
                            f"CONTEXT_COMPACTION spans."
                        ),
                        detected_at=datetime.now(timezone.utc),
                        status="open"
                    )

                    findings.append(finding)

                    # Only report the first detected probable compaction to avoid duplicates
                    break

        return findings

    def run_all_checks(
        self,
        session_id: str,
        events: list[SessionEvent],
        edges: list[ExecutionEdge]
    ) -> list[Finding]:
        """
        Run all anomaly detection checks.

        Args:
            session_id: Session identifier
            events: List of SessionEvents
            edges: List of ExecutionEdges

        Returns:
            Combined list of all findings from all checks
        """
        findings = []

        # Run recursive loop check
        findings.extend(self.check_recursive_loop(session_id, events, edges))

        # Run token explosion check
        findings.extend(self.check_token_explosion(session_id, events))

        # Run probable compaction check
        findings.extend(self.check_probable_compaction(session_id, events))

        return findings

    def _generate_finding_id(
        self,
        session_id: str,
        finding_type: str,
        first_event_id: str
    ) -> str:
        """
        Generate deterministic finding_id.

        Args:
            session_id: Session identifier
            finding_type: Type of finding
            first_event_id: First triggering event ID

        Returns:
            Deterministic finding_id
        """
        finding_key = f"{session_id}:{finding_type}:{first_event_id}"
        finding_hash = hashlib.sha256(finding_key.encode()).hexdigest()[:16]
        return f"finding_{session_id}_{finding_hash}"
