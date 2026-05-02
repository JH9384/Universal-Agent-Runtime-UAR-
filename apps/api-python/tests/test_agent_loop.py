from agent_loop import run_section_strategy


def fake_execute_runtime(runtime_name, inputs):
    values = [5, 10]
    if runtime_name == "sum_contents":
        return {"result": sum(values), "output": "sum"}
    if runtime_name == "max_contents":
        return {"result": max(values), "output": "max"}
    if runtime_name == "min_contents":
        return {"result": min(values), "output": "min"}
    return {"result": None}


def test_strategy_maximize():
    section = {
        "label": "Finance",
        "goal": "maximize",
        "input_ids": ["a", "b"],
        "values": [5, 10],
    }

    result = run_section_strategy(
        section=section,
        execute_runtime=fake_execute_runtime,
        record_memory=False,
    )

    assert result["result"] == 15
    assert result["chosen"]["runtime"] == "sum_contents"
