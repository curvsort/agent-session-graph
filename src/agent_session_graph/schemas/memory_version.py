"""
MemoryVersion — tracking of agent memory state mutations.

Records when a memory key changed, what it changed from/to,
and staleness metrics (time since last read).
"""
from pydantic import BaseModel
from typing import Optional


class MemoryVersion(BaseModel):
    """
    A mutation event for a memory key.

    Tracks:
    - Which memory key changed
    - Content hashes (old → new) for deduplication
    - Which event wrote it
    - When it was last read (staleness tracking)
    - Change summary (optional human-readable description)

    Used for:
    - Detecting stale memory that's never read
    - Tracking memory churn patterns
    - Understanding memory usage across agent delegations
    """
    memory_version_id: str
    session_id: str
    memory_key: str
    old_hash: str
    new_hash: str
    change_summary: Optional[str] = None
    written_by_event_id: str
    last_read_event_id: Optional[str] = None
    staleness_at_write_ms: Optional[int] = None
