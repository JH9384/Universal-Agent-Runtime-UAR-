"""Input validation utilities for UAR"""

import re
from pathlib import Path
from typing import List, Optional

from .exceptions import ValidationError, PathSecurityError


def validate_goal(goal: str) -> str:
    """Validate goal input"""
    if not goal:
        raise ValidationError("Goal cannot be empty", field="goal")
    
    if not isinstance(goal, str):
        raise ValidationError("Goal must be a string", field="goal")
    
    goal = goal.strip()
    if len(goal) < 3:
        raise ValidationError("Goal must be at least 3 characters long", field="goal")
    
    if len(goal) > 10000:
        raise ValidationError("Goal cannot exceed 10,000 characters", field="goal")
    
    # Check for potentially dangerous content
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'data:text/html',  # Data URLs
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, goal, re.IGNORECASE):
            raise ValidationError("Goal contains potentially dangerous content", field="goal")
    
    return goal


def validate_skills(skills: Optional[List[str]]) -> List[str]:
    """Validate skills list"""
    if skills is None:
        return []
    
    if not isinstance(skills, list):
        raise ValidationError("Skills must be a list", field="skills")
    
    if len(skills) > 20:
        raise ValidationError("Cannot specify more than 20 skills", field="skills")
    
    validated_skills = []
    for skill in skills:
        if not isinstance(skill, str):
            raise ValidationError("Each skill must be a string", field="skills")
        
        skill = skill.strip()
        if not skill:
            raise ValidationError("Skill names cannot be empty", field="skills")
        
        if len(skill) > 100:
            raise ValidationError("Skill name cannot exceed 100 characters", field="skills")
        
        # Validate skill name format (alphanumeric, underscores, hyphens)
        if not re.match(r'^[a-zA-Z0-9_-]+$', skill):
            raise ValidationError(
                f"Skill name '{skill}' contains invalid characters. "
                "Only letters, numbers, underscores, and hyphens are allowed.",
                field="skills"
            )
        
        validated_skills.append(skill)
    
    return validated_skills


def validate_input_path(input_path: Optional[str]) -> Optional[str]:
    """Validate input path for security"""
    if input_path is None:
        return None
    
    if not isinstance(input_path, str):
        raise ValidationError("Input path must be a string", field="input_path")
    
    input_path = input_path.strip()
    if not input_path:
        raise ValidationError("Input path cannot be empty", field="input_path")
    
    # Check for path traversal attempts
    if '..' in input_path:
        raise ValidationError("Path traversal not allowed", field="input_path")
    
    # Check for absolute paths (should be relative to project root)
    if Path(input_path).is_absolute():
        raise ValidationError("Absolute paths not allowed", field="input_path")
    
    # Check for dangerous patterns
    dangerous_patterns = [
        r'~/',  # Home directory
        r'^/',  # Root directory
        r'\.\./',  # Parent directory
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, input_path):
            raise ValidationError("Invalid path pattern detected", field="input_path")
    
    return input_path


def validate_path_security(path: Path, allowed_root: Path) -> None:
    """Validate that a path is within allowed bounds"""
    try:
        resolved_path = path.resolve()
        resolved_root = allowed_root.resolve()
        
        # Check if path is within allowed root
        resolved_path.relative_to(resolved_root)
        
        # Additional check for symlinks
        if path.is_symlink():
            raise PathSecurityError(str(path), "Symlinks are not allowed")
            
    except ValueError as e:
        raise PathSecurityError(str(path), "Path outside allowed root") from e
    except Exception as e:
        raise PathSecurityError(str(path), f"Path validation failed: {str(e)}") from e


def validate_timeout(timeout_seconds: Optional[float]) -> float:
    """Validate timeout value"""
    if timeout_seconds is None:
        return 5.0  # Default timeout
    
    if not isinstance(timeout_seconds, (int, float)):
        raise ValidationError("Timeout must be a number", field="timeout_seconds")
    
    if timeout_seconds <= 0:
        raise ValidationError("Timeout must be positive", field="timeout_seconds")
    
    if timeout_seconds > 300:  # 5 minutes max
        raise ValidationError("Timeout cannot exceed 300 seconds", field="timeout_seconds")
    
    return float(timeout_seconds)
