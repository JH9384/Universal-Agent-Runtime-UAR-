from uar.continuity.state_convergence import ContinuityStateConvergence


def test_continuity_state_convergence() -> None:
    convergence = ContinuityStateConvergence().converge(
        state_id='fabric-1',
        domains=['replay', 'topology', 'governance'],
    )

    payload = convergence.to_dict()

    assert payload['convergence_score'] > 0.0
    assert len(payload['participating_domains']) == 3
