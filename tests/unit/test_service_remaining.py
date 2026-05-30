"""Tests for uar.objects.service remaining coverage gaps."""

from unittest.mock import MagicMock, patch

import pytest

from uar.objects import SandboxError
from uar.objects.service import (
    bridge_ingest,
    constraint_check,
    delegation_plan,
    execute_runtime,
    extract_runtime_code,
    inference_analyze,
    locator_query,
    object_value,
    resolve_runtime,
    seed_standard_runtimes,
    workflow_run,
)


def _make_store():
    store = MagicMock()
    store.get_object.return_value = {
        "digest": "sha256:test",
        "attributes": {},
        "content": {"code": "1+1"},
    }
    store.get_runtime_digest.return_value = "sha256:rt"
    store.iter_objects.return_value = [
        ("sha256:a", {
            "mediaType": "text/plain",
            "mode": "immutable",
            "attributes": {"name": "a"},
        }),
    ]
    store.list_runtimes.return_value = {}
    return store


class TestExtractRuntimeCode:
    def test_string_content(self):
        obj = {"content": "print(1)"}
        assert extract_runtime_code(obj) == "print(1)"

    def test_dict_content(self):
        obj = {"content": {"code": "print(1)"}}
        assert extract_runtime_code(obj) == "print(1)"

    def test_invalid_content(self):
        obj = {"content": 123}
        with pytest.raises(SandboxError):
            extract_runtime_code(obj)


class TestResolveRuntime:
    def test_by_name(self):
        store = _make_store()
        digest, obj = resolve_runtime(store, "py", None)
        assert digest == "sha256:rt"

    def test_by_object(self):
        store = _make_store()
        digest, obj = resolve_runtime(store, None, "sha256:obj")
        assert digest == "sha256:obj"

    def test_none_raises(self):
        store = _make_store()
        with pytest.raises(SandboxError):
            resolve_runtime(store, None, None)


class TestObjectValue:
    def test_plain_content(self):
        obj = {"content": {"result": 42}}
        assert object_value(obj) == 42

    def test_non_dict(self):
        obj = {"content": "hello"}
        assert object_value(obj) == "hello"

    def test_result_wrapper(self):
        obj = {"content": {"result": 42, "extra": 1}}
        assert object_value(obj) == {"result": 42, "extra": 1}


class TestLocatorQuery:
    def test_match(self):
        store = _make_store()
        matches = locator_query(store, {"attributes.name": "a"}, 10)
        assert len(matches) == 1

    def test_no_match(self):
        store = _make_store()
        matches = locator_query(store, {"attributes.name": "b"}, 10)
        assert len(matches) == 0

    def test_limit(self):
        store = _make_store()
        matches = locator_query(store, {}, 0)
        assert len(matches) == 0


class TestConstraintCheck:
    def test_allowed(self):
        store = _make_store()
        from uar.objects.agents import AGENTS
        agent = list(AGENTS.keys())[0]
        action = AGENTS[agent][0]
        result = constraint_check(
            store, agent=agent, action=action, target="sha256:test"
        )
        assert result["allowed"] is True

    def test_not_found(self):
        store = MagicMock()
        store.get_object.side_effect = KeyError("missing")
        with pytest.raises(KeyError):
            constraint_check(store, agent="a", action="read", target="t")


class TestBridgeIngest:
    def test_basic(self):
        store = _make_store()
        result = bridge_ingest(
            store, source={"uri": "s"}, normalize=True, attributes={}
        )
        assert "object" in result


class TestInferenceAnalyze:
    def test_basic(self):
        store = _make_store()
        result = inference_analyze(
            store, objects=["sha256:test"], task="analyze"
        )
        assert "analysisRecord" in result


class TestDelegationPlan:
    def test_basic(self):
        store = _make_store()
        result = delegation_plan(
            store, goal="g", inputs=["sha256:test"], allowed_agents=[]
        )
        assert "plan" in result


class TestExecuteRuntime:
    def test_with_parameters_code(self):
        store = _make_store()
        with patch("uar.objects.service.run_code") as mock_run:
            mock_run.return_value = {"status": "ok"}
            result = execute_runtime(
                store,
                runtime_name=None,
                runtime_object=None,
                inputs=[],
                parameters={"code": "1+1"},
            )
        assert result["status"] == "completed"

    def test_with_runtime(self):
        store = _make_store()
        with patch("uar.objects.service.run_code") as mock_run:
            mock_run.return_value = {"status": "ok"}
            result = execute_runtime(
                store,
                runtime_name="py",
                runtime_object=None,
                inputs=[],
                parameters={},
            )
        assert result["status"] == "completed"


class TestWorkflowRun:
    def test_basic(self):
        store = _make_store()
        with patch("uar.objects.service.execute_runtime") as mock_exec:
            mock_exec.return_value = {
                "status": "completed",
                "output": "sha256:out",
            }
            result = workflow_run(
                store,
                name="wf",
                inputs=["sha256:a"],
                steps=[{"parameters": {}}],
            )
        assert result["status"] == "completed"

    def test_empty_steps_raises(self):
        store = _make_store()
        with pytest.raises(SandboxError):
            workflow_run(store, name="wf", inputs=[], steps=[])

    def test_use_previous_false(self):
        store = _make_store()
        with patch("uar.objects.service.execute_runtime") as mock_exec:
            mock_exec.return_value = {
                "status": "completed",
                "output": "sha256:out",
            }
            result = workflow_run(
                store,
                name="wf",
                inputs=["sha256:a"],
                steps=[{"usePreviousOutput": False, "parameters": {}}],
            )
        assert result["status"] == "completed"


class TestSeedStandardRuntimes:
    def test_already_present(self):
        store = _make_store()
        store.get_runtime_digest.return_value = "sha256:existing"
        result = seed_standard_runtimes(store)
        assert isinstance(result, dict)
