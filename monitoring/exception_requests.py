from datetime import datetime, timedelta
from typing import Callable, Iterable

from monitoring.errors import ExceptionNotNeededError
from monitoring.models import (
    AppointmentSlot, ExceptionRequest, RequestStatus, Role, User,
)
from monitoring.schedule import PermissionDeniedError
from monitoring.sqlite_repository import SQLiteScheduleRepository

MIN_CANCELLATION_NOTICE = timedelta(hours=72)


def requires_exception(slot: AppointmentSlot, now: datetime) -> bool:
    """True quando faltam menos de 72 h para a vaga."""
    return slot.starts_at - now < MIN_CANCELLATION_NOTICE


class ExceptionRequestService:
    """Pedido de exceção à regra das 72 h e análise pelo ADMIN.

    Com a exceção aprovada, `BookingService.cancel` deixa o aluno ou o monitor
    cancelarem a reserva. Avisos usam `repository.add_notification`.
    """

    def __init__(self, repository: SQLiteScheduleRepository,
                 admin_ids: Iterable[int] = (),
                 clock: Callable[[], datetime] = datetime.now):
        self.repository = repository
        self.admin_ids = tuple(admin_ids)
        self.clock = clock

    def request(self, actor: User, booking_id: int, reason: str) -> ExceptionRequest:
        reason = reason.strip() if isinstance(reason, str) else ''
        with self.repository.transaction():
            booking = self.repository.get_booking(booking_id)
            slot = self.repository.get_slot(booking.slot_id)
            owner = actor.role == Role.STUDENT and actor.id == booking.student_id
            monitor = actor.role == Role.MONITOR and actor.id == slot.monitor_id
            if not (owner or monitor):
                raise PermissionDeniedError(
                    'Só o aluno da reserva ou o monitor da vaga pedem exceção.')
            if not reason:
                raise ValueError('Informe o motivo da exceção.')
            if booking.status != 'ACTIVE':
                raise ValueError('A reserva já foi cancelada.')
            now = self.clock()
            if slot.starts_at <= now:
                raise ValueError('O atendimento já iniciou.')
            if not requires_exception(slot, now):
                raise ExceptionNotNeededError(
                    'O cancelamento tem 72 h ou mais de antecedência; não precisa de exceção.')
            request = self.repository.add_exception_request(booking_id, actor.id, reason, now)
            self._notify(self.admin_ids, now,
                         f'Nova solicitação de exceção #{request.id} para a reserva '
                         f'#{booking_id} ({slot.subject}, {slot.starts_at:%Y-%m-%d %H:%M}).')
            return request

    def list_pending(self, admin: User) -> list[ExceptionRequest]:
        self._require_admin(admin)
        return self.repository.list_exception_requests(status=RequestStatus.PENDING)

    def approve(self, admin: User, request_id: int, note: str = '') -> ExceptionRequest:
        self._require_admin(admin)
        note = note.strip() if isinstance(note, str) else ''
        with self.repository.transaction():
            request = self.repository.get_exception_request(request_id)
            booking = self.repository.get_booking(request.booking_id)
            slot = self.repository.get_slot(booking.slot_id)
            now = self.clock()
            if request.status == RequestStatus.PENDING and (
                    booking.status != 'ACTIVE' or slot.starts_at <= now):
                raise ValueError('A reserva não está mais ativa ou o atendimento já iniciou.')
            decided = self.repository.decide_exception_request(
                request_id, RequestStatus.APPROVED, admin.id, now, note)
            self._notify((request.requester_id, booking.student_id, slot.monitor_id), now,
                         f'Exceção #{decided.id} aprovada: a reserva #{booking.id} '
                         f'pode ser cancelada.' + (f' Observação: {note}' if note else ''))
            return decided

    def reject(self, admin: User, request_id: int, note: str) -> ExceptionRequest:
        self._require_admin(admin)
        note = note.strip() if isinstance(note, str) else ''
        if not note:
            raise ValueError('Informe a justificativa da recusa.')
        with self.repository.transaction():
            now = self.clock()
            decided = self.repository.decide_exception_request(
                request_id, RequestStatus.REJECTED, admin.id, now, note)
            self._notify((decided.requester_id,), now,
                         f'Exceção #{decided.id} recusada para a reserva '
                         f'#{decided.booking_id}: {note}')
            return decided

    def is_approved(self, booking_id: int) -> bool:
        return bool(self.repository.list_exception_requests(
            status=RequestStatus.APPROVED, booking_id=booking_id))

    def _notify(self, user_ids: Iterable[int], now: datetime, message: str) -> None:
        for user_id in dict.fromkeys(user_ids):
            self.repository.add_notification(user_id, message, now)

    @staticmethod
    def _require_admin(user: User) -> None:
        if user.role != Role.ADMIN:
            raise PermissionDeniedError('Somente o ADMIN analisa exceções.')
