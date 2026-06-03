"""Regression tests for alert_tracker silent-exception fixes.

Covers:
  FIX-AT-1  _persist_event logs store failures instead of silent pass
  FIX-AT-2  _load_event logs store failures instead of silent pass
  FIX-AT-3  _load_all_events logs corrupt JSON and list_meta_keys failures
"""

import logging

from uar.api.alert_tracker import AlertTracker


class FakeStore:
    """Store that raises on every operation to test fallback paths."""

    def __init__(self, exc: Exception = RuntimeError("boom")):
        self.exc = exc

    def put_metadata(self, key: str, value: str) -> None:
        raise self.exc

    def get_metadata(self, key: str) -> str:
        raise self.exc

    def list_meta_keys(self):
        raise self.exc


class BrokenJsonStore:
    """Store that returns invalid JSON so json.loads fails."""

    def list_meta_keys(self):
        return ["alert_tracker:test"]

    def get_metadata(self, key: str) -> str:
        return "not-json{{"


def test_persist_event_falls_back_to_memory_on_store_failure(caplog):
    """_persist_event must keep event in memory even when store fails."""
    caplog.set_level(logging.DEBUG, logger="uar.api.alert_tracker")
    tracker = AlertTracker(store=FakeStore())
    tracker.record_fired("type", "high", "msg")
    assert len(tracker._pending) == 1
    assert tracker._pending[0]["message"] == "msg"
    assert "store persist failed" in caplog.text


def test_load_event_falls_back_to_memory_on_store_failure(caplog):
    """_load_event must fall back to in-memory list when store fails."""
    caplog.set_level(logging.DEBUG, logger="uar.api.alert_tracker")
    tracker = AlertTracker(store=FakeStore())
    alert_id = tracker.record_fired("type", "high", "msg")
    # Clear memory to force store read, which will fail
    tracker._pending.clear()
    result = tracker.record_action(alert_id, "acted")
    assert result is False  # store failed, nothing in memory
    assert "store load failed" in caplog.text


def test_load_all_events_logs_corrupt_json(caplog):
    """_load_all_events must log corrupt JSON instead of silent pass."""
    caplog.set_level(logging.DEBUG, logger="uar.api.alert_tracker")
    tracker = AlertTracker(store=BrokenJsonStore())
    events = tracker._load_all_events()
    assert events == []
    assert "corrupt alert JSON" in caplog.text


def test_load_all_events_logs_list_meta_keys_failure(caplog):
    """_load_all_events must log list_meta_keys failure."""
    caplog.set_level(logging.DEBUG, logger="uar.api.alert_tracker")
    tracker = AlertTracker(store=FakeStore())
    events = tracker._load_all_events()
    assert events == []
    assert "list_meta_keys failed" in caplog.text
