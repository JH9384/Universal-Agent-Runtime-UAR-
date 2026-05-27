from uar.core.runtime_bootstrap import RuntimeBootstrapPlan
from uar.core.runtime_bootstrap import RuntimeBootstrapStep


def test_runtime_bootstrap_plan_serialization():
    plan = RuntimeBootstrapPlan(environment="local")

    plan.add_step(
        RuntimeBootstrapStep(
            name="start-runtime",
            command="python -m uar.runtime",
        )
    )

    payload = plan.to_dict()

    assert payload["environment"] == "local"
    assert payload["steps"][0]["name"] == "start-runtime"
