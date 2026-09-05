"""Load and shape the deterministic scam lexicon."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

LEXICON_PATH = Path(__file__).with_name("lexicon.yaml")
KEYTERM_LIMIT = 100


def load_lexicon(path: Path = LEXICON_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data.get("signals"), dict):
        raise ValueError("lexicon must contain a signals mapping")
    return data


def streaming_keyterms(
    lexicon: dict[str, Any],
    org_names: list[str] | None = None,
    people_names: list[str] | None = None,
) -> list[str]:
    """Prioritize names, then lexicon phrases of at most three words."""

    terms: list[str] = []
    seen: set[str] = set()
    sources = [org_names or [], people_names or []]
    sources.extend(
        signal.get("phrases", [])
        for signal in lexicon.get("signals", {}).values()
        if isinstance(signal, dict)
    )
    for source in sources:
        for raw in source:
            term = str(raw).strip()
            key = term.casefold()
            if not term or len(term.split()) > 3 or len(term) > 50 or key in seen:
                continue
            seen.add(key)
            terms.append(term)
            if len(terms) == KEYTERM_LIMIT:
                return terms
    return terms
