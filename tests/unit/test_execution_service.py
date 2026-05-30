"""Tests for uar.services.execution."""

import asyncio
import os
from unittest.mock import MagicMock, patch

from uar.services.execution import (
    AdaptiveBackpressure,
    GoalExecutionService,
)


class TestAdaptiveBackpressure:
    def test_disabled(self):
        bp = AdaptiveBackpressure(enabled=False)
        asyncio.run(bp.apply())

    def test_first_call(self):
        bp = AdaptiveBackpressure(enabled=True)
        asyncio.run(bp.apply())
        assert bp._last_emit_time > 0

    def test_slow_consumer(self):
        bp = AdaptiveBackpressure(
            enabled=True, slow_threshold=0.01, increment=0.05
        )
        bp._last_emit_time = 0.1
        asyncio.run(bp.apply())
        assert bp._current_delay > 0

    def test_fast_consumer(self):
        bp = AdaptiveBackpressure(
            enabled=True, fast_threshold=1.0, decrement=0.02
        )
        bp._last_emit_time = 0.1
        asyncio.run(bp.apply())


class TestGoalExecutionService:
    def test_init_defaults(self):
        svc = GoalExecutionService()
        assert svc.max_stream_events > 0
        assert svc.event_buffer_size > 0

    def test_persist_from_file_filter(self, tmp_path):
        svc = GoalExecutionService()
        f = tmp_path / "events.jsonl"
        lines = '{"type": "ok", "data": 1}\n{"type": "skip", "data": 2}\n'
        f.write_text(lines)

        with patch.dict(os.environ, {"UAR_PERSIST_FILTER": "ok"}):
            with patch("uar.core.replay.run_record_from_events") as m:
                m.return_value = MagicMock(run_id="r1")
                with patch.object(svc._store, "append"):
                    svc._persist_from_file(str(f), MagicMock(), None, "req")
        assert m.called
        events = m.call_args[0][0]
        assert len(events) == 1
        assert events[0]["type"] == "ok"

    def test_persist_from_file_dedup(self, tmp_path):
        svc = GoalExecutionService()
        f = tmp_path / "events.jsonl"
        f.write_text('{"type": "ok", "data": 1}\n{"type": "ok", "data": 1}\n')

        with patch.dict(os.environ, {"UAR_DEDUP_EVENTS": "true"}):
            with patch("uar.core.replay.run_record_from_events") as m:
                m.return_value = MagicMock(run_id="r1")
                with patch.object(svc._store, "append"):
                    svc._persist_from_file(str(f), MagicMock(), None, "req")
        assert m.called
        events = m.call_args[0][0]
        assert len(events) == 1

    def test_persist_from_file_gzip(self, tmp_path):
        import gzip

        svc = GoalExecutionService()
        f = tmp_path / "events.jsonl.gz"
        with gzip.open(f, "wt") as fh:
            fh.write('{"type": "ok", "data": 1}\n')

        with patch("uar.core.replay.run_record_from_events") as m:
            m.return_value = MagicMock(run_id="r1")
            with patch.object(svc._store, "append"):
                svc._persist_from_file(str(f), MagicMock(), None, "req")
        assert m.called

    def test_persist_from_file_json_error(self, tmp_path):
        svc = GoalExecutionService()
        f = tmp_path / "events.jsonl"
        f.write_text("bad json\n")

        with patch("uar.core.replay.run_record_from_events") as m:
            m.return_value = MagicMock(run_id="r1")
            with patch.object(svc._store, "append"):
                svc._persist_from_file(str(f), MagicMock(), None, "req")
        assert m.called
        events = m.call_args[0][0]
        assert len(events) == 0

    def test_persist_from_file_read_error(self, tmp_path):
        svc = GoalExecutionService()
        result = svc._persist_from_file(
            "/nonexistent", MagicMock(), None, "req"
        )
        assert result is None

    def test_persist_async(self, tmp_path):
        import asyncio

        svc = GoalExecutionService()
        f = tmp_path / "events.jsonl"
        f.write_text('{"type": "ok"}\n')

        with patch("uar.core.replay.run_record_from_events") as m:
            m.return_value = MagicMock(run_id="r1")
            with patch.object(svc._store, "append"):
                asyncio.run(
                    svc._persist_async(str(f), MagicMock(), None, "req")
                )
