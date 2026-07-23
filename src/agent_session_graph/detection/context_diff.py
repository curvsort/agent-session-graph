"""
Reference implementation of context versioning and instruction loss detection.

This module provides tools for tracking context evolution across an agent session:
- Deterministic hash computation for instruction/tool sets
- Git-style diff computation between context versions
- Detection of critical instruction loss during context compaction

These are REFERENCE IMPLEMENTATIONS. Users should adapt the instruction loss
rules to match their specific governance requirements (e.g., what constitutes
a "critical" instruction, acceptable instruction drift thresholds).

Example usage:
    from agent_session_graph.detection import ContextDiffEngine

    engine = ContextDiffEngine()

    # Build versioned context snapshots
    version_1 = engine.build_context_version(
        session_id="sess_123",
        profile_id="agent_profile_1",
        instructions=["Never approve refunds over $100", "Be polite"],
        tools=["approve_refund", "escalate"],
        parent_version_id=None,
        token_count=150
    )

    version_2 = engine.build_context_version(
        session_id="sess_123",
        profile_id="agent_profile_1",
        instructions=["Be polite"],  # Lost the refund policy!
        tools=["approve_refund", "escalate"],
        parent_version_id=version_1.context_version_id,
        token_count=120
    )

    # Detect instruction loss
    findings = engine.check_instruction_loss(
        context_versions=[version_1, version_2],
        original_instructions={
            "Never approve refunds over $100": "Never approve refunds over $100",
            "Be polite": "Be polite"
        }
    )
"""
import hashlib
from datetime import datetime, timezone

from agent_session_graph.schemas.context_version import ContextDiff, ContextVersion
from agent_session_graph.schemas.finding import Finding


def compute_hash(items: list[str]) -> str:
    """
    Deterministic SHA256 hash of a list of strings.
    Sorts items before hashing to ensure order-independence.

    Args:
        items: List of strings to hash

    Returns:
        SHA256 hash (hex digest)
    """
    sorted_items = sorted(items)
    joined = "\n".join(sorted_items)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class ContextDiffEngine:
    """
    Builds ContextVersion objects with computed hashes and diffs.
    Maintains in-memory cache of previous versions for diff computation.

    This is a REFERENCE IMPLEMENTATION. Users should extend this class to:
    - Integrate with their storage backend for version persistence
    - Customize instruction loss severity/classification rules
    - Add additional diff computation strategies (e.g., semantic similarity)

    Args:
        storage: Optional storage backend for persisting context versions.
                 If provided, should implement write_context_version(version).
                 Defaults to None (in-memory only).
    """

    def __init__(self, storage=None):
        """
        Initialize the context diff engine.

        Args:
            storage: Optional storage backend with write_context_version() method
        """
        self._version_cache: dict[str, dict[str, list[str]]] = {}
        self.storage = storage

    def build_context_version(
        self,
        session_id: str,
        profile_id: str,
        instructions: list[str],
        tools: list[str],
        parent_version_id: str | None,
        token_count: int,
    ) -> ContextVersion:
        """
        Build a ContextVersion with computed hashes and diff.

        Args:
            session_id: Session identifier
            profile_id: Profile identifier
            instructions: List of instruction strings
            tools: List of tool names
            parent_version_id: Optional parent version for diff computation
            token_count: Token count for this context version

        Returns:
            Populated ContextVersion object with computed hashes and diff
        """
        context_version_id = f"cv_{session_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        instruction_set_hash = compute_hash(instructions)
        tool_set_hash = compute_hash(tools)

        diff = self._compute_diff(
            instructions=instructions,
            tools=tools,
            parent_version_id=parent_version_id,
        )

        self._version_cache[context_version_id] = {
            "instructions": instructions,
            "tools": tools,
        }

        return ContextVersion(
            context_version_id=context_version_id,
            session_id=session_id,
            profile_id=profile_id,
            parent_version_id=parent_version_id,
            timestamp=datetime.now(timezone.utc),
            token_count=token_count,
            diff=diff,
            instruction_set_hash=instruction_set_hash,
            tool_set_hash=tool_set_hash,
            content_ref=None,
            diff_ref=None,
        )

    def _compute_diff(
        self,
        instructions: list[str],
        tools: list[str],
        parent_version_id: str | None,
    ) -> ContextDiff:
        """
        Compute diff by comparing current sets against cached parent.

        Returns empty diff if no parent exists.
        """
        if parent_version_id is None or parent_version_id not in self._version_cache:
            return ContextDiff()

        parent = self._version_cache[parent_version_id]
        parent_instructions = set(parent["instructions"])
        parent_tools = set(parent["tools"])

        current_instructions = set(instructions)
        current_tools = set(tools)

        return ContextDiff(
            added_instruction_refs=sorted(current_instructions - parent_instructions),
            removed_instruction_refs=sorted(parent_instructions - current_instructions),
            added_tool_refs=sorted(current_tools - parent_tools),
            removed_tool_refs=sorted(parent_tools - current_tools),
        )

    def check_instruction_loss(
        self,
        context_versions: list[ContextVersion],
        original_instructions: dict[str, str],
    ) -> list[Finding]:
        """
        Detect critical instruction loss across context versions.

        This is a REFERENCE IMPLEMENTATION with a simple rule: any removed
        instruction generates a high-severity finding. Users should customize
        this logic to match their governance model:
        - Classify instructions by criticality (e.g., safety vs. style)
        - Allow acceptable instruction drift (e.g., rephrasings)
        - Add semantic similarity checks for instruction equivalence

        Args:
            context_versions: List of ContextVersion objects to check
            original_instructions: Mapping from instruction text to itself
                                   (or instruction ID to text)

        Returns:
            List of Finding objects for versions with removed instructions
        """
        findings = []

        for cv in context_versions:
            if not cv.diff.removed_instruction_refs:
                continue

            removed_texts = [
                original_instructions.get(ref, ref)
                for ref in cv.diff.removed_instruction_refs
            ]

            ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            finding_id = f"find_{cv.context_version_id}_{ts_ms}"

            finding = Finding(
                finding_id=finding_id,
                session_id=cv.session_id,
                finding_class="governance",
                finding_type="critical_instruction_loss",
                severity="high",
                triggering_event_ids=[cv.context_version_id],
                root_cause_summary=(
                    f"Lost {len(removed_texts)} instruction(s): "
                    f"{', '.join(removed_texts)}"
                ),
                context_diff_ref=cv.diff_ref,
                detected_at=datetime.now(timezone.utc),
            )

            findings.append(finding)

        return findings
