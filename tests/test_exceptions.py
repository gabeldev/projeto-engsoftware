import unittest
from datetime import datetime, timedelta

from monitoring.bookings import BookingService
from monitoring.errors import ExceptionNotNeededError, RequestStateError
from monitoring.exception_requests import (
    ExceptionRequestService, MIN_CANCELLATION_NOTICE, requires_exception,
)
from monitoring.models import RequestStatus, Role, User
from monitoring.schedule import PermissionDeniedError, ScheduleService
from monitoring.sqlite_repository import SQLiteScheduleRepository

NOW = datetime(2026, 10, 19, 10)


class ExceptionRequestTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = NOW
        clock = lambda: self.now
        self.admin = User(1, 'Admin', Role.ADMIN)
        self.monitor = User(2, 'Monitor', Role.MONITOR)
        self.student = User(3, 'Aluno', Role.STUDENT)
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.service = ExceptionRequestService(self.repo, admin_ids=[self.admin.id], clock=clock)
        # vaga em 24 h: dentro da janela de 72 h
        self.slot = self.schedule.create_slot(self.monitor, 'Calculus', NOW + timedelta(hours=24), 2)
        self.booking = self.bookings.book(self.student, self.slot.id, 'Limites')

    def messages(self, user):
        return [n.message for n in self.repo.list_notifications(user.id)]

    def test_rule_threshold_is_72_hours(self):
        self.assertEqual(MIN_CANCELLATION_NOTICE, timedelta(hours=72))
        start = self.slot.starts_at
        self.assertTrue(requires_exception(self.slot, start - timedelta(hours=71, minutes=59)))
        self.assertFalse(requires_exception(self.slot, start - timedelta(hours=72)))

    def test_student_requests_and_admin_is_notified(self):
        request = self.service.request(self.student, self.booking.id, ' Consulta ')
        self.assertEqual((request.status, request.reason, request.requester_id, request.created_at),
                         (RequestStatus.PENDING, 'Consulta', self.student.id, NOW))
        self.assertEqual(self.service.list_pending(self.admin), [request])
        self.assertIn(f'#{request.id}', self.messages(self.admin)[0])

    def test_monitor_of_the_slot_can_request(self):
        request = self.service.request(self.monitor, self.booking.id, 'Imprevisto')
        self.assertEqual(request.requester_id, self.monitor.id)

    def test_request_validations_leave_no_side_effects(self):
        outsiders = (User(4, 'Outro', Role.STUDENT), User(5, 'Outro monitor', Role.MONITOR), self.admin)
        for outsider in outsiders:
            with self.subTest(outsider=outsider), self.assertRaises(PermissionDeniedError):
                self.service.request(outsider, self.booking.id, 'x')
        for reason in ('', '  ', None):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                self.service.request(self.student, self.booking.id, reason)
        with self.assertRaises(ValueError):
            self.service.request(self.student, 999, 'x')
        self.assertEqual(self.service.list_pending(self.admin), [])
        self.assertEqual(self.messages(self.admin), [])

    def test_not_needed_with_notice_and_after_start_or_cancellation(self):
        far = self.schedule.create_slot(self.monitor, 'Physics', NOW + timedelta(days=5), 1)
        far_booking = self.bookings.book(self.student, far.id, 'Forca')
        with self.assertRaises(ExceptionNotNeededError):
            self.service.request(self.student, far_booking.id, 'x')
        self.now = self.slot.starts_at
        with self.assertRaises(ValueError):
            self.service.request(self.student, self.booking.id, 'x')
        self.now = NOW
        self.bookings.cancel(self.admin, self.booking.id, 'Admin cancelou')
        with self.assertRaisesRegex(ValueError, 'cancelada'):
            self.service.request(self.student, self.booking.id, 'x')

    def test_duplicate_request_rejected_until_rejected(self):
        first = self.service.request(self.student, self.booking.id, 'x')
        with self.assertRaises(RequestStateError):
            self.service.request(self.monitor, self.booking.id, 'y')
        self.service.reject(self.admin, first.id, 'Sem justificativa')
        second = self.service.request(self.student, self.booking.id, 'z')
        self.assertEqual(second.id, first.id + 1)

    def test_approve_notifies_involved_and_enables_cancellation(self):
        request = self.service.request(self.student, self.booking.id, 'x')
        with self.assertRaisesRegex(ValueError, '72'):
            self.bookings.cancel(self.student, self.booking.id)
        decided = self.service.approve(self.admin, request.id, 'Ok')
        self.assertEqual((decided.status, decided.decided_by, decided.decided_at, decided.decision_note),
                         (RequestStatus.APPROVED, self.admin.id, NOW, 'Ok'))
        self.assertTrue(self.service.is_approved(self.booking.id))
        self.assertEqual(self.service.list_pending(self.admin), [])
        for user in (self.student, self.monitor):
            self.assertTrue(any('aprovada' in m for m in self.messages(user)), user)
        cancelled = self.bookings.cancel(self.student, self.booking.id, 'Consulta')
        self.assertEqual(cancelled.status, 'CANCELLED')
        with self.assertRaisesRegex(ValueError, 'já foi cancelada'):
            self.bookings.cancel(self.student, self.booking.id)

    def test_approval_is_per_booking(self):
        other = self.schedule.create_slot(self.monitor, 'Physics', NOW + timedelta(hours=30), 1)
        other_booking = self.bookings.book(self.student, other.id, 'Forca')
        self.service.approve(self.admin, self.service.request(self.student, self.booking.id, 'x').id)
        with self.assertRaisesRegex(ValueError, '72'):
            self.bookings.cancel(self.student, other_booking.id)

    def test_reject_requires_note_and_keeps_cancellation_blocked(self):
        request = self.service.request(self.student, self.booking.id, 'x')
        with self.assertRaises(ValueError):
            self.service.reject(self.admin, request.id, '  ')
        self.assertEqual(self.service.list_pending(self.admin), [request])
        self.service.reject(self.admin, request.id, 'Fora do prazo')
        self.assertFalse(self.service.is_approved(self.booking.id))
        self.assertIn('Fora do prazo', self.messages(self.student)[-1])
        self.assertFalse(any('Fora do prazo' in m for m in self.messages(self.monitor)))
        with self.assertRaises(ValueError):
            self.bookings.cancel(self.student, self.booking.id)

    def test_only_admin_decides_and_only_once(self):
        request = self.service.request(self.student, self.booking.id, 'x')
        for user in (self.student, self.monitor):
            with self.subTest(role=user.role):
                with self.assertRaises(PermissionDeniedError):
                    self.service.approve(user, request.id)
                with self.assertRaises(PermissionDeniedError):
                    self.service.reject(user, request.id, 'x')
                with self.assertRaises(PermissionDeniedError):
                    self.service.list_pending(user)
        self.service.approve(self.admin, request.id)
        with self.assertRaises(RequestStateError):
            self.service.reject(self.admin, request.id, 'mudei de ideia')
        with self.assertRaises(ValueError):
            self.service.approve(self.admin, 999)
        self.assertEqual(self.repo.get_exception_request(request.id).status, RequestStatus.APPROVED)

    def test_approve_fails_when_booking_already_cancelled(self):
        request = self.service.request(self.student, self.booking.id, 'x')
        self.bookings.cancel(self.admin, self.booking.id, 'Admin cancelou')
        with self.assertRaises(ValueError):
            self.service.approve(self.admin, request.id)
        self.assertEqual(self.repo.get_exception_request(request.id).status, RequestStatus.PENDING)

    def test_admin_direct_cancellation_still_requires_reason(self):
        with self.assertRaises(ValueError):
            self.bookings.cancel(self.admin, self.booking.id, ' ')
        self.assertEqual(self.bookings.cancel(self.admin, self.booking.id, 'Monitor doente').status,
                         'CANCELLED')

    def test_requests_survive_reopening_file(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'db.sqlite3')
            clock = lambda: NOW
            first = SQLiteScheduleRepository(path)
            slot = ScheduleService(first, clock=clock).create_slot(
                self.monitor, 'Calculus', NOW + timedelta(hours=24), 1)
            booking = BookingService(first, clock=clock).book(self.student, slot.id, 'x')
            request = ExceptionRequestService(first, clock=clock).request(self.student, booking.id, 'x')
            first.close()
            with SQLiteScheduleRepository(path) as second:
                self.assertEqual(second.list_exception_requests(status=RequestStatus.PENDING), [request])


if __name__ == '__main__':
    unittest.main()
