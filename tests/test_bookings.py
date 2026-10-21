import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from monitoring.models import Role, User
from monitoring.sqlite_repository import SQLiteScheduleRepository
from monitoring.bookings import BookingService
from monitoring.schedule import ScheduleService


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = datetime(2026, 10, 19, 10)
        self.monitor = User(2, 'Monitor', Role.MONITOR)
        self.student = User(3, 'Aluno', Role.STUDENT)
        self.admin = User(1, 'Admin', Role.ADMIN)
        self.schedule = ScheduleService(self.repo, clock=lambda: self.now)
        self.service = BookingService(self.repo, clock=lambda: self.now)
        self.slot = self.schedule.create_slot(self.monitor, 'Calculus', self.now + timedelta(days=4), 2)

    def book(self, **changes):
        data = dict(student=self.student, slot_id=self.slot.id, question='Derivadas')
        data.update(changes)
        return self.service.book(**data)

    def test_booking_persists_and_consumes_capacity(self):
        booking = self.book()
        self.assertEqual(booking.question, 'Derivadas')
        self.book(student=User(4, 'Outro', Role.STUDENT))
        self.assertEqual(self.service.list_available_slots('Calculus'), [])
        with self.assertRaises(ValueError):
            self.book(student=User(5, 'Terceiro', Role.STUDENT))

    def test_validation_and_duplicates(self):
        for changes in ({'question': ' '}, {'slot_id': 999}, {'student': self.monitor}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, PermissionError)):
                self.book(**changes)
        self.book()
        with self.assertRaises(ValueError):
            self.book()

    def test_weekly_limit_and_next_week(self):
        self.book()
        second = self.schedule.create_slot(self.monitor, ' calculus ', self.slot.starts_at + timedelta(hours=1))
        third = self.schedule.create_slot(self.monitor, 'Calculus', self.slot.starts_at + timedelta(hours=2))
        self.book(slot_id=second.id)
        with self.assertRaises(ValueError):
            self.book(slot_id=third.id)
        next_week = self.schedule.create_slot(self.monitor, 'Calculus', self.slot.starts_at + timedelta(days=7))
        self.book(slot_id=next_week.id)

    def test_cancellation_releases_capacity_and_notifies(self):
        booking = self.book()
        cancelled = self.service.cancel(self.student, booking.id)
        self.assertEqual(cancelled.status, 'CANCELLED')
        self.assertEqual(len(self.repo.list_notifications(self.monitor.id)), 1)
        self.assertEqual(len(self.repo.list_notifications(self.student.id)), 1)
        self.assertEqual(len(self.service.list_available_slots()), 1)
        self.book()

    def test_deadline_boundary_and_admin_exception(self):
        booking = self.book()
        self.now = self.slot.starts_at - timedelta(hours=72) + timedelta(seconds=1)
        with self.assertRaises(ValueError):
            self.service.cancel(self.student, booking.id)
        with self.assertRaises(ValueError):
            self.service.cancel(self.admin, booking.id)
        self.service.cancel(self.admin, booking.id, reason='Exceção autorizada')
        with self.assertRaises(ValueError):
            self.service.cancel(self.admin, booking.id, reason='Repetida')

    def test_exactly_seventy_two_hours_allowed(self):
        booking = self.book()
        self.now = self.slot.starts_at - timedelta(hours=72)
        self.service.cancel(self.student, booking.id)

    def test_ownership_and_question_visibility(self):
        booking = self.book()
        stranger = User(8, 'Outro', Role.STUDENT)
        with self.assertRaises(PermissionError):
            self.service.cancel(stranger, booking.id)
        with self.assertRaises(PermissionError):
            self.service.list_questions(stranger, self.slot.id)
        self.assertEqual(self.service.list_questions(self.student, self.slot.id), ['Derivadas'])
        self.assertEqual(self.service.list_bookings(stranger), [])
        self.assertEqual(len(self.service.list_bookings(self.monitor)), 1)

    def test_started_slot_rejected(self):
        self.now = self.slot.starts_at
        with self.assertRaises(ValueError):
            self.book()

    def test_file_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'test.sqlite3')
            with SQLiteScheduleRepository(path) as repo:
                slot = ScheduleService(repo, clock=lambda: self.now).create_slot(
                    self.monitor, 'Physics', self.slot.starts_at)
                BookingService(repo, clock=lambda: self.now).book(self.student, slot.id, 'Forças')
            with SQLiteScheduleRepository(path) as repo:
                self.assertEqual(repo.list_slots()[0].subject, 'Physics')
                self.assertEqual(BookingService(repo).list_bookings(self.student)[0].question, 'Forças')


class BookingIntegrationTests(unittest.TestCase):
    def test_concurrent_connections_do_not_overbook(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        now = datetime(2026, 10, 19)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'race.sqlite3')
            with SQLiteScheduleRepository(path) as repo:
                slot = ScheduleService(repo, clock=lambda: now).create_slot(
                    User(2, 'Monitor', Role.MONITOR), 'Physics', now + timedelta(days=5))
            barrier = Barrier(2)

            def reserve(student_id):
                with SQLiteScheduleRepository(path) as repo:
                    barrier.wait(timeout=5)
                    try:
                        BookingService(repo, clock=lambda: now).book(
                            User(student_id, 'Aluno', Role.STUDENT), slot.id, 'Forças')
                        return 'booked'
                    except ValueError:
                        return 'full'

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(reserve, [3, 4]))
            self.assertCountEqual(results, ['booked', 'full'])

    def test_configurable_limit_and_other_subject(self):
        now = datetime(2026, 10, 19)
        with SQLiteScheduleRepository(':memory:') as repo:
            service = BookingService(repo, clock=lambda: now, weekly_limit=1)
            schedule = ScheduleService(repo, clock=lambda: now)
            monitor = User(2, 'Monitor', Role.MONITOR)
            student = User(3, 'Aluno', Role.STUDENT)
            for index, subject in enumerate(['Calculus', 'Physics', 'Calculus']):
                slot = schedule.create_slot(monitor, subject, now + timedelta(days=4, hours=index))
                if index < 2:
                    service.book(student, slot.id, 'Dúvida')
                else:
                    with self.assertRaises(ValueError):
                        service.book(student, slot.id, 'Dúvida')

    def test_monitor_ownership_and_failed_cancellation_has_no_side_effects(self):
        now = datetime(2026, 10, 19)
        with SQLiteScheduleRepository(':memory:') as repo:
            monitor = User(2, 'Monitor', Role.MONITOR)
            slot = ScheduleService(repo, clock=lambda: now).create_slot(
                monitor, 'Physics', now + timedelta(days=4))
            service = BookingService(repo, clock=lambda: now)
            booking = service.book(User(3, 'Aluno', Role.STUDENT), slot.id, 'Forças')
            with self.assertRaises(PermissionError):
                service.cancel(User(9, 'Outro monitor', Role.MONITOR), booking.id)
            self.assertEqual(repo.get_booking(booking.id).status, 'ACTIVE')
            self.assertEqual(repo.list_notifications(3), [])
            service.cancel(monitor, booking.id, 'Indisponibilidade')
            self.assertEqual(repo.get_booking(booking.id).status, 'CANCELLED')
