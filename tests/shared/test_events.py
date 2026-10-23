"""Unit tests for the in-memory event bus."""

from dataclasses import dataclass

import pytest

from app.shared.events import Event, InMemoryEventBus


@dataclass(frozen=True)
class Created(Event):
    name: str


@dataclass(frozen=True)
class Deleted(Event):
    name: str


def test_only_subscribers_of_the_published_type_run() -> None:
    bus = InMemoryEventBus()
    seen: list[str] = []
    bus.subscribe(Created, lambda e: seen.append(f"created {e.name}"))
    bus.subscribe(Deleted, lambda e: seen.append(f"deleted {e.name}"))

    bus.publish(Created("a"))

    assert seen == ["created a"]


def test_a_failing_handler_is_logged_and_does_not_stop_the_others(caplog: pytest.LogCaptureFixture) -> None:
    bus = InMemoryEventBus()
    seen: list[str] = []

    def broken(event: Created) -> None:
        raise RuntimeError("boom")

    bus.subscribe(Created, broken)
    bus.subscribe(Created, lambda e: seen.append(e.name))

    bus.publish(Created("a"))

    assert seen == ["a"]
    assert "Created" in caplog.text
    assert "boom" in caplog.text
