"""
OTel span ingestion and normalization.

Converts OpenTelemetry trace data into SessionEvent objects.
"""
from agent_session_graph.ingestion.normalizer import normalize_span, normalize_trace

__all__ = [
    "normalize_span",
    "normalize_trace",
]
