"""Application naming and filtering helpers."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

from .config import KNOWN_APP_NAMES


def _humanise(token: str) -> str:
    """``visual-studio-code`` -> ``Visual Studio Code``."""
    cleaned = re.sub(r"[_\-]+", " ", token).strip()
    if not cleaned:
        return token
    words = cleaned.split()
    # A single camelCase/PascalCase token (``MyEditor``) is already readable.
    if len(words) == 1 and any(char.isupper() for char in words[0][1:]):
        return words[0]
    rendered: List[str] = []
    for word in words:
        if word.isupper() and len(word) <= 4:
            rendered.append(word)  # keep acronyms such as IDE, VLC, GIMP
        else:
            rendered.append(word[:1].upper() + word[1:].lower() if word else word)
    return " ".join(rendered)


def prettify_app_name(app_id: Optional[str], fallback: str = "") -> str:
    """Map a machine identifier (``WM_CLASS``, ``app_id``) to a display name."""
    raw = (app_id or "").strip()
    if not raw:
        return fallback.strip()

    candidates = [raw, raw.lower(), raw.rsplit(".", 1)[-1], raw.rsplit(".", 1)[-1].lower()]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in KNOWN_APP_NAMES:
            return KNOWN_APP_NAMES[candidate]
        lowered = candidate.lower()
        for known, friendly in KNOWN_APP_NAMES.items():
            if lowered == known.lower():
                return friendly

    # Reverse-domain style identifiers: org.gnome.Nautilus -> Nautilus
    tail = raw.rsplit(".", 1)[-1] if "." in raw else raw
    tail = tail.strip()
    if not tail:
        return fallback.strip() or raw
    return _humanise(tail)


def normalise(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def matches_any(text: Optional[str], patterns: Iterable[str]) -> bool:
    """Case-insensitive substring match against every pattern."""
    haystack = normalise(text)
    if not haystack:
        return False
    for pattern in patterns:
        needle = normalise(pattern)
        if needle and needle in haystack:
            return True
    return False


def should_track(
    app_id: Optional[str],
    app_name: Optional[str],
    title: Optional[str] = None,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
) -> bool:
    """Decide whether a foreground window should be recorded.

    * ``include`` acts as an allow-list when it is non-empty.
    * ``exclude`` always wins over ``include``.
    * An empty window (no identifier at all) is never tracked.
    """
    if not (app_id or "").strip() and not (app_name or "").strip():
        return False

    haystacks = [app_id, app_name, title]
    if include and not any(matches_any(value, include) for value in haystacks):
        return False
    if exclude and any(matches_any(value, exclude) for value in haystacks):
        return False
    return True


def desktop_app_id(process_cmdline: Sequence[str], fallback: str = "") -> str:
    """Derive a stable application id from a process command line."""
    if not process_cmdline:
        return fallback
    executable = process_cmdline[0]
    name = executable.rsplit("/", 1)[-1]
    if name in ("python", "python3", "bash", "sh", "env") and len(process_cmdline) > 1:
        name = process_cmdline[1].rsplit("/", 1)[-1]
    return name or fallback
