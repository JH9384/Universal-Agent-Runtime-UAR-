from uar.core.replay_certificate import ReplayCertificate


def test_replay_certificate_hash_stability():
    certificate = ReplayCertificate(
        replay_id="replay-001",
        topology_hash="topology",
        semantic_hash="semantic",
        governance_hash="governance",
    )

    first_hash = certificate.certificate_hash
    second_hash = certificate.certificate_hash

    assert first_hash == second_hash
    assert len(first_hash) == 64
