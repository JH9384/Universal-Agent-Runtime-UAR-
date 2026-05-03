def validate_skill(skill: dict) -> bool:
    """Basic safety filter for imported skills."""
    dangerous_tokens = [
        "rm ",
        "sudo",
        "os.system",
        "subprocess",
        "bash",
        "sh ",
    ]

    raw = skill.get("raw", "").lower()

    return not any(token in raw for token in dangerous_tokens)
