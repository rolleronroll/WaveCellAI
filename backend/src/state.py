from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        if len(self._hits) > 10_000:
            self._hits.clear()
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class DailyBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._day = ""
        self._used = 0

    def _roll(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._day:
            self._day, self._used = today, 0

    def has_room(self) -> bool:
        self._roll()
        return self._used < self.limit

    def take(self) -> None:
        self._roll()
        self._used += 1


limiter_ip = SlidingWindowLimiter(20, 60.0)        # 20 messages per minute per IP
limiter_phone = SlidingWindowLimiter(30, 3600.0)   # 30 messages per hour per phone
claude_budget = DailyBudget(300)                   # Claude replies per day, per instance

EVENTS: deque[dict] = deque(maxlen=500)            # feeds the analytics page later


def log_event(**fields) -> None:
    EVENTS.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields})