import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path("schemas/semantic")


def test_semantic_exchange_schemas_are_valid_draft_2020_12():
    names = {
        "history-corpus.schema.json",
        "history-attestation.schema.json",
        "history-review.schema.json",
        "decision-certificate.schema.json",
    }

    for name in names:
        schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
