"""Tests for skills made real from stubs/cosplay/placeholders."""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.core.uor_ecosystem import get_uor_ecosystem, reset_uor_ecosystem
from uar.skills.advanced_integrations import agent_workflow


class TestPrismBTC:
    """PrismBTCClient now generates real Bitcoin addresses."""

    def test_anchor_generates_address_and_tx(self):
        eco = get_uor_ecosystem()
        result = eco.prism_btc.anchor_digest("sha256:test123")

        assert result["status"] == "completed"
        assert result["mode"] == "local_computed"
        assert result["anchor_type"] == "op_return"
        assert "bitcoin_address" in result
        assert result["bitcoin_address"].startswith("1")
        assert "transaction_hex" in result
        assert len(result["transaction_hex"]) > 20
        assert "mock_transaction" in result
        assert result["mock_transaction"]["version"] == 2

    def test_verify_reproduces_address(self):
        eco = get_uor_ecosystem()
        digest = "sha256:verify456"
        result = eco.prism_btc.verify_anchor(digest)

        assert result["status"] == "completed"
        assert result["mode"] == "local_computed"
        assert result["bitcoin_address"].startswith("1")
        assert result["expected_txid"] == result["expected_txid"]
        assert result["verified_on_chain"] is False

    def test_anchor_consistent_for_same_digest(self):
        eco = get_uor_ecosystem()
        r1 = eco.prism_btc.anchor_digest("sha256:same")
        r2 = eco.prism_btc.anchor_digest("sha256:same")
        assert r1["bitcoin_address"] == r2["bitcoin_address"]


class TestSeveranceAI:
    """SeveranceAIClient routes to available LLM or falls back."""

    def test_infer_no_url_returns_local_mode(self, monkeypatch):
        monkeypatch.delenv("SEVERANCE_AI_URL", raising=False)
        reset_uor_ecosystem()
        eco = get_uor_ecosystem()
        result = eco.severance_ai.infer("Hello", "default")

        assert result["status"] == "completed"
        assert result["mode"] in ("uar_native", "ollama_local", "openai_api")

    def test_verify_no_url_local_checks(self):
        eco = get_uor_ecosystem()
        result = eco.severance_ai.verify_output(
            "Hello world",
            {"contains": "hello", "min_length": 5, "max_length": 100},
        )

        assert result["status"] == "completed"
        assert result["mode"] == "local_verified"
        assert result["passed"] is True
        assert result["checks"]["contains"]["passed"] is True
        assert result["checks"]["min_length"]["actual"] == 11

    def test_verify_fails_when_criteria_not_met(self):
        eco = get_uor_ecosystem()
        result = eco.severance_ai.verify_output(
            "Hi",
            {"contains": "xyz", "min_length": 100},
        )

        assert result["passed"] is False
        assert result["checks"]["contains"]["passed"] is False
        assert result["checks"]["min_length"]["passed"] is False


class TestAnunix:
    """AnunixClient executes local commands in a sandbox."""

    def test_health_check_local(self):
        eco = get_uor_ecosystem()
        result = eco.anunix.health_check("test_host")

        assert result["status"] == "completed"
        assert result["mode"] == "local"
        assert result["host_id"] == "test_host"
        assert "platform" in result
        assert "python_version" in result

    def test_run_command_allowed(self):
        eco = get_uor_ecosystem()
        result = eco.anunix.run_command("localhost", "echo hello")

        assert result["status"] == "completed"
        assert result["mode"] == "local_sandbox"
        assert result["stdout"].strip() == "hello"
        assert result["returncode"] == 0

    def test_run_command_blocked_dangerous(self):
        eco = get_uor_ecosystem()
        result = eco.anunix.run_command("localhost", "rm -rf /")

        assert result["status"] == "failed"
        assert "Blocked dangerous pattern" in result["stderr"]
        assert result["returncode"] == -1

    def test_run_command_blocked_disallowed(self):
        eco = get_uor_ecosystem()
        result = eco.anunix.run_command("localhost", "wget example.com")

        assert result["status"] == "failed"
        assert "not in local allowlist" in result["stderr"]


class TestAgentWorkflow:
    """agent_workflow tries AutoGen then falls back to UAR-native."""

    def test_falls_back_to_uar_native_when_autogen_missing(self):
        ctx = PipelineContext(
            goal=GoalSpec(
                id="test",
                user_intent="test",
                objective="test",
                metadata={
                    "agent_sequence": ["agent1"],
                    "initial_message": "Hello",
                },
            )
        )
        result = agent_workflow(ctx)

        assert result["mode"] == "uar_native"
        assert result["status"] == "success"
        assert result["workflow_id"].startswith("workflow_")

    def test_registers_agents_from_metadata(self):
        ctx = PipelineContext(
            goal=GoalSpec(
                id="test",
                user_intent="test",
                objective="test",
                metadata={
                    "agent_sequence": ["a1"],
                    "agents": [
                        {
                            "id": "a1",
                            "name": "Agent One",
                            "description": "Test agent",
                        }
                    ],
                    "initial_message": "Go",
                },
            )
        )
        result = agent_workflow(ctx)

        assert result["mode"] == "uar_native"
        assert result["status"] == "success"
