from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class LoginThrottle:
    """At most `limit` failed logins per key (client IP) within the last `window_seconds`.

    Time is passed in (monotonic seconds) so the policy stays pure. State lives in memory: it is lost on restart.
    """

    limit: int = 5
    window_seconds: float = 900
    _failures: defaultdict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque), repr=False)

    def _recent(self, key: str, now: float) -> deque[float]:
        attempts = self._failures[key]
        while attempts and attempts[0] < now - self.window_seconds:
            attempts.popleft()
        return attempts

    def is_blocked(self, key: str, now: float) -> bool:
        return len(self._recent(key, now)) >= self.limit

    def record_failure(self, key: str, now: float) -> None:
        self._recent(key, now).append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
