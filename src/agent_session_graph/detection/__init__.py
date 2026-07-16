"""
Detection modules for agent session analysis.

This package provides reference implementations of detection engines for common
runtime anomalies and governance violations in multi-agent systems:

Anomaly Detection (anomaly.py):
    - Recursive agent loops (uncontrolled delegation cycles)
    - Token explosion (rapidly growing context windows)
    - Probable context compaction (inferred from token drops)

Context Diff Engine (context_diff.py):
    - Context versioning with deterministic hashing
    - Git-style diffs for instruction/tool set changes
    - Detection of critical instruction loss during compaction

These are REFERENCE IMPLEMENTATIONS designed to demonstrate detection patterns.
Users should:
- Extend these classes with domain-specific rules
- Replace detection logic to match their agent architectures
- Customize severity/classification to match their governance model

Example usage:
    from agent_session_graph.detection import AnomalyDetector, ContextDiffEngine

    # Anomaly detection
    detector = AnomalyDetector(storage=your_storage_backend)
    findings = detector.run_all_checks(session_id, events, edges)

    # Context versioning
    engine = ContextDiffEngine(storage=your_storage_backend)
    version = engine.build_context_version(
        session_id="sess_123",
        profile_id="agent_1",
        instructions=["Rule 1", "Rule 2"],
        tools=["tool_a", "tool_b"],
        parent_version_id=None,
        token_count=150
    )
    findings = engine.check_instruction_loss([version], original_instructions)
"""

from agent_session_graph.detection.anomaly import AnomalyDetector
from agent_session_graph.detection.context_diff import ContextDiffEngine, compute_hash

__all__ = [
    "AnomalyDetector",
    "ContextDiffEngine",
    "compute_hash",
]
