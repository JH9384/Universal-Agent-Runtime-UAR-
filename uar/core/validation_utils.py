"""Shared validation utilities for UAR.

Provides common validation functions used across multiple modules
to reduce code duplication and ensure consistent validation logic.
"""

import re
from typing import Any, Optional, List
from .exceptions import ValidationError


def validate_string_field(
    value: Any,
    field_name: str,
    min_length: int = 0,
    max_length: Optional[int] = None,
    allow_empty: bool = False,
) -> str:
    """Validate a string field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length (default: 0)
        max_length: Maximum allowed length (default: None)
        allow_empty: Whether empty strings are allowed (default: False)

    Returns:
        Validated string value

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string", field=field_name
        )

    if not allow_empty and not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty", field=field_name
        )

    if len(value) < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters",
            field=field_name,
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            field=field_name,
        )

    return value


def validate_positive_number(
    value: Any,
    field_name: str,
    min_value: float = 0.0,
    max_value: Optional[float] = None,
) -> float:
    """Validate a positive numeric field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value (default: 0.0)
        max_value: Maximum allowed value (default: None)

    Returns:
        Validated numeric value

    Raises:
        ValidationError: If validation fails
    """
    try:
        num_value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(
            f"{field_name} must be a number", field=field_name
        ) from None

    if num_value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}", field=field_name
        )

    if max_value is not None and num_value > max_value:
        raise ValidationError(
            f"{field_name} must be at most {max_value}", field=field_name
        )

    return num_value


def validate_list_field(
    value: Any,
    field_name: str,
    min_items: int = 0,
    max_items: Optional[int] = None,
    item_type: Optional[type] = None,
) -> List[Any]:
    """Validate a list field.

    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_items: Minimum number of items (default: 0)
        max_items: Maximum number of items (default: None)
        item_type: Expected type of list items (default: None)

    Returns:
        Validated list

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be a list", field=field_name)

    if len(value) < min_items:
        raise ValidationError(
            f"{field_name} must have at least {min_items} items",
            field=field_name,
        )

    if max_items is not None and len(value) > max_items:
        raise ValidationError(
            f"{field_name} must have at most {max_items} items",
            field=field_name,
        )

    if item_type is not None:
        for i, item in enumerate(value):
            if not isinstance(item, item_type):
                raise ValidationError(
                    f"{field_name}[{i}] must be of type {item_type.__name__}",
                    field=field_name,
                )

    return value


def validate_email(email: str, field_name: str = "email") -> str:
    """Validate an email address.

    Args:
        email: Email address to validate
        field_name: Name of the field for error messages

    Returns:
        Validated email address

    Raises:
        ValidationError: If validation fails
    """
    email_pattern = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    if not email_pattern.match(email):
        raise ValidationError(
            f"{field_name} must be a valid email address", field=field_name
        )

    return email


def validate_url(url: str, field_name: str = "url") -> str:
    """Validate a URL.

    Args:
        url: URL to validate
        field_name: Name of the field for error messages

    Returns:
        Validated URL

    Raises:
        ValidationError: If validation fails
    """
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # noqa
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    if not url_pattern.match(url):
        raise ValidationError(
            f"{field_name} must be a valid URL", field=field_name
        )

    return url
