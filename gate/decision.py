from __future__ import annotations

import json
import re
from dataclasses import dataclass

_JSON_OBJECT = re.compile(r"\{.*?\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class GateDecision:
    action: str
    confidence: float
    reason: str

    @property
    def should_respond(self) -> bool:
        return self.action == "RESPOND"


def parse_gate_decision(raw: str) -> GateDecision | None:
    """Parse a conservative RESPOND/IGNORE decision.

    Any malformed or unknown output returns ``None`` so callers can fail closed.
    """

    if not isinstance(raw, str) or not raw.strip():
        return None

    match = _JSON_OBJECT.search(raw)
    if not match:
        return None

    try:
        payload = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    action = str(payload.get("decision", "")).strip().upper()
    if action not in {"RESPOND", "IGNORE"}:
        return None

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None

    reason = " ".join(str(payload.get("reason", "")).split())[:160]
    return GateDecision(action=action, confidence=confidence, reason=reason)
