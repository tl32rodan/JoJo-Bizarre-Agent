"""StandMessage bus — lightweight pub/sub for Stand-to-Stand communication.

Gold Experience uses this to coordinate with spawned Stands.
Messages are kept in-process; no external broker required.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class StandMessage:
    """A single message between Stands."""
    from_stand: str          # StandType.value of sender
    to_stand: str | None     # None = broadcast
    msg_type: str            # "task" | "result" | "status" | "feedback"
    content: Any
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)


Callback = Callable[[StandMessage], None]


class MessageBus:
    """Simple in-process pub/sub.

    Usage::

        bus = MessageBus()
        bus.subscribe("crazy_diamond", my_handler)
        bus.publish(StandMessage(
            from_stand="gold_experience",
            to_stand="crazy_diamond",
            msg_type="feedback",
            content={"code": "...", "review_request": True},
        ))
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callback]] = defaultdict(list)
        self._broadcast_subscribers: list[Callback] = []
        self._history: dict[str, list[StandMessage]] = defaultdict(list)

    def subscribe(self, stand: str, callback: Callback) -> None:
        """Subscribe *stand* to receive directed and broadcast messages."""
        self._subscribers[stand].append(callback)

    def subscribe_all(self, callback: Callback) -> None:
        """Subscribe to every message (broadcast listener)."""
        self._broadcast_subscribers.append(callback)

    def publish(self, msg: StandMessage) -> None:
        """Publish a message.  Delivers synchronously."""
        self._history[msg.correlation_id].append(msg)

        # Directed delivery.
        if msg.to_stand:
            for cb in self._subscribers.get(msg.to_stand, []):
                cb(msg)
        else:
            # Broadcast.
            for callbacks in self._subscribers.values():
                for cb in callbacks:
                    cb(msg)

        # Always notify broadcast listeners.
        for cb in self._broadcast_subscribers:
            cb(msg)

    def get_history(self, correlation_id: str) -> list[StandMessage]:
        """Return all messages for a given correlation chain."""
        return list(self._history.get(correlation_id, []))

    def clear(self) -> None:
        """Clear all history (not subscriptions)."""
        self._history.clear()
