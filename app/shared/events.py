"""In-memory event bus. Publishers publish only after their unit of work commits; handlers use their own."""

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Base class for events; each event type belongs to the context that publishes it."""


class EventPublisher(Protocol):
    def publish(self, event: Event) -> None: ...


class InMemoryEventBus:
    """Calls every handler subscribed to the event's exact type, synchronously, in subscription order.

    A failing handler is logged and does not stop the others nor undo what the publisher already committed.
    """

    def __init__(self) -> None:
        self._handlers: defaultdict[type[Event], list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe[E: Event](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        # One map holds handlers of every event type; the key guarantees each receives its own type
        self._handlers[event_type].append(cast(Callable[[Any], None], handler))

    def publish(self, event: Event) -> None:
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception:
                log.exception("Handler for %s failed", type(event).__name__)
