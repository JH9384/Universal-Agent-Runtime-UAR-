from uar.core.semantic_trace import DecisionState, directed_transition_risk


def test_directional_risk_is_policy_separate_from_symmetric_divergence():
    risk = {
        (DecisionState.REJECT, DecisionState.ADMIT): 10.0,
        (DecisionState.ADMIT, DecisionState.REJECT): 2.0,
    }

    assert directed_transition_risk(
        DecisionState.REJECT,
        DecisionState.ADMIT,
        risk,
    ) == 10.0
    assert directed_transition_risk(
        DecisionState.ADMIT,
        DecisionState.REJECT,
        risk,
    ) == 2.0
