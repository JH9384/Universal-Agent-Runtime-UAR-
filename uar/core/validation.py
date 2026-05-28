"""Input validation utilities for UAR"""

import re
from pathlib import Path
from typing import List, Optional

from .exceptions import ValidationError, PathSecurityError

# Constants
MIN_GOAL_LENGTH = 3
MAX_GOAL_LENGTH = 10000
MAX_SKILLS = 20
MAX_SKILL_NAME_LENGTH = 100
DEFAULT_TIMEOUT_SECONDS = 5.0
MIN_TIMEOUT_SECONDS = 0.1  # Minimum 100ms to prevent zero timeout
MAX_TIMEOUT_SECONDS = 300  # 5 minutes

# Compiled regex cache for frequently-used patterns
_DANGEROUS_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"data:text/html", re.IGNORECASE),
    re.compile(r"<[^>]+on\w+\s*=", re.IGNORECASE),
    re.compile(r"alert\s*\(", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
]
_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_goal(goal: str) -> str:
    """Validate goal input"""
    if not goal:
        raise ValidationError("Goal cannot be empty", field="goal")

    if not isinstance(goal, str):
        raise ValidationError("Goal must be a string", field="goal")

    goal = goal.strip()
    if not goal:
        raise ValidationError("Goal cannot be empty", field="goal")

    if len(goal) < MIN_GOAL_LENGTH:
        raise ValidationError(
            f"Goal must be at least {MIN_GOAL_LENGTH} characters long",
            field="goal",
        )

    if len(goal) > MAX_GOAL_LENGTH:
        raise ValidationError(
            f"Goal cannot exceed {MAX_GOAL_LENGTH:,} characters", field="goal"
        )

    # Check for potentially dangerous content (compiled regex cache)
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(goal):
            raise ValidationError(
                "Goal contains potentially dangerous content", field="goal"
            )

    return goal


def validate_skills(skills: Optional[List[str]]) -> List[str]:
    """Validate skills list"""
    if skills is None:
        return []

    if not isinstance(skills, list):
        raise ValidationError("Skills must be a list", field="skills")

    if len(skills) > MAX_SKILLS:
        raise ValidationError(
            f"Cannot specify more than {MAX_SKILLS} skills", field="skills"
        )

    validated_skills = []
    for skill in skills:
        if not isinstance(skill, str):
            raise ValidationError(
                "Each skill must be a string", field="skills"
            )

        skill = skill.strip()
        if not skill:
            raise ValidationError(
                "Skill names cannot be empty", field="skills"
            )

        if len(skill) > MAX_SKILL_NAME_LENGTH:
            raise ValidationError(
                f"Skill name cannot exceed {MAX_SKILL_NAME_LENGTH} characters",
                field="skills",
            )

        # Validate skill name format (alphanumeric, underscores, hyphens)
        if not _SKILL_NAME_RE.match(skill):
            raise ValidationError(
                f"Skill name '{skill}' contains invalid characters. "
                "Only letters, numbers, underscores, and hyphens are allowed.",
                field="skills",
            )

        validated_skills.append(skill)

    return validated_skills


