"""OpenTelemetry tracing instrumentation for UAR API.

Provides distributed tracing for API requests, skill execution, and external service calls.
Configure via env:
  OTEL_ENABLED              - Enable/disable tracing (default: false)
  OTEL_EXPORTER_OTLP_ENDPOINT - OTLP exporter endpoint (default: http://localhost:4317)
  OTEL_SERVICE_NAME        - Service name (default: uar-api)
"""  # noqa: E501

from __future__ import annotations

import logging
import os
from typing import Optional, Any

logger = logging.getLogger(__name__)

_tracer = None
_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"


def init_tracing() -> None:
    """Initialize OpenTelemetry tracing."""
    global _tracer, _enabled

    if not _enabled:
        logger.info("OpenTelemetry tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        service_name = os.getenv("OTEL_SERVICE_NAME", "uar-api")
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)

        logger.info(
            f"OpenTelemetry tracing initialized for {service_name} -> {otlp_endpoint}"  # noqa: E501
        )
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"  # noqa: E501
        )
        _enabled = False
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
        _enabled = False


def get_tracer() -> Optional[Any]:
    """Get the OpenTelemetry tracer instance."""
    if _tracer is None:
        init_tracing()
    return _tracer


def is_enabled() -> bool:
    """Check if tracing is enabled."""
    return _enabled


def trace_span(name: str, attributes: Optional[dict] = None) -> Any:
    """Context manager for tracing a span.

    Usage:
        with trace_span("skill_execution", {"skill": "doc_ingest"}):
            # code to trace
    """
    if not _enabled:
        return NoOpSpan()

    tracer = get_tracer()
    if tracer is None:
        return NoOpSpan()

    return tracer.start_as_current_span(name, attributes=attributes or {})


class NoOpSpan:
    """No-op span context manager when tracing is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def add_event(self, name, attributes=None):
        pass

    def set_attribute(self, key, value):
        pass

    def set_status(self, status):
        pass


# Initialize tracing on import
init_tracing()
