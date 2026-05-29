"""Regression tests for issues found in the May 28 review session."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. executor.py: _cached_expand_execution_order preserves full recipe metadata
# ---------------------------------------------------------------------------

class TestExecutorCachePreservesMetadata:
    def test_cached_expand_preserves_recipe_parameters(self):
        """Recipe parameters must survive cache key round-trip."""
        from uar.core.executor import _cached_expand_execution_order

        execution_order = [
            {"type": "recipe", "content": "review", "id": "r1"},
        ]
        eo_tuple = tuple(
            json.dumps(item, sort_keys=True) for item in execution_order
        )

        # Recipe map with extra metadata beyond just "skills"
        recipe_map = {
            "review": {
                "id": "review",
                "skills": ["doc_ingest", "ollama_generate"],
                "parameters": {"temperature": 0.7},
                "condition": {"key": "input_path", "exists": True},
                "max_retries": 5,
            }
        }
        rm_tuple = tuple(
            sorted(
                (
                    k,
                    json.dumps(v, sort_keys=True, default=str),
                )
                for k, v in recipe_map.items()
            )
        )

        skills, markers = _cached_expand_execution_order(eo_tuple, rm_tuple)
        assert skills == ["doc_ingest", "ollama_generate"]
        assert len(markers) == 2  # start + end
        start_marker = markers[0]
        assert start_marker["kind"] == "start"
        # The key fix: recipe parameters and condition must survive
        # cache-key round-trip (they were previously stripped).
        assert start_marker.get("parameters") == {"temperature": 0.7}
        assert start_marker.get("condition") == {
            "key": "input_path", "exists": True
        }

    def test_cache_key_distinct_for_different_parameters(self):
        """Two recipe maps with same skills but different params must
        NOT collide."""
        from uar.core.executor import _cached_expand_execution_order

        eo = [{"type": "recipe", "content": "review", "id": "r1"}]
        eo_tuple = tuple(json.dumps(i, sort_keys=True) for i in eo)

        rm1 = {
            "review": {
                "id": "review",
                "skills": ["doc_ingest"],
                "parameters": {"temp": 0.5},
            }
        }
        rm2 = {
            "review": {
                "id": "review",
                "skills": ["doc_ingest"],
                "parameters": {"temp": 0.9},
            }
        }

        rm_tuple_1 = tuple(
            sorted(
                (k, json.dumps(v, sort_keys=True, default=str))
                for k, v in rm1.items()
            )
        )
        rm_tuple_2 = tuple(
            sorted(
                (k, json.dumps(v, sort_keys=True, default=str))
                for k, v in rm2.items()
            )
        )

        # Cache keys must be different
        assert rm_tuple_1 != rm_tuple_2

        _, markers1 = _cached_expand_execution_order(eo_tuple, rm_tuple_1)
        _, markers2 = _cached_expand_execution_order(eo_tuple, rm_tuple_2)
        assert markers1[0]["parameters"]["temp"] == 0.5
        assert markers2[0]["parameters"]["temp"] == 0.9


# ---------------------------------------------------------------------------
# 2. code_analysis.py: _has_real_comment handles string literals
# ---------------------------------------------------------------------------

class TestHasRealComment:
    def test_hash_inside_string_is_not_comment(self):
        from uar.skills.code_analysis import _has_real_comment

        assert not _has_real_comment('x = "hello # world"', "#")

    def test_double_slash_inside_string_is_not_comment(self):
        from uar.skills.code_analysis import _has_real_comment

        assert not _has_real_comment('url = "http://example.com"', "//")

    def test_real_comment_outside_string(self):
        from uar.skills.code_analysis import _has_real_comment

        assert _has_real_comment('x = 1  # real comment', "#")
        assert _has_real_comment('x = 1 // real comment', "//")

    def test_escaped_quote_does_not_end_string(self):
        from uar.skills.code_analysis import _has_real_comment

        # \" inside a double-quoted string is an escaped quote,
        # not a terminator. The string still ends at the final ".
        line = 'x = "say \\"hello\\"" # comment'
        # After the string ends, the # IS a real comment
        assert _has_real_comment(line, "#")
        # A # inside an unclosed string is not a comment
        assert not _has_real_comment('x = "hi # there', "#")

    def test_single_quoted_string_blocks_hash(self):
        from uar.skills.code_analysis import _has_real_comment

        assert not _has_real_comment("x = 'a # b'", "#")

    def test_block_comment_outside_string(self):
        from uar.skills.code_analysis import _has_real_comment

        assert _has_real_comment("int x; /* block start", "/*")
        assert not _has_real_comment('x = "/* not a comment */"', "/*")


class TestCountLinesIgnoresStringContents:
    def test_line_with_hash_inside_string_not_counted_as_comment(self):
        from uar.skills.code_analysis import _count_lines

        source = 'x = "hello # world"\ny = 2\n'
        result = _count_lines(source)
        assert result["comment"] == 0
        assert result["code"] == 2

    def test_line_with_double_slash_inside_string_not_counted(self):
        from uar.skills.code_analysis import _count_lines

        source = 'url = "http://example.com"\n'
        result = _count_lines(source)
        assert result["comment"] == 0

    def test_real_inline_comment_still_counted(self):
        from uar.skills.code_analysis import _count_lines

        source = 'x = 1  # comment\n'
        result = _count_lines(source)
        assert result["comment"] == 1
        assert result["code"] == 0

    def test_block_comment_outside_string(self):
        from uar.skills.code_analysis import _count_lines

        source = 'int x = 1; /* start\ncomment line\nend */ int y = 2;\n'
        result = _count_lines(source)
        # line 1: starts block (comment)
        # line 2: inside block (comment)
        # line 3: still inside block when checked, so comment
        assert result["comment"] == 3
        assert result["code"] == 0


# ---------------------------------------------------------------------------
# 3. docs.py: _require_auth_or_dev treats invalid key as anonymous in dev
# ---------------------------------------------------------------------------

class TestRequireAuthOrDevInvalidKey:
    """Invalid API keys in dev mode must be treated as anonymous."""

    @pytest.fixture
    def dev_env(self, tmp_path):
        env = {"ENVIRONMENT": "development", "PROJECT_ROOT": str(tmp_path)}
        with patch.dict(os.environ, env, clear=False):
            yield

    @pytest.fixture
    def api_keys(self):
        with patch.dict(
            "uar.api.middleware.API_KEYS",
            {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
            clear=True,
        ):
            yield

    @pytest.mark.usefixtures("dev_env", "api_keys")
    def test_invalid_key_in_dev_is_anonymous(self):
        """GET /api/uar/docs/browse with bad key in dev → 200
        (not 401)."""
        response = client.get(
            "/api/uar/docs/browse?path=.",
            headers={"Authorization": "Bearer bad-key"},
        )
        # Should succeed, not 401
        assert response.status_code == 200
