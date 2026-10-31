"""A small in-memory sliding-window limiter.

It is per process, which is right for one server (the free Render plan runs exactly one). With several servers
the counts would need a shared store such as Redis; that is noted in docs/SECURITY.md."""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config

_lock = threading.Lock()


class Limiter:
    def __init__(self, name: str, limit: int, seconds: int):
        self.name, self.limit, self.seconds = name, limit, seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and hits[0] <= now - self.seconds:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)  # keeps memory bounded: idle keys are forgotten
            return deque()
        return hits

    def retry_after(self, key: str) -> int:
        """Seconds until one more hit would be allowed, or 0 when under the limit."""
        now = time.monotonic()
        with _lock:
            hits = self._trim(key, now)
            return 0 if len(hits) < self.limit else max(1, int(hits[0] + self.seconds - now) + 1)

    def hit(self, key: str) -> None:
        now = time.monotonic()
        with _lock:
            self._trim(key, now)
            self._hits[key].append(now)

    def check(self, key: str) -> None:
        """Counts one hit, or raises 429 when the key is over the limit."""
        if not config.RATE_LIMITS_ENABLED:
            return
        wait = self.retry_after(key)
        if wait:
            raise HTTPException(429, "Too many attempts. Please wait a bit and try again.", headers={"Retry-After": str(wait)})
        self.hit(key)

    def clear(self, key: str | None = None) -> None:
        with _lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


def client_ip(request: Request) -> str:
    """The caller's address. X-Forwarded-For is only believed when TRUST_PROXY is on, and then the LAST entry is
    used: that is the one our own proxy appended, whereas earlier entries can be written by the caller."""
    if config.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


# One limiter per kind of action. Numbers are generous for people and tight for scripts.
LOGIN_IP = Limiter("login-ip", 20, 60)            # any email, per address
LOGIN_ACCOUNT = Limiter("login-account", 5, 900)  # failed attempts on one email, per 15 minutes
REGISTER = Limiter("register", 10, 3600)
BOOKING = Limiter("booking", 30, 3600)            # per user
UPLOAD = Limiter("upload", 20, 3600)              # per user
WRITE = Limiter("write", 120, 60)                 # service/profile edits, per user
ALL = (LOGIN_IP, LOGIN_ACCOUNT, REGISTER, BOOKING, UPLOAD, WRITE)


def reset_all() -> None:
    for limiter in ALL:
        limiter.clear()
