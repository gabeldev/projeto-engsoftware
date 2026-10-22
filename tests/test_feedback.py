import os
import tempfile
import unittest
from datetime import datetime, timedelta

from monitoring.attendance import AttendanceService
from monitoring.bookings import BookingService
from monitoring.feedback import MAX_COMMENT_LENGTH, FeedbackService
from monitoring.models import Role, User
from monitoring.schedule import PermissionDeniedError, ScheduleService
from monitoring.sqlite_repository import SQLiteScheduleRepository

NOW = datetime(2026, 10, 19, 10)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = NOW
        clock = lambda: self.now
        self.admin = User(1, 'Admin', Role.ADMIN)
        self.monitor = User(2, 'Monitor', Role.MONITOR)
        self.other_monitor = User(5, 'Outro monitor', Role.MONITOR)
        self.student = User(3, 'Aluno', Role.STUDENT)
        self.other_student = User(4, 'Outro', Role.STUDENT)
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.service = FeedbackService(self.repo, clock=clock)
        self.attendance = AttendanceService(self.repo, clock=clock)
        self.slot = self.schedule.create_slot(self.monitor, 'Calculus', NOW + timedelta(days=4), 2)
        self.booking = self.bookings.book(self.student, self.slot.id, 'Derivadas')
        self.now = self.slot.ends_at  # atendimento terminou
        self.attendance.mark(self.monitor, self.booking.id, 'PRESENT')

    def test_student_submits_after_session_and_everyone_authorized_sees_it(self):
        item = self.service.submit(self.student, self.booking.id, 5, '  Ótimo  ')
        self.assertEqual((item.booking_id, item.student_id, item.rating, item.comment, item.created_at),
                         (self.booking.id, self.student.id, 5, 'Ótimo', self.slot.ends_at))
        for viewer in (self.student, self.monitor, self.admin):
            self.assertEqual(self.service.list_for(viewer), [item], viewer.role)
        for hidden in (self.other_student, self.other_monitor):
            self.assertEqual(self.service.list_for(hidden), [], hidden.role)

    def test_comment_is_optional(self):
        self.assertEqual(self.service.submit(self.student, self.booking.id, 1).comment, '')

    def test_invalid_ratings_and_long_comment_are_rejected_without_saving(self):
        for rating in (0, 6, -1, '5', 4.5, True, None):
            with self.subTest(rating=rating), self.assertRaises(ValueError):
                self.service.submit(self.student, self.booking.id, rating)
        with self.assertRaises(ValueError):
            self.service.submit(self.student, self.booking.id, 5, 'x' * (MAX_COMMENT_LENGTH + 1))
        self.assertEqual(self.repo.list_feedback(), [])
        self.assertEqual(self.service.submit(self.student, self.booking.id, 5, 'x' * MAX_COMMENT_LENGTH).rating, 5)

    def test_only_the_booking_student_can_submit(self):
        for actor in (self.admin, self.monitor, self.other_monitor, self.other_student):
            with self.subTest(role=actor.role, id=actor.id), self.assertRaises(PermissionDeniedError):
                self.service.submit(actor, self.booking.id, 5)
        self.assertEqual(self.repo.list_feedback(), [])

    def test_cannot_submit_before_the_session_ends(self):
        self.now = self.slot.ends_at - timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError, 'não terminou'):
            self.service.submit(self.student, self.booking.id, 5)
        self.now = self.slot.ends_at  # fronteira: exatamente no fim já vale
        self.assertEqual(self.service.submit(self.student, self.booking.id, 5).rating, 5)

    def test_cancelled_unknown_and_duplicate_are_rejected(self):
        with self.assertRaises(ValueError):
            self.service.submit(self.student, 999, 5)
        self.service.submit(self.student, self.booking.id, 4)
        with self.assertRaisesRegex(ValueError, 'já foi avaliada'):
            self.service.submit(self.student, self.booking.id, 5)
        self.assertEqual([f.rating for f in self.repo.list_feedback()], [4])
        self.now = NOW
        other_slot = self.schedule.create_slot(self.monitor, 'Physics', NOW + timedelta(days=6), 1)
        cancelled = self.bookings.book(self.student, other_slot.id, 'Força')
        self.bookings.cancel(self.student, cancelled.id)
        self.now = other_slot.ends_at
        with self.assertRaisesRegex(ValueError, 'canceladas'):
            self.service.submit(self.student, cancelled.id, 5)

    def test_only_students_marked_present_can_rate(self):
        self.now = NOW
        unmarked = self.bookings.book(self.other_student, self.slot.id, 'Integrais')
        self.now = self.slot.ends_at
        with self.assertRaisesRegex(ValueError, 'compareceu'):  # sem presença registrada
            self.service.submit(self.other_student, unmarked.id, 5)
        self.attendance.mark(self.monitor, unmarked.id, 'ABSENT')
        with self.assertRaisesRegex(ValueError, 'compareceu'):  # faltou
            self.service.submit(self.other_student, unmarked.id, 5)
        self.assertEqual(self.service.list_pending(self.other_student), [])
        self.assertEqual(self.repo.list_feedback(), [])

    def test_pending_lists_only_finished_active_unrated_bookings(self):
        self.assertEqual(self.service.list_pending(self.student), [self.booking])
        self.assertEqual(self.service.list_pending(self.other_student), [])
        self.service.submit(self.student, self.booking.id, 5)
        self.assertEqual(self.service.list_pending(self.student), [])
        for actor in (self.admin, self.monitor):
            with self.assertRaises(PermissionDeniedError):
                self.service.list_pending(actor)

    def test_feedback_survives_reopening_the_database_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'db.sqlite3')
            clock = lambda: self.now
            self.now = NOW
            with SQLiteScheduleRepository(path) as first:
                slot = ScheduleService(first, clock=clock).create_slot(
                    self.monitor, 'Calculus', NOW + timedelta(days=4), 1)
                booking = BookingService(first, clock=clock).book(self.student, slot.id, 'x')
                self.now = slot.ends_at
                AttendanceService(first, clock=clock).mark(self.monitor, booking.id, 'PRESENT')
                saved = FeedbackService(first, clock=clock).submit(self.student, booking.id, 3, 'ok')
            with SQLiteScheduleRepository(path) as second:
                self.assertEqual(FeedbackService(second, clock=clock).list_for(self.admin), [saved])


if __name__ == '__main__':
    unittest.main()
