from datetime import datetime, timedelta
from typing import Callable

from monitoring.models import AppointmentSlot, Role, User
from monitoring.repository import ScheduleRepository


class PermissionDeniedError(PermissionError):
    pass


class ScheduleConflictError(ValueError):
    pass


class ScheduleService:
    def __init__(self, repository: ScheduleRepository,
                 clock: Callable[[], datetime] = datetime.now):
        self.repository = repository
        self.clock = clock

    def create_slot(self, actor: User, subject: str, starts_at: datetime,
                    capacity: int = 1) -> AppointmentSlot:
        if actor.role != Role.MONITOR:
            raise PermissionDeniedError('Somente monitores podem publicar vagas próprias.')
        subject = subject.strip()
        if not subject:
            raise ValueError('Informe a disciplina.')
        if type(capacity) is not int or capacity < 1:
            raise ValueError('A capacidade deve ser um inteiro positivo.')
        if starts_at.tzinfo is not None:
            raise ValueError('Informe data e hora locais, sem fuso horário.')
        if starts_at.second or starts_at.microsecond:
            raise ValueError('O horário deve ter precisão de minuto.')
        if starts_at <= self.clock():
            raise ValueError('O horário deve estar no futuro.')
        ends_at = starts_at + timedelta(minutes=30)
        for slot in self.repository.list_slots():
            if (slot.monitor_id == actor.id and starts_at < slot.ends_at
                    and slot.starts_at < ends_at):
                raise ScheduleConflictError('O monitor já tem uma vaga nesse intervalo.')
        return self.repository.add_slot(actor.id, subject, starts_at, capacity)

    def list_slots(self, subject: str | None = None) -> list[AppointmentSlot]:
        """Consulta a agenda futura. Não calcula ocupação por reservas."""
        now = self.clock()
        query = subject.strip().casefold() if subject is not None else None
        return sorted(
            (slot for slot in self.repository.list_slots()
             if slot.starts_at > now and
             (query is None or slot.subject.casefold() == query)),
            key=lambda slot: (slot.starts_at, slot.id),
        )
