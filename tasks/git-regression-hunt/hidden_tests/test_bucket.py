import pytest

from ratekit.bucket import TokenBucket


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return FakeClock()


def test_starts_full(clock):
    b = TokenBucket(rate=2, capacity=5, clock=clock)
    assert all(b.try_acquire() for _ in range(5))
    assert not b.try_acquire()


def test_refill_whole_seconds(clock):
    b = TokenBucket(rate=2, capacity=5, clock=clock)
    for _ in range(5):
        b.try_acquire()
    clock.t += 1
    assert b.try_acquire() and b.try_acquire() and not b.try_acquire()


def test_refill_partial_seconds(clock):
    b = TokenBucket(rate=4, capacity=4, clock=clock)
    for _ in range(4):
        b.try_acquire()
    clock.t += 0.5
    assert b.try_acquire() and b.try_acquire() and not b.try_acquire()


def test_wait_time(clock):
    b = TokenBucket(rate=10, capacity=1, clock=clock)
    b.try_acquire()
    assert b.wait_time() == pytest.approx(0.1)
    clock.t += 0.05
    assert b.wait_time() == pytest.approx(0.05)


def test_capacity_cap(clock):
    b = TokenBucket(rate=100, capacity=3, clock=clock)
    clock.t += 60
    assert sum(b.try_acquire() for _ in range(10)) == 3


@pytest.mark.parametrize("rate,capacity", [(0, 1), (1, 0), (-1, 5)])
def test_rejects_bad_args(rate, capacity):
    with pytest.raises(ValueError):
        TokenBucket(rate, capacity)
