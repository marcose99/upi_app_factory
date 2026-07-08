from __future__ import annotations


class Metrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def increment(self, name: str) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1
