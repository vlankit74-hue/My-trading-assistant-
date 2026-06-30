"""
A simple shared async rate limiter (token bucket / sliding window) used to
keep ALL outbound calls to a given upstream API under a fixed
calls-per-minute budget, no matter which code path triggers them.

This exists because Twelve Data's free/basic plan allows only 8 calls per
minute total. Each provider call site independently sleeping between its
own requests (e.g. "poll every 30s") is not enough to stay under that
budget: two independent streaming loops (Gold + BTC) plus on-demand REST
endpoints (candles/analysis, on a cache miss) can all fire within the same
few seconds of each other with no coordination, easily bursting past the
limit even though each individual loop looks well-behaved in isolation.
A single shared limiter that every call path awaits before hitting the
network is the only way to guarantee the aggregate stays under budget.
"""
import asyncio
import time


class AsyncRateLimiter:
    """Sliding-window limiter: at most `max_calls` calls in any rolling
    `period_seconds` window, shared across all callers via one instance."""

    def __init__(self, max_calls: int, period_seconds: float):
        self._max_calls = max_calls
        self._period = period_seconds
        self._call_times: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                # Drop timestamps older than the window.
                self._call_times = [t for t in self._call_times if now - t < self._period]

                if len(self._call_times) < self._max_calls:
                    self._call_times.append(now)
                    return

                # Wait until the oldest call in the window expires.
                wait_for = self._period - (now - self._call_times[0]) + 0.05
                await asyncio.sleep(max(wait_for, 0.05))
