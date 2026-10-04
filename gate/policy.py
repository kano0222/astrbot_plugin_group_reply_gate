from __future__ import annotations

import re
from dataclasses import dataclass

_SPLIT_VALUES = re.compile(r"[,，\s]+")


@dataclass(frozen=True, slots=True)
class ModePolicy:
    evaluation_probability: float
    confidence_threshold: float


_MODE_POLICIES = {
    "conservative": ModePolicy(0.15, 0.80),
    "balanced": ModePolicy(0.35, 0.65),
    "active": ModePolicy(0.70, 0.50),
}


def get_mode_policy(mode: object) -> ModePolicy:
    return _MODE_POLICIES.get(str(mode).strip().lower(), _MODE_POLICIES["balanced"])


def parse_string_set(raw: object) -> set[str]:
    if isinstance(raw, (list, tuple, set, frozenset)):
        values = raw
    else:
        values = _SPLIT_VALUES.split(str(raw or ""))
    return {str(value).strip() for value in values if str(value).strip()}


def group_is_allowed(
    *,
    umo: str,
    group_id: str,
    whitelist: set[str],
    blacklist: set[str],
) -> bool:
    identifiers = {str(umo).strip(), str(group_id).strip()} - {""}
    if identifiers & blacklist:
        return False
    return not whitelist or bool(identifiers & whitelist)


def contains_alias(text: str, aliases: set[str]) -> bool:
    normalized = text.casefold()
    return any(alias.casefold() in normalized for alias in aliases if alias)


def starts_with_ignored_prefix(text: str, prefixes: set[str]) -> bool:
    stripped = text.lstrip().casefold()
    for prefix in prefixes:
        normalized_prefix = prefix.casefold()
        if not normalized_prefix or not stripped.startswith(normalized_prefix):
            continue
        remainder = stripped[len(normalized_prefix) :]
        if not remainder:
            return True
        next_character = remainder[0]
        if next_character.isascii() and (
            next_character.isalnum() or next_character == "_"
        ):
            continue
        return True
    return False
