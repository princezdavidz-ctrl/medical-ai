"""Conservative input checks before any hosted-model transfer."""
import re


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_KENYAN_PHONE = re.compile(r"(?<!\w)(?:\+?254|0)(?:7\d{8}|1\d{8})(?!\w)")
_IDENTIFIER_LABEL = re.compile(
    r"\b(?:MRN|medical\s+record(?:\s+number)?|patient\s+ID|national\s+ID|"
    r"passport|date\s+of\s+birth|DOB)\s*[:#-]?\s*\S+",
    re.IGNORECASE,
)


def contains_obvious_personal_identifiers(value: str) -> bool:
    """Catch common direct identifiers; this is not a complete PHI detector."""
    return any(
        pattern.search(value)
        for pattern in (_EMAIL, _KENYAN_PHONE, _IDENTIFIER_LABEL)
    )
