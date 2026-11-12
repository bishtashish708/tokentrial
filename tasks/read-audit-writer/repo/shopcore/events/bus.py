"""In-process event bus."""

from collections import defaultdict
from collections.abc import Callable

_subscribers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)


def subscribe(topic: str):
    def register(fn):
        _subscribers[topic].append(fn)
        return fn

    return register


def publish(topic: str, payload: dict) -> None:
    for fn in list(_subscribers.get(topic, ())):
        fn(payload)
