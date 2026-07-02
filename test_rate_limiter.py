import math
import pytest
from rate_limiter import RateLimiter


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def now(self):
        return self.t


# --- Construction / starts full ---

def test_starts_full():
    c = FakeClock()
    rl = RateLimiter(10.0, 1.0, c)
    assert rl.available_tokens() == 10.0


def test_capacity_zero_raises():
    with pytest.raises(ValueError):
        RateLimiter(0, 1.0, FakeClock())


def test_capacity_negative_raises():
    with pytest.raises(ValueError):
        RateLimiter(-5, 1.0, FakeClock())


def test_refill_negative_raises():
    with pytest.raises(ValueError):
        RateLimiter(10.0, -1.0, FakeClock())


def test_refill_zero_ok():
    rl = RateLimiter(10.0, 0.0, FakeClock())
    assert rl.available_tokens() == 10.0


# --- try_acquire validation ---

def test_acquire_zero_raises():
    rl = RateLimiter(10.0, 1.0, FakeClock())
    with pytest.raises(ValueError):
        rl.try_acquire(0)


def test_acquire_negative_raises():
    rl = RateLimiter(10.0, 1.0, FakeClock())
    with pytest.raises(ValueError):
        rl.try_acquire(-1)


def test_tokens_gt_capacity_returns_false_never_raises():
    rl = RateLimiter(5.0, 1.0, FakeClock())
    assert rl.try_acquire(6.0) is False
    # nothing consumed
    assert rl.available_tokens() == 5.0


# --- Consumption semantics ---

def test_basic_consume():
    rl = RateLimiter(10.0, 1.0, FakeClock())
    assert rl.try_acquire(4.0) is True
    assert rl.available_tokens() == 6.0


def test_insufficient_consumes_nothing():
    c = FakeClock()
    rl = RateLimiter(10.0, 0.0, c)
    assert rl.try_acquire(8.0) is True
    assert rl.try_acquire(5.0) is False
    assert rl.available_tokens() == 2.0


def test_exact_boundary_true():
    c = FakeClock()
    rl = RateLimiter(10.0, 0.0, c)
    assert rl.try_acquire(10.0) is True
    assert rl.available_tokens() == 0.0


# --- Refill ---

def test_refill_over_time():
    c = FakeClock(0.0)
    rl = RateLimiter(10.0, 2.0, c)
    rl.try_acquire(10.0)
    c.t = 3.0
    assert rl.available_tokens() == pytest.approx(6.0)


def test_refill_capped_at_capacity():
    c = FakeClock(0.0)
    rl = RateLimiter(10.0, 5.0, c)
    rl.try_acquire(10.0)
    c.t = 1000.0
    assert rl.available_tokens() == 10.0


def test_fractional_refill_and_tokens():
    c = FakeClock(0.0)
    rl = RateLimiter(1.0, 0.25, c)
    assert rl.try_acquire(1.0) is True
    c.t = 2.0  # 0.5 tokens
    assert rl.try_acquire(0.5) is True
    assert rl.available_tokens() == pytest.approx(0.0)


# --- Non-monotonic clock ---

def test_backward_clock_no_refill_no_loss():
    c = FakeClock(100.0)
    rl = RateLimiter(10.0, 1.0, c)
    rl.try_acquire(5.0)  # 5 left
    c.t = 50.0  # go backwards
    assert rl.available_tokens() == 5.0  # unchanged
    # Then advance forward from the original time (not the backward one)
    c.t = 101.0
    # elapsed from last_time (100) = 1 -> +1 token
    assert rl.available_tokens() == pytest.approx(6.0)


def test_backward_then_forward_from_backward_point():
    # Ensures last_time did NOT move backward
    c = FakeClock(100.0)
    rl = RateLimiter(10.0, 1.0, c)
    rl.try_acquire(10.0)  # 0 tokens
    c.t = 90.0
    rl.available_tokens()  # backward, elapsed 0
    c.t = 95.0  # still before 100, elapsed still negative -> 0
    assert rl.available_tokens() == 0.0
    c.t = 100.0
    assert rl.available_tokens() == 0.0
    c.t = 105.0
    assert rl.available_tokens() == pytest.approx(5.0)


# --- Sequences ---

def test_sequence_deplete_and_refill():
    c = FakeClock(0.0)
    rl = RateLimiter(3.0, 1.0, c)
    assert rl.try_acquire(1.0) is True
    assert rl.try_acquire(1.0) is True
    assert rl.try_acquire(1.0) is True
    assert rl.try_acquire(1.0) is False
    c.t = 1.0
    assert rl.try_acquire(1.0) is True
    assert rl.try_acquire(1.0) is False


def test_default_tokens_arg():
    rl = RateLimiter(2.0, 0.0, FakeClock())
    assert rl.try_acquire() is True
    assert rl.try_acquire() is True
    assert rl.try_acquire() is False


# --- Interface exactness ---

def test_available_returns_float():
    rl = RateLimiter(5, 1, FakeClock())
    assert isinstance(rl.available_tokens(), float)


def test_no_time_import():
    import rate_limiter
    import inspect
    src = inspect.getsource(rate_limiter)
    assert "import time" not in src


# --- Adversarial: floating point boundary after refill ---

def test_float_accumulation_boundary():
    c = FakeClock(0.0)
    rl = RateLimiter(1.0, 0.1, c)
    rl.try_acquire(1.0)
    c.t = 10.0  # exactly 1.0 refilled
    assert rl.try_acquire(1.0) is True
