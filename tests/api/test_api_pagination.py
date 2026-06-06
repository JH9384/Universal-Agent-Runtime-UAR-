"""Tests for uar.api.pagination (E7 — cursor-based list endpoints)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from uar.api.pagination import decode_cursor, encode_cursor, paginate_cursor
from uar.api.server import app

client = TestClient(app)


class TestCursorEncoding:
    def test_roundtrip(self):
        cursor = encode_cursor("run-123", sort_field="run_id")
        decoded = decode_cursor(cursor)
        assert decoded is not None
        assert decoded["last_id"] == "run-123"
        assert decoded["sort"] == "run_id"

    def test_decode_invalid_returns_none(self):
        assert decode_cursor("not-a-cursor") is None
        assert decode_cursor("") is None

    def test_decode_malformed_json_returns_none(self):
        import base64

        bad = base64.urlsafe_b64encode(b"not json").decode().rstrip("=")
        assert decode_cursor(bad) is None


class TestPaginateCursor:
    def test_first_page_no_cursor(self):
        items = [{"run_id": f"r{i}"} for i in range(25)]
        page, next_cursor = paginate_cursor(items, limit=10)
        assert len(page) == 10
        assert page[0]["run_id"] == "r0"
        assert page[-1]["run_id"] == "r9"
        assert next_cursor is not None

    def test_second_page(self):
        items = [{"run_id": f"r{i}"} for i in range(25)]
        _, cursor = paginate_cursor(items, limit=10)
        page2, next_cursor = paginate_cursor(items, cursor=cursor, limit=10)
        assert len(page2) == 10
        assert page2[0]["run_id"] == "r10"
        assert page2[-1]["run_id"] == "r19"
        assert next_cursor is not None

    def test_last_page(self):
        items = [{"run_id": f"r{i}"} for i in range(25)]
        _, c1 = paginate_cursor(items, limit=10)
        _, c2 = paginate_cursor(items, cursor=c1, limit=10)
        page3, next_cursor = paginate_cursor(items, cursor=c2, limit=10)
        assert len(page3) == 5
        assert page3[0]["run_id"] == "r20"
        assert next_cursor is None

    def test_empty_list(self):
        page, next_cursor = paginate_cursor([], limit=10)
        assert page == []
        assert next_cursor is None

    def test_cursor_not_found_starts_from_beginning(self):
        items = [{"run_id": f"r{i}"} for i in range(10)]
        page, next_cursor = paginate_cursor(
            items, cursor=encode_cursor("missing-id"), limit=5
        )
        assert len(page) == 5
        assert page[0]["run_id"] == "r0"

    def test_limit_larger_than_data(self):
        items = [{"run_id": "r1"}]
        page, next_cursor = paginate_cursor(items, limit=100)
        assert len(page) == 1
        assert next_cursor is None


class TestListRunsPagination:
    @pytest.fixture(autouse=True)
    def _seed_runs(self):
        """Seed a few runs via the API so list has data."""
        for i in range(5):
            client.post(
                "/api/uar/run",
                json={
                    "goal": f"test pagination {i}",
                    "skills": ["echo"],
                },
                headers={"Authorization": "Bearer dev-key-12345"},
            )

    def test_list_runs_default_pagination(self):
        resp = client.get(
            "/api/uar/runs",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "items" in data
        assert "total" in data
        assert "next_cursor" in data

    def test_list_runs_with_limit(self):
        resp = client.get(
            "/api/uar/runs?limit=2",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert resp.status_code == 200
        payload = resp.json()["data"]
        assert len(payload["items"]) <= 2
        assert payload["total"] >= 5

    def test_list_runs_bad_limit_rejected(self):
        resp = client.get(
            "/api/uar/runs?limit=999",
            headers={"Authorization": "Bearer dev-key-12345"},
        )
        assert resp.status_code == 422
