"""Presença, faltas por semestre e histórico de atendimentos."""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from monitoring.models import Attendance, AttendanceStatus, Booking, Role, User
from monitoring.schedule import PermissionDeniedError
from monitoring.sqlite_repository import SQLiteScheduleRepository

ABSENCE_LIMIT = 3  # a terceira falta no semestre vai ao ADMIN


def semester_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """1º semestre: janeiro a junho; 2º: julho a dezembro."""
    if moment.month <= 6:
        return datetime(moment.year, 1, 1), datetime(moment.year, 7, 1)
    return datetime(moment.year, 7, 1), datetime(moment.year + 1, 1, 1)


def semester_label(moment: datetime) -> str:
    return f'{moment.year}.{1 if moment.month <= 6 else 2}'


@dataclass(frozen=True)
class HistoryEntry:
    booking_id: int
    student_id: int
    slot_id: int
    subject: str
    starts_at: datetime
    question: str
    booking_status: str        # ACTIVE ou CANCELLED
    attendance: str | None     # PRESENT, ABSENT ou None (ainda não registrada)


class AttendanceService:
    def __init__(self, repository: SQLiteScheduleRepository, admin_ids: Iterable[int] = (),
                 clock: Callable[[], datetime] = datetime.now):
        self.repository = repository
        self.admin_ids = tuple(admin_ids)
        self.clock = clock

    def mark(self, actor: User, booking_id: int, status) -> Attendance:
        """O monitor da vaga (ou o ADMIN) registra presença ou falta, uma única vez.

        Falta avisa o aluno; a terceira falta no semestre avisa também o ADMIN.
        """
        if actor.role not in (Role.MONITOR, Role.ADMIN):
            raise PermissionDeniedError('Somente o monitor da vaga ou o ADMIN registram presença.')
        try:
            status = AttendanceStatus(status)
        except ValueError:
            raise ValueError('A situação deve ser PRESENT (presente) ou ABSENT (faltou).') from None
        with self.repository.transaction():
            booking = self.repository.get_booking(booking_id)
            slot = self.repository.get_slot(booking.slot_id)
            if actor.role == Role.MONITOR and slot.monitor_id != actor.id:
                raise PermissionDeniedError('Só o monitor da vaga registra a presença.')
            if booking.status != 'ACTIVE':
                raise ValueError('Reservas canceladas não têm presença.')
            now = self.clock()
            if slot.starts_at > now:
                raise ValueError('O atendimento ainda não começou.')
            record = self.repository.add_attendance(booking_id, status, actor.id, now)
            if status == AttendanceStatus.ABSENT:
                self._warn_absence(booking, slot, now)
            return record

    def list_pending(self, actor: User) -> list[Booking]:
        """Reservas ativas de atendimentos já iniciados, sem presença registrada."""
        if actor.role not in (Role.MONITOR, Role.ADMIN):
            raise PermissionDeniedError('Somente o monitor ou o ADMIN registram presença.')
        marked = {a.booking_id for a in self.repository.list_attendance()}
        now = self.clock()
        result = []
        for booking in self.repository.list_bookings():
            slot = self.repository.get_slot(booking.slot_id)
            if (booking.status == 'ACTIVE' and booking.id not in marked and slot.starts_at <= now
                    and (actor.role == Role.ADMIN or slot.monitor_id == actor.id)):
                result.append(booking)
        return result

    def history(self, actor: User, student_id: int | None = None) -> list[HistoryEntry]:
        """Reservas com a presença de cada uma, inclusive canceladas.

        Aluno: só as suas; monitor: as das suas vagas; ADMIN: todas.
        `student_id` filtra por aluno.
        """
        if actor.role == Role.STUDENT:
            if student_id not in (None, actor.id):
                raise PermissionDeniedError('O aluno só consulta o próprio histórico.')
            student_id = actor.id
        slots = {s.id: s for s in self.repository.list_slots()}
        marks = {a.booking_id: a.status.value for a in self.repository.list_attendance()}
        entries = []
        for booking in self.repository.list_bookings():
            slot = slots[booking.slot_id]
            if student_id is not None and booking.student_id != student_id:
                continue
            if actor.role == Role.MONITOR and slot.monitor_id != actor.id:
                continue
            entries.append(HistoryEntry(booking.id, booking.student_id, slot.id, slot.subject,
                                        slot.starts_at, booking.question, booking.status,
                                        marks.get(booking.id)))
        return sorted(entries, key=lambda e: (e.starts_at, e.booking_id))

    def semester_absences(self, actor: User, student_id: int | None = None,
                          moment: datetime | None = None) -> int:
        """Faltas do aluno no semestre de `moment` (padrão: agora). Aluno: só as suas; ADMIN: qualquer."""
        if actor.role == Role.STUDENT:
            if student_id not in (None, actor.id):
                raise PermissionDeniedError('O aluno só consulta as próprias faltas.')
            student_id = actor.id
        elif actor.role != Role.ADMIN:
            raise PermissionDeniedError('Faltas são consultadas pelo aluno ou pelo ADMIN.')
        if student_id is None:
            raise ValueError('Informe o aluno.')
        return self._absences(student_id, moment or self.clock())

    def _absences(self, student_id: int, moment: datetime) -> int:
        start, end = semester_bounds(moment)
        slots = {s.id: s for s in self.repository.list_slots()}
        bookings = {b.id: b for b in self.repository.list_bookings()}
        count = 0
        for mark in self.repository.list_attendance():
            booking = bookings[mark.booking_id]
            if (mark.status == AttendanceStatus.ABSENT and booking.student_id == student_id
                    and start <= slots[booking.slot_id].starts_at < end):
                count += 1
        return count

    def _warn_absence(self, booking: Booking, slot, now: datetime) -> None:
        when = f'{slot.subject}, {slot.starts_at:%Y-%m-%d %H:%M}'
        self.repository.add_notification(
            booking.student_id, f'Falta registrada na reserva #{booking.id} ({when}).', now)
        total = self._absences(booking.student_id, slot.starts_at)
        if total == ABSENCE_LIMIT:
            label = semester_label(slot.starts_at)
            self.repository.add_notification(
                booking.student_id,
                f'Atenção: esta é a sua {ABSENCE_LIMIT}ª falta no semestre {label}.', now)
            for admin_id in dict.fromkeys(self.admin_ids):
                self.repository.add_notification(
                    admin_id,
                    f'Aluno {booking.student_id} atingiu {ABSENCE_LIMIT} faltas no semestre {label}.',
                    now)
