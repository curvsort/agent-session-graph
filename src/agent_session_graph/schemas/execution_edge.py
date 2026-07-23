"""
ExecutionEdge — causal relationships between SessionEvents.

Edges answer "why did X happen?" by pointing to the cause.
Forms the execution graph that traces lineage through agent delegations,
tool invocations, memory reads, and causal relationships.
"""
from typing import Literal

from pydantic import BaseModel


class ExecutionEdge(BaseModel):
    """
    Directed edge between two SessionEvents representing a causal relationship.

    Edge types:
    - caused_by: Generic parent-child causal relationship (from parent_event_id)
    - delegated_to: Agent A delegated to Agent B
    - invoked: Tool call resulted in this response
    - returned_to: Agent returned control to caller
    - read_from: Memory read from this write
    - written_by: Memory write that created this state
    - triggered_finding: Event that caused this anomaly to be detected
    """
    edge_id: str
    session_id: str
    source_event_id: str
    target_event_id: str
    edge_type: Literal[
        "caused_by",
        "delegated_to",
        "invoked",
        "returned_to",
        "read_from",
        "written_by",
        "triggered_finding"
    ]
