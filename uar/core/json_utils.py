"""Shared JSON serialization utilities for UAR.

Provides consistent JSON serialization/deserialization with
error handling and type safety across the codebase.
"""

import importlib.util
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

# Fast serialization: orjson when available (10-100x faster than stdlib)
if importlib.util.find_spec("orjson") is not None:
    import orjson  # type: ignore[import-untyped]

    def fast_dumps(obj: Any) -> str:
        """Serialize to JSON string using orjson if available."""
        return orjson.dumps(obj).decode("utf-8")

    def fast_dumps_bytes(obj: Any) -> bytes:
        """Serialize to JSON bytes using orjson if available."""
        return orjson.dumps(obj)
else:
    def fast_dumps(obj: Any) -> str:
        """Serialize to JSON string using stdlib json."""
        return json.dumps(obj)

    def fast_dumps_bytes(obj: Any) -> bytes:
        """Serialize to JSON bytes using stdlib json."""
        return json.dumps(obj).encode("utf-8")

logger = logging.getLogger(__name__)


def json_load_safely(
    file_path: Path,
    default: Optional[Any] = None,
) -> Any:
    """Load JSON from file with error handling.

    Args:
        file_path: Path to JSON file
        default: Default value to return if file doesn't exist or is invalid

    Returns:
        Parsed JSON data or default value
    """
    if not file_path.exists():
        logger.warning("JSON file not found: %s", file_path)
        return default

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in %s", file_path)
        return default
    except (OSError, TypeError):
        logger.exception("Error reading JSON from %s", file_path)
        return default


def json_dump_safely(
    data: Any,
    file_path: Path,
    sort_keys: bool = False,
    indent: int = 2,
) -> bool:
    """Dump JSON to file with error handling.

    Args:
        data: Data to serialize
        file_path: Path to output file
        sort_keys: Whether to sort dictionary keys
        indent: Indentation level

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create parent directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=sort_keys, indent=indent)
        return True
    except TypeError:
        logger.exception("Data not JSON serializable")
        return False
    except OSError:
        logger.exception("Error writing JSON to %s", file_path)
        return False


def json_loads_safely(
    json_str: str,
    default: Optional[Any] = None,
) -> Any:
    """Parse JSON string with error handling.

    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON data or default value
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON string")
        return default
    except (TypeError, ValueError):
        logger.exception("Error parsing JSON string")
        return default


def json_dumps_safely(
    data: Any,
    sort_keys: bool = False,
    indent: Optional[int] = None,
) -> Optional[str]:
    """Serialize data to JSON string with error handling.

    Args:
        data: Data to serialize
        sort_keys: Whether to sort dictionary keys
        indent: Indentation level (None for compact)

    Returns:
        JSON string or None if serialization fails
    """
    try:
        return json.dumps(data, sort_keys=sort_keys, indent=indent)
    except (TypeError, ValueError):
        logger.exception("Error serializing to JSON")
        return None


def validate_json_structure(
    data: Any,
    required_keys: Optional[list[str]] = None,
    key_types: Optional[Dict[str, type]] = None,
) -> bool:
    """Validate JSON data structure.

    Args:
        data: Data to validate
        required_keys: List of required top-level keys
        key_types: Dictionary mapping keys to expected types

    Returns:
        True if validation passes, False otherwise
    """
    if not isinstance(data, dict):
        return False

    if required_keys:
        for key in required_keys:
            if key not in data:
                logger.warning("Missing required key: %s", key)
                return False

    if key_types:
        for key, expected_type in key_types.items():
            if key in data and not isinstance(data[key], expected_type):
                logger.warning(
                    "Key '%s' has wrong type: expected %s, got %s",
                    key,
                    expected_type,
                    type(data[key]),
                )
                return False

    return True
