"""
ContextVersion — git-commit-style tracking of context evolution.

Tracks changes to agent context (instructions, tools, memory) using diffs
rather than full snapshots. Enables detection of instruction loss,
context compaction issues, and governance violations.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContextDiff(BaseModel):
    """
    Diff between two context versions (git-commit style).

    Tracks what was added/removed in terms of:
    - Instructions (system prompts, guidelines)
    - Tools (available functions)
    - Memory (keys in working memory)
    """
    added_instruction_refs: list[str] = Field(default_factory=list)
    removed_instruction_refs: list[str] = Field(default_factory=list)
    added_tool_refs: list[str] = Field(default_factory=list)
    removed_tool_refs: list[str] = Field(default_factory=list)
    added_memory_refs: list[str] = Field(default_factory=list)
    removed_memory_refs: list[str] = Field(default_factory=list)


class ContextVersion(BaseModel):
    """
    A snapshot + diff of agent context at a point in time.

    Like a git commit:
    - Has a unique ID (hash-based)
    - Points to parent version
    - Contains a diff of what changed
    - Has content hashes for deduplication
    - Optionally references full content in external storage

    Used for:
    - Detecting instruction loss after compaction
    - Tracking context window evolution
    - Governance checks (did critical instructions disappear?)
    """
    context_version_id: str
    session_id: str
    profile_id: str
    parent_version_id: Optional[str] = None
    timestamp: datetime
    token_count: int
    diff: ContextDiff
    instruction_set_hash: str
    tool_set_hash: str
    content_ref: Optional[str] = Field(
        None,
        description="Reference to full context content (S3 URI, file path, etc.)"
    )
    diff_ref: Optional[str] = Field(
        None,
        description="Reference to diff content (S3 URI, file path, etc.)"
    )
