import json
from pathlib import Path

from uar.core.evidence_pack_validation_corpus import (
    evaluate_evidence_pack_corpus_document,
)


def test_seed_corpus_is_machine_readable_and_exercises_control():
    path = Path("docs/research/fcrl_v4_seed_corpus.json")
    document = json.loads(path.read_text(encoding="utf-8"))

    result = evaluate_evidence_pack_corpus_document(document)

    assert result.corpus_id == "fcrl-v4-seed-corpus-1"
    assert result.classification_counts == {"exact_reference_reconstruction": 1}
    assert result.certificate_only_obstruction_count >= 1
