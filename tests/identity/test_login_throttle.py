"""Unit tests for the login attempt limit policy (pure domain, no clock or database)."""

from app.identity.domain.throttle import LoginThrottle


def fail(throttle: LoginThrottle, key: str, *times: float) -> None:
    for now in times:
        throttle.record_failure(key, now)


def test_blocks_after_five_failures_within_the_window() -> None:
    throttle = LoginThrottle()
    fail(throttle, "10.0.0.1", 0, 1, 2, 3)
    assert not throttle.is_blocked("10.0.0.1", now=4)

    fail(throttle, "10.0.0.1", 4)

    assert throttle.is_blocked("10.0.0.1", now=5)


def test_a_failure_stops_counting_once_older_than_the_window() -> None:
    throttle = LoginThrottle()
    fail(throttle, "10.0.0.1", 0, 600, 601, 602, 603)

    assert throttle.is_blocked("10.0.0.1", now=900)  # exactly 900 s old still counts
    assert not throttle.is_blocked("10.0.0.1", now=900.5)


def test_reset_clears_the_failures_of_a_key() -> None:
    throttle = LoginThrottle()
    fail(throttle, "10.0.0.1", 0, 1, 2, 3, 4)

    throttle.reset("10.0.0.1")

    assert not throttle.is_blocked("10.0.0.1", now=5)


def test_keys_are_independent() -> None:
    throttle = LoginThrottle()
    fail(throttle, "10.0.0.1", 0, 1, 2, 3, 4)

    assert not throttle.is_blocked("10.0.0.2", now=5)
