from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    sender_name: str
    text: str


class GroupGateState:
    def __init__(self) -> None:
        self._history: dict[str, deque[HistoryEntry]] = defaultdict(deque)
        self._last_reply_at: dict[str, float] = {}
        self._inflight: set[str] = set()

    def recent(self, group_key: str, limit: int) -> list[HistoryEntry]:
        if limit <= 0:
            return []
        return list(self._history.get(group_key, deque()))[-limit:]

    def append(self, group_key: str, entry: HistoryEntry, limit: int) -> None:
        history = self._history[group_key]
        history.append(entry)
        trim_to = max(1, limit)
        while len(history) > trim_to:
            history.popleft()

    def cooling_down(
        self,
        group_key: str,
        cooldown_seconds: int,
        *,
        now: float | None = None,
    ) -> bool:
        if cooldown_seconds <= 0 or group_key not in self._last_reply_at:
            return False
        current = time.monotonic() if now is None else now
        return current - self._last_reply_at[group_key] < cooldown_seconds

    def mark_reply(self, group_key: str, *, now: float | None = None) -> None:
        self._last_reply_at[group_key] = time.monotonic() if now is None else now

    def begin(self, group_key: str) -> bool:
        if group_key in self._inflight:
            return False
        self._inflight.add(group_key)
        return True

    def end(self, group_key: str) -> None:
        self._inflight.discard(group_key)
