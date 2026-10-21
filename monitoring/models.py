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


@dataclass(frozen=True)
class Booking:
    id: int
    student_id: int
    slot_id: int
    question: str
    created_at: datetime
    status: str
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None


@dataclass(frozen=True)
class Notification:
    id: int
    user_id: int
    message: str
    created_at: datetime

class RequestStatus(str, Enum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'


@dataclass(frozen=True)
class ExceptionRequest:
    id: int
    booking_id: int
    requester_id: int
    reason: str
    status: RequestStatus
    created_at: datetime
    decided_by: int | None = None
    decided_at: datetime | None = None
    decision_note: str = ''