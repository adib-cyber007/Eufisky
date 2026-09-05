"""Text normalization shared by live speech and the offline rule harness."""

from __future__ import annotations

import re

_DIGITS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2",
    "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9",
}
_SYNONYMS = (
    (r"\bs\.?\s*s\.?\s*n\.?\b", "social security number"),
    (r"\bsocial security card\b", "social security number"),
    (r"\bmedicare id\b", "medicare number"),
    (r"\bmedicare card number\b", "medicare number"),
    (r"\bcredit card digits\b", "card number"),
    (r"\bpasscode\b", "pin"),
    (r"\bwire the money\b", "wire transfer"),
    (r"\bdoctor\b", "dr"),
)


def normalize(text: str) -> str:
    """Return lowercase matching text with spoken digit runs collapsed."""

    value = text.lower().replace("’", "'")
    for pattern, replacement in _SYNONYMS:
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"[^a-z0-9/\-']+", " ", value)
    tokens = value.split()
    output: list[str] = []
    digit_run: list[str] = []

    def flush_digits() -> None:
        if digit_run:
            output.append("".join(digit_run))
            digit_run.clear()

    for token in tokens:
        digit = _DIGITS.get(token)
        if digit is not None:
            digit_run.append(digit)
        else:
            flush_digits()
            output.append(token.strip("'"))
    flush_digits()
    return " ".join(token for token in output if token)
