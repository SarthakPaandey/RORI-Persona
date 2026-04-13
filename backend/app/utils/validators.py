"""Input validation helpers."""


def non_empty_str(value: str, field_name: str = "value") -> str:
    """Return stripped string or raise if empty."""
    s = value.strip()
    if not s:
        raise ValueError(f"{field_name} must not be empty")
    return s
