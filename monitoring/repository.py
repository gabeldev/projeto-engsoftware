from datetime import datetime
from typing import Protocol

from monitoring.models import AppointmentSlot


class ScheduleRepository(Protocol):
    def list_slots(self) -> list[AppointmentSlot]:
        """Retorna as vagas cadastradas, inclusive passadas."""
        ...

    def add_slot(self, monitor_id: int, subject: str, starts_at: datetime,
                 capacity: int) -> AppointmentSlot:
        """Gera um id único e salva a vaga; não recebe input do terminal."""
        ...


class InMemoryScheduleRepository:
    """Armazenamento temporário; Ives implementará o adaptador SQLite."""

    def __init__(self):
        self._slots: list[AppointmentSlot] = []

    def list_slots(self) -> list[AppointmentSlot]:
        return list(self._slots)

    def add_slot(self, monitor_id: int, subject: str, starts_at: datetime,
                 capacity: int) -> AppointmentSlot:
        slot = AppointmentSlot(len(self._slots) + 1, monitor_id, subject, starts_at, capacity)
        self._slots.append(slot)
        return slot
