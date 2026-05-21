"""UOR schema validation.

Provides schema validation for UOR objects using JSON Schema and
UOR Foundation ontology when available.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class UORSchemaValidator:
    """Validator for UOR object schemas."""

    UOR_FOUNDATION_REPO = "https://github.com/UOR-Foundation/UOR-Framework"
    UOR_FOUNDATION_SCHEMA_URL = (
        "https://raw.githubusercontent.com/UOR-Foundation/"
        "UOR-Framework/main/schemas/uor.foundation.schema.json"
    )

    def __init__(self, schema_dir: Optional[str] = None):
        """Initialize the UOR schema validator.

        Args:
            schema_dir: Optional directory path to load schemas from
        """
        self.schemas: Dict[str, Dict] = {}
        self.schema_dir = schema_dir
        self._load_builtin_schemas()
        if schema_dir:
            self._load_schemas_from_directory(schema_dir)

    def _load_builtin_schemas(self):
        """Load built-in UAR-specific schemas."""
        # UOR object envelope schema
        self.schemas["uor.schema.object.v1"] = {
            "type": "object",
            "required": ["digest", "mediaType", "mode", "schema", "content"],
            "properties": {
                "digest": {
                    "type": "string",
                    "pattern": "^sha256:[a-f0-9]{64}$",
                },
                "mediaType": {"type": "string"},
                "mode": {
                    "enum": [
                        "immutable_singular",
                        "mutable_singular",
                        "mutable_array",
                    ]
                },
                "schema": {"type": "string"},
                "attributes": {"type": "object"},
                "links": {"type": "array", "items": {"type": "object"}},
                "content": {},
            },
        }

        # Execution record schema
        self.schemas["uar.schema.execution_record.v1"] = {
            "type": "object",
            "required": [
                "execution_id",
                "skill",
                "input_digest",
                "output_digest",
            ],
            "properties": {
                "execution_id": {"type": "string"},
                "skill": {"type": "string"},
                "input_digest": {"type": "string"},
                "output_digest": {"type": "string"},
                "timestamp": {"type": "string"},
                "duration_ms": {"type": "number"},
                "status": {"enum": ["success", "failure", "timeout"]},
                "metadata": {"type": "object"},
                "error": {"type": "string"},
            },
        }

    def _load_schemas_from_directory(self, schema_dir: str):
        """Load schemas from a directory.

        Args:
            schema_dir: Directory path containing JSON schema files
        """
        schema_path = Path(schema_dir)
        if not schema_path.exists():
            logger.warning(f"Schema directory not found: {schema_dir}")
            return

        for schema_file in schema_path.glob("*.json"):
            try:
                with open(schema_file, "r") as f:
                    schema = json.load(f)
                    schema_name = schema_file.stem
                    self.schemas[schema_name] = schema
                    logger.info(f"Loaded schema from file: {schema_file}")
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")

    def load_uor_foundation_schema(self):
        """Load UOR Foundation schema from remote repository.

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            import urllib.request

            url = self.UOR_FOUNDATION_SCHEMA_URL
            with urllib.request.urlopen(url) as response:
                schema = json.loads(response.read().decode())
                self.schemas["uor.foundation.schema"] = schema
                logger.info("Loaded UOR Foundation schema from remote")
                return True
        except Exception as e:
            logger.warning(f"Failed to load UOR Foundation schema: {e}")
            return False

    def load_schema(self, schema_name: str, schema: Dict) -> None:
        """Load a custom schema.

        Args:
            schema_name: Name/identifier for the schema
            schema: JSON Schema dictionary
        """
        self.schemas[schema_name] = schema
        logger.info(f"Loaded schema: {schema_name}")

    def validate(
        self, obj: Dict, schema_name: str = "uor.schema.object.v1"
    ) -> tuple[bool, List[str]]:
        """Validate object against schema.

        Args:
            obj: Object to validate
            schema_name: Schema to validate against

        Returns:
            Tuple of (is_valid, error_messages)
        """
        if schema_name not in self.schemas:
            return False, [f"Schema not found: {schema_name}"]

        schema = self.schemas[schema_name]
        errors = []

        # Basic validation
        if "required" in schema:
            for field in schema["required"]:
                if field not in obj:
                    errors.append(f"Missing required field: {field}")

        if "properties" in schema:
            for field, field_schema in schema["properties"].items():
                if field in obj:
                    value = obj[field]
                    if "type" in field_schema:
                        expected_type = field_schema["type"]
                        if not self._check_type(value, expected_type):
                            errors.append(
                                f"Field '{field}' has wrong type: "
                                f"expected {expected_type}, got {type(value).__name__}"  # noqa: E501
                            )

                    if "pattern" in field_schema and isinstance(value, str):
                        import re

                        if not re.match(field_schema["pattern"], value):
                            errors.append(
                                f"Field '{field}' does not match pattern: "
                                f"{field_schema['pattern']}"
                            )

                    if "enum" in field_schema:
                        if value not in field_schema["enum"]:
                            enum_vals = field_schema["enum"]
                            errors.append(
                                f"Field '{field}' has invalid value: "
                                f"{value} not in {enum_vals}"
                            )

        return len(errors) == 0, errors

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type.

        Args:
            value: Value to check
            expected_type: Expected type string

        Returns:
            True if type matches
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }

        python_type = type_map.get(expected_type, object)
        if python_type is object:
            return True
        return isinstance(value, python_type)  # type: ignore[arg-type]

    def validate_envelope(self, envelope: Dict) -> tuple[bool, List[str]]:
        """Validate UOR object envelope.

        Args:
            envelope: UOR envelope dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        return self.validate(envelope, "uor.schema.object.v1")

    def validate_execution_record(
        self, record: Dict
    ) -> tuple[bool, List[str]]:
        """Validate execution record.

        Args:
            record: Execution record dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        return self.validate(record, "uar.schema.execution_record.v1")

    def get_available_schemas(self) -> List[str]:
        """Get list of available schema names.

        Returns:
            List of schema names
        """
        return list(self.schemas.keys())
