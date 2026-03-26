from __future__ import annotations

from datetime import datetime


class BotStats:
    def __init__(self) -> None:
        self.total_forwarded = 0
        self.cancelled = 0
        self.by_type: dict[str, int] = {}
        self.start_time = datetime.now()

    @property
    def total_attempts(self) -> int:
        return self.total_forwarded + self.cancelled

    def add_forward(self, file_type: str) -> None:
        self.total_forwarded += 1
        self.by_type[file_type] = self.by_type.get(file_type, 0) + 1

    def add_cancel(self) -> None:
        self.cancelled += 1

    def get_uptime(self) -> str:
        delta = datetime.now() - self.start_time
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{days}д {hours}ч {minutes}м"
