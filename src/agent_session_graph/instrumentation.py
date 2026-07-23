"""
OpenTelemetry instrumentation helper for multi-agent systems.

Provides a simple way to instrument Python agents with OTel tracing
that can be consumed by agent-session-graph's normalizer.

This module requires the optional 'instrumentation' extra:
    pip install agent-session-graph[instrumentation]

Usage:
    from agent_session_graph.instrumentation import setup_tracing

    tracer = setup_tracing(service_name="my_agent")

    with tracer.start_as_current_span("agent.start") as span:
        span.set_attribute("agent_id", "coordinator")
        span.set_attribute("session_id", "sess_123")
        # ... agent work ...
"""
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:
    raise ImportError(
        "OpenTelemetry SDK not installed. "
        "Install with: pip install agent-session-graph[instrumentation]"
    )


def setup_tracing(
    service_name: str,
    otlp_endpoint: str = "http://localhost:4317"
) -> trace.Tracer:
    """
    Set up OpenTelemetry tracing for agent instrumentation.

    Creates a TracerProvider with an OTLP exporter pointing at your collector.
    The collector receives spans via gRPC and can forward them to your
    ingestion pipeline.

    Args:
        service_name: Name of the agent/service being instrumented
                      (appears in span attributes)
        otlp_endpoint: OTLP collector gRPC endpoint
                       (default: http://localhost:4317)

    Returns:
        Tracer instance for creating spans

    Example:
        tracer = setup_tracing("my_agent")

        with tracer.start_as_current_span("agent.start") as span:
            span.set_attribute("agent_id", "coordinator")
            span.set_attribute("session_id", "sess_123")
            # ... agent logic ...

        with tracer.start_as_current_span("model.call") as span:
            span.set_attribute("model", "claude-3.5-sonnet")
            span.set_attribute("input_tokens", 1500)
            # ... LLM call ...
    """
    # Create tracer provider
    provider = TracerProvider()

    # Create OTLP exporter pointing at collector
    exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True  # Use TLS in production
    )

    # Add batch processor to avoid blocking on every span
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Return a tracer for the given service
    return trace.get_tracer(service_name)
