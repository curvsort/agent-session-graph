"""
Context tracking and instruction loss detection tests.

Tests the ContextDiffEngine reference implementation for:
- Context version creation with hash computation
- Git-style diff computation between versions
- Instruction loss detection during context compaction
- Tool set changes tracking
"""
from agent_session_graph.detection import ContextDiffEngine


def test_build_context_version_initial():
    """Test building initial context version (no parent)."""
    engine = ContextDiffEngine()

    version = engine.build_context_version(
        session_id="sess_001",
        profile_id="profile_default",
        instructions=["Be polite", "Never share personal data"],
        tools=["search", "summarize"],
        parent_version_id=None,
        token_count=150
    )

    # Verify basic fields
    assert version.session_id == "sess_001"
    assert version.profile_id == "profile_default"
    assert version.parent_version_id is None
    assert version.token_count == 150

    # Verify hashes are computed
    assert version.instruction_set_hash
    assert version.tool_set_hash
    assert len(version.instruction_set_hash) == 64  # SHA256 hex

    # Verify diff is empty for initial version
    assert len(version.diff.added_instruction_refs) == 0
    assert len(version.diff.removed_instruction_refs) == 0
    assert len(version.diff.added_tool_refs) == 0
    assert len(version.diff.removed_tool_refs) == 0


def test_context_version_diff_computation():
    """Test diff computation between parent and child versions."""
    engine = ContextDiffEngine()

    # Create parent version
    v1 = engine.build_context_version(
        session_id="sess_002",
        profile_id="profile_default",
        instructions=["Be polite", "Never share personal data", "Verify sources"],
        tools=["search", "summarize"],
        parent_version_id=None,
        token_count=200
    )

    # Create child version with changes
    v2 = engine.build_context_version(
        session_id="sess_002",
        profile_id="profile_default",
        instructions=["Be polite", "Check credentials"],  # Removed 2, added 1
        tools=["search", "summarize", "authenticate"],  # Added 1 tool
        parent_version_id=v1.context_version_id,
        token_count=180
    )

    # Verify parent relationship
    assert v2.parent_version_id == v1.context_version_id

    # Verify instruction diff
    assert "Check credentials" in v2.diff.added_instruction_refs
    assert "Never share personal data" in v2.diff.removed_instruction_refs
    assert "Verify sources" in v2.diff.removed_instruction_refs
    assert "Be polite" not in v2.diff.added_instruction_refs  # Unchanged

    # Verify tool diff
    assert "authenticate" in v2.diff.added_tool_refs
    assert len(v2.diff.removed_tool_refs) == 0


def test_instruction_loss_detection():
    """Test detection of critical instruction loss."""
    engine = ContextDiffEngine()

    # Initial context with critical instructions
    v1 = engine.build_context_version(
        session_id="sess_003",
        profile_id="profile_default",
        instructions=[
            "Never approve refunds over $100",
            "Always verify identity",
            "Be professional"
        ],
        tools=["approve_refund", "verify_identity"],
        parent_version_id=None,
        token_count=250
    )

    # Context after compaction - lost critical instruction
    v2 = engine.build_context_version(
        session_id="sess_003",
        profile_id="profile_default",
        instructions=["Be professional"],  # Lost both critical instructions!
        tools=["approve_refund", "verify_identity"],
        parent_version_id=v1.context_version_id,
        token_count=100
    )

    # Check for instruction loss
    original_instructions = {
        "Never approve refunds over $100": "Never approve refunds over $100",
        "Always verify identity": "Always verify identity",
        "Be professional": "Be professional"
    }

    findings = engine.check_instruction_loss(
        context_versions=[v1, v2],
        original_instructions=original_instructions
    )

    # Should detect loss in v2
    assert len(findings) == 1
    finding = findings[0]

    assert finding.finding_class == "governance"
    assert finding.finding_type == "critical_instruction_loss"
    assert finding.severity == "high"
    assert finding.session_id == "sess_003"
    assert "Never approve refunds over $100" in finding.root_cause_summary
    assert "Always verify identity" in finding.root_cause_summary


def test_no_instruction_loss_when_unchanged():
    """Test that unchanged instructions don't trigger findings."""
    engine = ContextDiffEngine()

    v1 = engine.build_context_version(
        session_id="sess_004",
        profile_id="profile_default",
        instructions=["Be polite", "Verify sources"],
        tools=["search"],
        parent_version_id=None,
        token_count=150
    )

    # Same instructions, different tools
    v2 = engine.build_context_version(
        session_id="sess_004",
        profile_id="profile_default",
        instructions=["Be polite", "Verify sources"],  # Unchanged
        tools=["search", "summarize"],  # Added tool
        parent_version_id=v1.context_version_id,
        token_count=160
    )

    findings = engine.check_instruction_loss(
        context_versions=[v1, v2],
        original_instructions={
            "Be polite": "Be polite",
            "Verify sources": "Verify sources"
        }
    )

    # No instruction loss
    assert len(findings) == 0


