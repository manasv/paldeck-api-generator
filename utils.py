import re


def normalize_pal_id(pal_id_raw: str) -> str:
    """Normalize a numeric Pal ID and uppercase its optional variant."""
    match = re.fullmatch(r"(\d+)([a-zA-Z]?)", pal_id_raw.strip())
    if match:
        return match.group(1) + match.group(2).upper()
    return pal_id_raw.strip()


def slugify(value: str) -> str:
    """Create a stable snake_case identifier from display text."""
    value = re.sub(r"[^\w]+", "_", value.strip().lower(), flags=re.UNICODE)
    return value.strip("_")
