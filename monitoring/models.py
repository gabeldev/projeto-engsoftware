from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class Role(str, Enum):
    ADMIN = 'ADMIN'
    MONITOR = 'MONITOR'
    STUDENT = 'STUDENT'


@dataclass(frozen=True)
class User:
    id: int
    name: str
    role: Role


@dataclass(frozen=True)
class AppointmentSlot:
    id: int
    monitor_id: int
    subject: str
    starts_at: datetime
    capacity: int

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=30)