def test_hash_deterministic():
    """Test that hashes are deterministic for same content."""
    engine1 = ContextDiffEngine()
    engine2 = ContextDiffEngine()

    instructions = ["Be polite", "Verify sources"]
    tools = ["search", "summarize"]

    v1 = engine1.build_context_version(
        session_id="sess_005",
        profile_id="profile_default",
        instructions=instructions,
        tools=tools,
        parent_version_id=None,
        token_count=150
    )

    v2 = engine2.build_context_version(
        session_id="sess_006",  # Different session
        profile_id="profile_default",
        instructions=instructions,  # Same content
        tools=tools,
        parent_version_id=None,
        token_count=150
    )

    # Hashes should be identical for same content
    assert v1.instruction_set_hash == v2.instruction_set_hash
    assert v1.tool_set_hash == v2.tool_set_hash


def test_hash_order_independent():
    """Test that instruction order doesn't affect hash."""
    engine = ContextDiffEngine()

    v1 = engine.build_context_version(
        session_id="sess_007",
        profile_id="profile_default",
        instructions=["A", "B", "C"],
        tools=["tool1"],
        parent_version_id=None,
        token_count=100
    )

    v2 = engine.build_context_version(
        session_id="sess_008",
        profile_id="profile_default",
        instructions=["C", "A", "B"],  # Different order
        tools=["tool1"],
        parent_version_id=None,
        token_count=100
    )

    # Hashes should be identical (order-independent)
    assert v1.instruction_set_hash == v2.instruction_set_hash


def test_context_evolution_chain():
    """Test tracking context evolution through multiple versions."""
    engine = ContextDiffEngine()

    # Version 1: Initial state
    v1 = engine.build_context_version(
        session_id="sess_009",
        profile_id="profile_default",
        instructions=["A", "B", "C"],
        tools=["tool1", "tool2"],
        parent_version_id=None,
        token_count=200
    )

    # Version 2: Remove one instruction, add one tool
    v2 = engine.build_context_version(
        session_id="sess_009",
        profile_id="profile_default",
        instructions=["A", "B"],  # Lost C
        tools=["tool1", "tool2", "tool3"],  # Added tool3
        parent_version_id=v1.context_version_id,
        token_count=180
    )

    # Version 3: Add instruction back, remove tool
    v3 = engine.build_context_version(
        session_id="sess_009",
        profile_id="profile_default",
        instructions=["A", "B", "C"],  # C is back
        tools=["tool1", "tool3"],  # Lost tool2
        parent_version_id=v2.context_version_id,
        token_count=190
    )

    # Verify chain
    assert v1.parent_version_id is None
    assert v2.parent_version_id == v1.context_version_id
    assert v3.parent_version_id == v2.context_version_id

    # Verify v2 diff
    assert "C" in v2.diff.removed_instruction_refs
    assert "tool3" in v2.diff.added_tool_refs

    # Verify v3 diff (relative to v2)
    assert "C" in v3.diff.added_instruction_refs
    assert "tool2" in v3.diff.removed_tool_refs


def test_tool_removal_tracking():
    """Test detection of tool removals."""
    engine = ContextDiffEngine()

    v1 = engine.build_context_version(
        session_id="sess_010",
        profile_id="profile_default",
        instructions=["Use tools wisely"],
        tools=["search", "summarize", "translate", "verify"],
        parent_version_id=None,
        token_count=200
    )

    v2 = engine.build_context_version(
        session_id="sess_010",
        profile_id="profile_default",
        instructions=["Use tools wisely"],
        tools=["search", "summarize"],  # Lost translate and verify
        parent_version_id=v1.context_version_id,
        token_count=150
    )

    # Verify tool removals tracked
    assert "translate" in v2.diff.removed_tool_refs
    assert "verify" in v2.diff.removed_tool_refs
    assert len(v2.diff.removed_tool_refs) == 2
    assert len(v2.diff.added_tool_refs) == 0


def test_empty_context_version():
    """Test handling of empty instruction/tool sets."""
    engine = ContextDiffEngine()

    v1 = engine.build_context_version(
        session_id="sess_011",
        profile_id="profile_default",
        instructions=[],
        tools=[],
        parent_version_id=None,
        token_count=50
    )

    # Should not crash
    assert v1.instruction_set_hash
    assert v1.tool_set_hash
    assert len(v1.diff.added_instruction_refs) == 0


def test_multiple_sessions_isolated():
    """Test that different sessions have isolated version chains."""
    engine = ContextDiffEngine()

    # Session A
    v1a = engine.build_context_version(
        session_id="sess_012",
        profile_id="profile_default",
        instructions=["A"],
        tools=["tool1"],
        parent_version_id=None,
        token_count=100
    )

    # Session B (different session, unrelated)
    v1b = engine.build_context_version(
        session_id="sess_013",
        profile_id="profile_default",
        instructions=["B"],
        tools=["tool2"],
        parent_version_id=None,
        token_count=100
    )

    # Both should have no parent
    assert v1a.parent_version_id is None
    assert v1b.parent_version_id is None

    # Session IDs should differ
    assert v1a.session_id != v1b.session_id
