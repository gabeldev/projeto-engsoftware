"""Relatórios exclusivos do ADMIN: horas mensais de monitores e dúvidas por disciplina."""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from monitoring.models import AttendanceStatus, Role, User
from monitoring.schedule import PermissionDeniedError
from monitoring.sqlite_repository import SQLiteScheduleRepository

SESSION_HOURS = 0.5  # cada atendimento dura 30 minutos


@dataclass(frozen=True)
class MonitorMonthlyRow:
    monitor_id: int
    sessions: int
    hours: float
    active_bookings: int
    cancelled_bookings: int
    feedback_count: int
    average_rating: float | None
    present: int = 0
    absent: int = 0


@dataclass(frozen=True)
class QuestionGroup:
    subject: str
    question: str
    count: int


class ReportService:
    def __init__(self, repository: SQLiteScheduleRepository,
                 clock: Callable[[], datetime] = datetime.now):
        self.repository = repository
        self.clock = clock

    def monthly_hours(self, admin: User, year: int, month: int) -> list[MonitorMonthlyRow]:
        """Horas por monitor no mês, para bolsas.

        Um atendimento conta quando a vaga está no mês, já terminou e teve ao menos
        um aluno presente (vaga sem presença registrada não conta horas). Cada um vale 0,5 h.
        """
        self._require_admin(admin)
        if (type(year) is not int or type(month) is not int
                or not 2000 <= year <= 2100 or not 1 <= month <= 12):
            raise ValueError('Informe um ano entre 2000 e 2100 e um mês de 1 a 12.')
        start = datetime(year, month, 1)
        end = datetime(year + month // 12, month % 12 + 1, 1)
        now = self.clock()
        by_slot: dict[int, list] = {}
        for booking in self.repository.list_bookings():
            by_slot.setdefault(booking.slot_id, []).append(booking)
        ratings = {f.booking_id: f.rating for f in self.repository.list_feedback()}
        marks = {a.booking_id: a.status for a in self.repository.list_attendance()}
        totals: dict[int, dict] = {}
        for slot in self.repository.list_slots():
            if not (start <= slot.starts_at < end and slot.ends_at <= now):
                continue
            mine = by_slot.get(slot.id, [])
            active = [b for b in mine if b.status == 'ACTIVE']
            row = totals.setdefault(slot.monitor_id, {
                'sessions': 0, 'active': 0, 'cancelled': 0, 'present': 0, 'absent': 0, 'ratings': []})
            present = [b for b in active if marks.get(b.id) == AttendanceStatus.PRESENT]
            if present:
                row['sessions'] += 1
                row['ratings'] += [ratings[b.id] for b in present if b.id in ratings]
            row['active'] += len(active)
            row['present'] += len(present)
            row['absent'] += sum(1 for b in active if marks.get(b.id) == AttendanceStatus.ABSENT)
            row['cancelled'] += len(mine) - len(active)
        return [MonitorMonthlyRow(
                    monitor_id, row['sessions'], row['sessions'] * SESSION_HOURS,
                    row['active'], row['cancelled'], len(row['ratings']),
                    round(sum(row['ratings']) / len(row['ratings']), 2) if row['ratings'] else None,
                    row['present'], row['absent'])
                for monitor_id, row in sorted(totals.items())]

    def questions_by_subject(self, admin: User, subject: str | None = None) -> list[QuestionGroup]:
        """Dúvidas das reservas ativas agrupadas por disciplina e conteúdo, mais frequentes primeiro."""
        self._require_admin(admin)
        query = subject.strip().casefold() if isinstance(subject, str) and subject.strip() else None
        slots = {s.id: s for s in self.repository.list_slots()}
        groups: dict[tuple[str, str], list] = {}
        names: dict[str, str] = {}  # grafia da primeira vaga de cada disciplina
        for booking in self.repository.list_bookings():
            if booking.status != 'ACTIVE':
                continue
            slot = slots[booking.slot_id]
            if query is not None and slot.subject.casefold() != query:
                continue
            question = ' '.join(booking.question.split())
            name = names.setdefault(slot.subject.casefold(), slot.subject)
            key = (slot.subject.casefold(), question.casefold())
            if key in groups:
                groups[key][2] += 1
            else:
                groups[key] = [name, question, 1]
        return sorted((QuestionGroup(*g) for g in groups.values()),
                      key=lambda g: (g.subject.casefold(), -g.count, g.question.casefold()))

    @staticmethod
    def _require_admin(user: User) -> None:
        if user.role != Role.ADMIN:
            raise PermissionDeniedError('Relatórios são exclusivos do ADMIN.')
