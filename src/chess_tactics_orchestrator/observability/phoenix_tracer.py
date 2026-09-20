"""
Phoenix observability setup for LangGraph + LangChain instrumentation.

Provides OpenTelemetry tracing for the multi-agent orchestrator with:
- Automatic LangChain/LangGraph instrumentation
- Custom span annotations for agents
- Phoenix UI integration
"""

import os
from typing import Optional
from contextlib import contextmanager

from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


class PhoenixTracer:
    """
    Manages Phoenix observability instrumentation.

    Handles:
    - Phoenix tracer registration
    - LangChain auto-instrumentation
    - Custom span creation for agents
    - Environment-based configuration
    """

    def __init__(
        self,
        phoenix_endpoint: str = "http://localhost:6006",
        project_name: str = "chess-tactics-orchestrator",
        enabled: bool = True
    ):
        """
        Initialize Phoenix tracer.

        Args:
            phoenix_endpoint: Phoenix collector endpoint
            project_name: Project name for Phoenix UI filtering
            enabled: Enable/disable tracing (useful for testing)
        """
        self.phoenix_endpoint = phoenix_endpoint
        self.project_name = project_name
        self.enabled = enabled
        self._tracer_provider: Optional[TracerProvider] = None
        self._instrumentor: Optional[LangChainInstrumentor] = None

    def setup(self) -> None:
        """
        Setup Phoenix instrumentation.

        Call this ONCE at application startup, before any LangChain/LangGraph usage.
        """
        if not self.enabled:
            print("⚠️  Phoenix tracing disabled")
            return

        try:
            # Register Phoenix tracer provider
            self._tracer_provider = register(
                project_name=self.project_name,
                endpoint=f"{self.phoenix_endpoint}/v1/traces"
            )

            # Auto-instrument LangChain (covers LangGraph too)
            self._instrumentor = LangChainInstrumentor()
            self._instrumentor.instrument(tracer_provider=self._tracer_provider)

            print(f"✓ Phoenix tracing enabled: {self.phoenix_endpoint}")
            print(f"  Project: {self.project_name}")

        except Exception as e:
            print(f"⚠️  Phoenix setup failed: {e}")
            print("   Continuing without observability")
            self.enabled = False

    def teardown(self) -> None:
        """Cleanup instrumentation (call on shutdown)."""
        if self._instrumentor:
            self._instrumentor.uninstrument()

        if self._tracer_provider:
            self._tracer_provider.shutdown()

    @contextmanager
    def span(self, name: str, attributes: Optional[dict] = None):
        """
        Create custom span for manual instrumentation.

        Usage:
            with phoenix.span("research_agent", {"username": "isabido86"}):
                result = fetch_games(...)

        Args:
            name: Span name (e.g., "research_agent", "stockfish_eval")
            attributes: Optional key-value metadata
        """
        if not self.enabled:
            yield
            return

        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    # Convert non-primitives to strings
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(key, value)
                    else:
                        span.set_attribute(key, str(value))

            yield span


# Global singleton
_phoenix_tracer: Optional[PhoenixTracer] = None


def get_phoenix_tracer() -> PhoenixTracer:
    """
    Get shared Phoenix tracer instance.

    Returns:
        PhoenixTracer singleton (lazily initialized)
    """
    global _phoenix_tracer

    if _phoenix_tracer is None:
        phoenix_endpoint = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006")
        phoenix_enabled = os.getenv("PHOENIX_ENABLED", "true").lower() == "true"

        _phoenix_tracer = PhoenixTracer(
            phoenix_endpoint=phoenix_endpoint,
            enabled=phoenix_enabled
        )

    return _phoenix_tracer


def setup_observability() -> None:
    """
    Initialize observability (call at app startup).

    Usage:
        # main.py or api.py
        from observability.phoenix_tracer import setup_observability

        setup_observability()
        app = create_app()
    """
    tracer = get_phoenix_tracer()
    tracer.setup()


def teardown_observability() -> None:
    """Cleanup observability (call at app shutdown)."""
    tracer = get_phoenix_tracer()
    tracer.teardown()
