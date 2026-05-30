"""Tests for uar.api.tracing."""

import os
from unittest.mock import MagicMock, patch

from uar.api.tracing import (
    init_tracing,
    get_tracer,
    is_enabled,
    trace_span,
    NoOpSpan,
    setup_fastapi_tracing,
    _fastapi_tracing_available,
)


class TestInitTracing:
    def test_disabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "false"}):
            init_tracing()
        assert is_enabled() is False

    def test_enabled_no_opentelemetry(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}):
            with patch.dict("sys.modules", {"opentelemetry": None}):
                init_tracing()
        assert is_enabled() is False

    def test_enabled_with_mock(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}):
            mock_trace = type(
                "trace",
                (),
                {
                    "set_tracer_provider": lambda x: None,
                    "get_tracer": lambda name: "mock_tracer",
                },
            )()
            mock_provider = type(
                "TracerProvider",
                (),
                {"add_span_processor": lambda self, p: None},
            )()
            mock_resource = type(
                "Resource", (), {"create": lambda cls, d: None}
            )()
            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": type(
                        "mod", (), {"trace": mock_trace}
                    )(),
                    "opentelemetry.sdk.trace": type(
                        "mod",
                        (),
                        {"TracerProvider": lambda **k: mock_provider},
                    )(),
                    "opentelemetry.sdk.trace.export": type(
                        "mod", (), {"BatchSpanProcessor": lambda x: None}
                    )(),
                    "opentelemetry.exporter.otlp.proto.grpc"
                    ".trace_exporter": type(
                        "mod",
                        (),
                        {"OTLPSpanExporter": lambda **k: None},
                    )(),
                    "opentelemetry.sdk.resources": type(
                        "mod",
                        (),
                        {
                            "Resource": mock_resource,
                            "SERVICE_NAME": "service.name",
                        },
                    )(),
                },
            ):
                init_tracing()


class TestGetTracer:
    def test_returns_none_when_disabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "false"}):
            assert get_tracer() is None


class TestTraceSpan:
    def test_disabled(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "false"}):
            with trace_span("test") as span:
                assert isinstance(span, NoOpSpan)

    def test_enabled_no_tracer(self):
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}):
            with trace_span("test") as span:
                assert isinstance(span, NoOpSpan)


class TestNoOpSpan:
    def test_context_manager(self):
        span = NoOpSpan()
        with span as s:
            assert s is span

    def test_methods(self):
        span = NoOpSpan()
        span.add_event("event")
        span.set_attribute("key", "value")
        span.set_status("ok")


class TestSetupFastapiTracing:
    def test_not_available(self):
        app = MagicMock()
        with patch(
            "uar.api.tracing._fastapi_tracing_available", False
        ):
            setup_fastapi_tracing(app)

    def test_available_disabled(self):
        app = MagicMock()
        with patch(
            "uar.api.tracing._fastapi_tracing_available", True
        ):
            with patch.dict(os.environ, {"UAR_ENABLE_TRACING": ""}):
                setup_fastapi_tracing(app)

    def test_available_enabled(self):
        # FastAPIInstrumentor only exists when opentelemetry is installed
        # Skip if not available
        if not _fastapi_tracing_available:
            return
        app = MagicMock()
        with patch.dict(
            os.environ, {"UAR_ENABLE_TRACING": "true"}
        ):
            setup_fastapi_tracing(app)
