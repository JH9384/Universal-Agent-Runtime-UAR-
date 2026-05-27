from pathlib import Path

from uar.core.replay_certificate import ReplayCertificate
from uar.core.runtime_replay_store import RuntimeReplayStore


def test_runtime_replay_store_initialization(tmp_path: Path):
    database_path = tmp_path / "runtime.db"

    store = RuntimeReplayStore(str(database_path))
    store.initialize()

    assert database_path.exists()


def test_runtime_replay_store_insert_certificate(tmp_path: Path):
    database_path = tmp_path / "runtime.db"

    store = RuntimeReplayStore(str(database_path))
    store.initialize()

    certificate = ReplayCertificate(
        replay_id="replay-001",
        topology_hash="topology",
        semantic_hash="semantic",
        governance_hash="governance",
    )

    store.insert_certificate(certificate)

    assert database_path.exists()
