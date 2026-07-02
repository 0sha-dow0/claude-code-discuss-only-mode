"""Token-bucket rate limiter.

A single-module, single-class, in-memory token-bucket rate limiter.

Design constraints (binding):
    * No I/O, no threads, no persistence.
    * Time is read ONLY through an injected ``clock`` object exposing
      ``now() -> float`` (finite, monotonic seconds). This module never
      imports or references ``time`` / ``datetime`` or any other time source.
    * All misuse raises ``ValueError`` synchronously before any state
      mutation. No other exception type originates here.
    * A non-monotonic clock reading is tolerated (degraded to zero elapsed
      time), never raised on.

Concurrency: explicitly single-threaded. This class is NOT reentrant or
thread-safe; concurrent use is a caller precondition, not enforced here.

Internal state (private, not part of the public contract):
    ``_capacity``  bucket size (stored unmodified)
    ``_refill``    refill rate in tokens/second (stored unmodified)
    ``_clock``     injected time source
    ``_tokens``    current token count
    ``_last``      last clock reading used for refill accounting

Public interface (exact):
    class RateLimiter:
        def __init__(self, capacity, refill_per_second, clock) -> None: ...
        def try_acquire(self, tokens=1.0) -> bool: ...
        def available_tokens(self) -> float: ...
"""

__all__ = ["RateLimiter"]


class RateLimiter:
    """Continuous token-bucket rate limiter.

    The bucket starts full. Tokens accrue continuously at
    ``refill_per_second`` and are capped at ``capacity`` (never exceeded).
    Time advances only via the injected ``clock.now()``.
    """

    def __init__(self, capacity: float, refill_per_second: float, clock) -> None:
        # D1: validate capacity, then refill; either failure raises ValueError
        # before any state is established (I2.5 / AC2.4). ``not (capacity > 0)``
        # rejects 0, -0.0, and negatives (and, harmlessly, NaN).
        if not (capacity > 0):
            raise ValueError("capacity must be > 0")
        # refill_per_second == 0 is valid (a bucket that never refills, AC2.3).
        if not (refill_per_second >= 0):
            raise ValueError("refill_per_second must be >= 0")

        # I2.1 / I2.2 / AC2.6: stored unmodified (no arithmetic, no coercion).
        self._capacity = capacity
        self._refill = refill_per_second
        self._clock = clock
        # I2.3: bucket starts FULL -- bit-for-bit the passed capacity.
        self._tokens = capacity
        # I2.4 / AC2.7: single baseline clock read captured at construction.
        self._last = clock.now()

    def _apply_refill(self) -> None:
        """Accrue tokens for elapsed time. Single source of truth (Unit 3).

        Reads the clock exactly once, adds ``elapsed * refill`` capped at
        capacity, and advances the baseline. On a backward or equal reading
        the baseline is NOT rewound (D3) and no tokens are added or lost, so
        no retroactive burst is ever granted.
        """
        now = self._clock.now()
        # I3.3 / D3: monotonic guard. elapsed <= 0 means a backward or equal
        # reading -> zero refill, keep the high-water baseline (AC3.3/AC3.4).
        elapsed = now - self._last
        if elapsed <= 0:
            return
        # I3.5: account this interval exactly once by advancing the baseline.
        self._last = now
        # I3.6 / AC3.6: when refill is 0 the accrual term is a no-op; skip it so
        # the token count is left bit-for-bit unchanged. Otherwise cap at
        # capacity so I3.2 (_tokens <= _capacity) always holds (AC3.2/AC3.5).
        if self._refill:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Attempt to consume ``tokens``.

        Returns True and consumes exactly ``tokens`` iff, after refilling for
        elapsed time, at least ``tokens`` are available; otherwise returns
        False and consumes nothing.

        Raises ValueError if ``tokens <= 0`` (validated BEFORE any refill or
        state change, so the raising path has zero side effects -- I4.1 / D2).
        A request larger than capacity simply returns False (AC4.2); it never
        raises.
        """
        # D2 / I4.1: validate first -- no clock read, no mutation on this path.
        if not (tokens > 0):
            raise ValueError("tokens must be > 0")
        # I4.5 / AC4.8: refill on every non-raising call, including failures.
        self._apply_refill()
        # I4.4: boundary is inclusive (>=) so exact equality succeeds (AC4.3).
        if self._tokens >= tokens:
            # I4.2: atomic consume of exactly ``tokens``; never partial.
            self._tokens = self._tokens - tokens
            return True
        return False

    def available_tokens(self) -> float:
        """Return the current token count after refill, without consuming.

        Idempotent at a fixed clock value (I5.1) and always a ``float`` within
        ``[0.0, capacity]`` (I5.2 / I5.3), even when capacity was an ``int``
        (AC5.6).
        """
        self._apply_refill()
        return float(self._tokens)