def validate_input_path(
    input_path: Optional[str], allowed_root: Optional[Path] = None
) -> Optional[str]:
    """Validate input path for security with comprehensive checks."""
    if input_path is None:
        return None

    if not isinstance(input_path, str):
        raise ValidationError(
            "Input path must be a string", field="input_path"
        )

    input_path = input_path.strip()
    if not input_path:
        raise ValidationError("Input path cannot be empty", field="input_path")

    # Check for null bytes (common attack vector)
    if "\x00" in input_path:
        raise ValidationError("Path contains null bytes", field="input_path")

    # Check for path traversal attempts (POSIX, Windows, and obfuscated)
    lowered = input_path.lower()
    normalized_path = Path(input_path).as_posix()
    parts = normalized_path.split("/")
    # Consolidated traversal check - covers all variants
    if (
        ".." in parts
        or "/./" in normalized_path
        or "..\\" in input_path
        or "\\.." in input_path
        or "...." in input_path  # e.g. ....// traversal obfuscation
        or "%2e" in lowered  # URL-encoded '.'
        or "%2f" in lowered
        or "%5c" in lowered  # URL-encoded separators
    ):
        raise ValidationError("Path traversal not allowed", field="input_path")

    # Check for absolute paths — allow only if contained within allowed_root
    if Path(input_path).is_absolute():
        if allowed_root:
            try:
                validate_path_security(Path(input_path), allowed_root)
                return input_path
            except PathSecurityError as exc:
                raise ValidationError(
                    "Absolute path outside allowed root", field="input_path"
                ) from exc
        raise ValidationError("Absolute paths not allowed", field="input_path")

    # Check for dangerous shell/path characters
    # Note: Parent directory traversal (..) is already checked above
    dangerous_patterns = [
        r"^~/",  # Home directory expansion (anchored at start)
        r"^/",   # Root directory (anchored at start)
        r"\|",   # Pipe character
        r";",    # Command separator
        r"&",    # Background process
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, input_path):
            raise ValidationError(
                "Invalid path pattern detected", field="input_path"
            )

    # Additional security check: validate against allowed root if provided
    if allowed_root:
        full_path = allowed_root / input_path
        try:
            validate_path_security(full_path, allowed_root)
        except PathSecurityError as exc:
            raise ValidationError(str(exc), field="input_path") from exc

    return input_path


def validate_path_security(path: Path, allowed_root: Path) -> None:
    """Validate path is within allowed bounds with comprehensive checks."""
    try:
        # Resolve to absolute paths first
        resolved_path = path.resolve()
        resolved_root = allowed_root.resolve()

        # Strict check: path must be within allowed root
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            raise PathSecurityError(
                str(path), "Path outside allowed root"
            ) from None

        # Check for symlinks at any point in the path chain
        # Check every component from root to target
        current = resolved_root
        for part in resolved_path.parts[len(resolved_root.parts):]:
            current = current / part
            if current.is_symlink():
                raise PathSecurityError(
                    str(path), f"Symlink detected in path: {current}"
                )

        # Direct symlink check for the target itself
        if path.is_symlink():
            raise PathSecurityError(str(path), "Symlinks are not allowed")

        # Ensure we can stat the path when it exists (sanity check only).
        # Note: hard links cannot cross filesystems, so a cross-device check is
        # not a meaningful defense and was removed because it rejected
        # legitimate deployments where RUNS_DIR / inputs live on a different
        # mount than PROJECT_ROOT.
        if path.exists():
            try:
                path.stat()
            except OSError:
                raise PathSecurityError(
                    str(path), "Cannot verify path security"
                ) from None

        # Check for potentially dangerous path patterns
        dangerous_patterns = [
            "..",  # Parent directory reference
            "~",  # Home directory expansion
            "$",  # Environment variable expansion attempt
        ]

        path_str = str(path)
        for pattern in dangerous_patterns:
            if pattern in path_str:
                raise PathSecurityError(
                    str(path), f"Dangerous pattern detected: {pattern}"
                )

    except PathSecurityError:
        raise
    except Exception as e:
        raise PathSecurityError(
            str(path), "Path validation failed"
        ) from e


def validate_timeout(timeout_seconds: Optional[float]) -> float:
    """Validate timeout value"""
    if timeout_seconds is None:
        return DEFAULT_TIMEOUT_SECONDS  # Default timeout

    if not isinstance(timeout_seconds, (int, float)):
        raise ValidationError(
            "Timeout must be a number", field="timeout_seconds"
        )

    if timeout_seconds < MIN_TIMEOUT_SECONDS:
        raise ValidationError(
            f"Timeout must be at least {MIN_TIMEOUT_SECONDS} seconds",
            field="timeout_seconds",
        )

    if timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValidationError(
            f"Timeout cannot exceed {MAX_TIMEOUT_SECONDS} seconds",
            field="timeout_seconds",
        )

    return float(timeout_seconds)
