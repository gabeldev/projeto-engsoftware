"""Feedback dos alunos sobre atendimentos já realizados."""
from datetime import datetime
from typing import Callable

from monitoring.models import AttendanceStatus, Booking, Feedback, Role, User
from monitoring.schedule import PermissionDeniedError
from monitoring.sqlite_repository import SQLiteScheduleRepository

MIN_RATING, MAX_RATING = 1, 5
MAX_COMMENT_LENGTH = 500


class FeedbackService:
    """Só o aluno da reserva avalia, uma vez, se compareceu e depois que o atendimento terminou."""

    def __init__(self, repository: SQLiteScheduleRepository,
                 clock: Callable[[], datetime] = datetime.now):
        self.repository = repository
        self.clock = clock

    def submit(self, student: User, booking_id: int, rating: int,
               comment: str = '') -> Feedback:
        if student.role != Role.STUDENT:
            raise PermissionDeniedError('Somente alunos avaliam atendimentos.')
        if type(rating) is not int or not MIN_RATING <= rating <= MAX_RATING:
            raise ValueError(f'A nota deve ser um inteiro de {MIN_RATING} a {MAX_RATING}.')
        comment = comment.strip() if isinstance(comment, str) else ''
        if len(comment) > MAX_COMMENT_LENGTH:
            raise ValueError(f'O comentário deve ter até {MAX_COMMENT_LENGTH} caracteres.')
        with self.repository.transaction():
            booking = self.repository.get_booking(booking_id)
            if booking.student_id != student.id:
                raise PermissionDeniedError('Só o aluno da reserva avalia o atendimento.')
            if booking.status != 'ACTIVE':
                raise ValueError('Reservas canceladas não podem ser avaliadas.')
            slot = self.repository.get_slot(booking.slot_id)
            now = self.clock()
            if slot.ends_at > now:
                raise ValueError('O atendimento ainda não terminou.')
            if not self._attended(booking_id):
                raise ValueError('Só quem compareceu pode avaliar o atendimento.')
            return self.repository.add_feedback(booking_id, student.id, rating, comment, now)

    def _attended(self, booking_id: int) -> bool:
        mark = self.repository.get_attendance(booking_id)
        return mark is not None and mark.status == AttendanceStatus.PRESENT

    def list_pending(self, student: User) -> list[Booking]:
        """Reservas do aluno com presença, já realizadas e ainda sem avaliação."""
        if student.role != Role.STUDENT:
            raise PermissionDeniedError('Somente alunos avaliam atendimentos.')
        rated = {f.booking_id for f in self.repository.list_feedback()}
        now = self.clock()
        return [b for b in self.repository.list_bookings()
                if b.student_id == student.id and b.status == 'ACTIVE'
                and b.id not in rated and self._attended(b.id)
                and self.repository.get_slot(b.slot_id).ends_at <= now]

    def list_for(self, actor: User) -> list[Feedback]:
        """Aluno: as próprias; monitor: as das suas vagas; ADMIN: todas."""
        feedback = self.repository.list_feedback()
        if actor.role == Role.ADMIN:
            return feedback
        if actor.role == Role.STUDENT:
            return [f for f in feedback if f.student_id == actor.id]
        owner = {b.id: self.repository.get_slot(b.slot_id).monitor_id
                 for b in self.repository.list_bookings()}
        return [f for f in feedback if owner.get(f.booking_id) == actor.id]
