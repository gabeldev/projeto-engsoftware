from datetime import datetime, timedelta
from typing import Callable

from monitoring.models import RequestStatus, Role, User
from monitoring.schedule import PermissionDeniedError
from monitoring.sqlite_repository import SQLiteScheduleRepository


class BookingService:
    def __init__(self, repository: SQLiteScheduleRepository,
                 clock: Callable[[], datetime] = datetime.now, weekly_limit: int = 2):
        if type(weekly_limit) is not int or weekly_limit < 1:
            raise ValueError('O limite semanal deve ser um inteiro positivo.')
        self.repository = repository
        self.clock = clock
        self.weekly_limit = weekly_limit

    def book(self, student: User, slot_id: int, question: str):
        if student.role != Role.STUDENT:
            raise PermissionDeniedError('Somente alunos podem reservar.')
        question = question.strip() if isinstance(question, str) else ''
        if not question:
            raise ValueError('Informe o conteúdo da dúvida.')
        with self.repository.transaction():
            slot = self.repository.get_slot(slot_id)
            now = self.clock()
            if slot.starts_at <= now:
                raise ValueError('A vaga deve estar no futuro.')
            active = [b for b in self.repository.list_bookings() if b.status == 'ACTIVE']
            if any(b.student_id == student.id and b.slot_id == slot_id for b in active):
                raise ValueError('Você já reservou esta vaga.')
            if sum(b.slot_id == slot_id for b in active) >= slot.capacity:
                raise ValueError('Vaga lotada.')
            week_start = slot.starts_at.date() - timedelta(days=slot.starts_at.weekday())
            count = 0
            for booking in active:
                if booking.student_id != student.id:
                    continue
                other = self.repository.get_slot(booking.slot_id)
                if (other.subject.casefold() == slot.subject.casefold()
                        and week_start <= other.starts_at.date() < week_start + timedelta(days=7)):
                    count += 1
            if count >= self.weekly_limit:
                raise ValueError('Limite semanal excedido para esta disciplina.')
            return self.repository.add_booking(student.id, slot_id, question, now)

    def list_available_slots(self, subject: str | None = None):
        active = [b for b in self.repository.list_bookings() if b.status == 'ACTIVE']
        query = subject.strip().casefold() if subject else None
        return sorted((s for s in self.repository.list_slots()
                       if s.starts_at > self.clock()
                       and (query is None or s.subject.casefold() == query)
                       and sum(b.slot_id == s.id for b in active) < s.capacity),
                      key=lambda s: (s.starts_at, s.id))

    def list_bookings(self, actor: User):
        return [b for b in self.repository.list_bookings()
                if actor.role == Role.ADMIN
                or (actor.role == Role.STUDENT and b.student_id == actor.id)
                or (actor.role == Role.MONITOR
                    and self.repository.get_slot(b.slot_id).monitor_id == actor.id)]

    def list_questions(self, actor: User, slot_id: int):
        slot = self.repository.get_slot(slot_id)
        bookings = [b for b in self.repository.list_bookings()
                    if b.slot_id == slot_id and b.status == 'ACTIVE']
        if not (actor.role == Role.ADMIN
                or (actor.role == Role.MONITOR and slot.monitor_id == actor.id)
                or (actor.role == Role.STUDENT and any(b.student_id == actor.id for b in bookings))):
            raise PermissionDeniedError('Dúvidas restritas aos participantes da vaga.')
        return [b.question for b in bookings]

    def cancel(self, actor: User, booking_id: int, reason: str = ''):
        with self.repository.transaction():
            booking = self.repository.get_booking(booking_id)
            slot = self.repository.get_slot(booking.slot_id)
            if not (actor.role == Role.ADMIN
                    or (actor.role == Role.STUDENT and booking.student_id == actor.id)
                    or (actor.role == Role.MONITOR and slot.monitor_id == actor.id)):
                raise PermissionDeniedError('Você não pode cancelar esta reserva.')
            if booking.status != 'ACTIVE':
                raise ValueError('A reserva já foi cancelada.')
            now = self.clock()
            if slot.starts_at <= now:
                raise ValueError('O atendimento já iniciou.')
            reason = reason.strip() if isinstance(reason, str) else ''
            if slot.starts_at - now < timedelta(hours=72):
                approved = self.repository.list_exception_requests(
                    status=RequestStatus.APPROVED, booking_id=booking_id)
                if actor.role != Role.ADMIN and not approved:
                    raise ValueError('Cancelamento exige pelo menos 72 horas de antecedência. '
                                     'Peça uma exceção ao ADMIN.')
                if actor.role == Role.ADMIN and not reason:
                    raise ValueError('Informe a justificativa da exceção.')
            cancelled = self.repository.cancel_booking(booking_id, now, reason)
            message = (f'Reserva #{booking_id} de {slot.subject}, {slot.starts_at:%Y-%m-%d %H:%M}, '
                       f'cancelada pelo usuário {actor.id}. Motivo: {reason or "Não informado"}.')
            for user_id in {booking.student_id, slot.monitor_id}:
                self.repository.add_notification(user_id, message, now)
            return cancelled
