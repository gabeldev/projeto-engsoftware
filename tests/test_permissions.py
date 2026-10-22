"""Matriz de permissões: para cada operação, quem deve ser barrado e quem pode tentar.

`denied` precisa levantar PermissionDeniedError. `allowed` não pode levantar
PermissionDeniedError (pode falhar por regra de negócio, como o prazo de 72 h).
Cada tentativa roda num banco novo, então uma não interfere na outra.
"""
import unittest
from datetime import datetime, timedelta

from monitoring.attendance import AttendanceService
from monitoring.bookings import BookingService
from monitoring.exception_requests import ExceptionRequestService
from monitoring.feedback import FeedbackService
from monitoring.models import Role, User
from monitoring.reports import ReportService
from monitoring.schedule import PermissionDeniedError, ScheduleService
from monitoring.sqlite_repository import SQLiteScheduleRepository

NOW = datetime(2026, 10, 19, 10)
ADMIN = User(1, 'Admin', Role.ADMIN)
MON_A = User(2, 'Monitor A', Role.MONITOR)
MON_B = User(5, 'Monitor B', Role.MONITOR)
STU_A = User(3, 'Aluno A', Role.STUDENT)
STU_B = User(4, 'Aluno B', Role.STUDENT)
EVERYONE = (ADMIN, MON_A, MON_B, STU_A, STU_B)


class World:
    """Banco novo: vaga do monitor A, em 24 h, com reserva do aluno A."""

    def __init__(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.now = NOW
        clock = lambda: self.now
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.exceptions = ExceptionRequestService(self.repo, admin_ids=[ADMIN.id], clock=clock)
        self.feedback = FeedbackService(self.repo, clock=clock)
        self.reports = ReportService(self.repo, clock=clock)
        self.attendance = AttendanceService(self.repo, admin_ids=[ADMIN.id], clock=clock)
        self.slot = self.schedule.create_slot(MON_A, 'Calculus', NOW + timedelta(hours=24), 3)
        self.booking = self.bookings.book(STU_A, self.slot.id, 'Derivadas')
        self.request_id = None

    def with_request(self):
        self.request_id = self.exceptions.request(STU_A, self.booking.id, 'Consulta').id
        return self


OPERATIONS = {
    'create_slot': (
        lambda w, u: w.schedule.create_slot(u, 'Physics', NOW + timedelta(days=9), 1),
        {'denied': (ADMIN, STU_A, STU_B), 'allowed': (MON_A, MON_B)}),
    'book': (
        lambda w, u: w.bookings.book(u, w.slot.id, 'Limites'),
        {'denied': (ADMIN, MON_A, MON_B), 'allowed': (STU_A, STU_B)}),
    'list_questions': (
        lambda w, u: w.bookings.list_questions(u, w.slot.id),
        {'denied': (MON_B, STU_B), 'allowed': (ADMIN, MON_A, STU_A)}),
    'cancel': (
        lambda w, u: w.bookings.cancel(u, w.booking.id, 'Motivo'),
        {'denied': (MON_B, STU_B), 'allowed': (ADMIN, MON_A, STU_A)}),
    'request_exception': (
        lambda w, u: w.exceptions.request(u, w.booking.id, 'Motivo'),
        {'denied': (ADMIN, MON_B, STU_B), 'allowed': (MON_A, STU_A)}),
    'list_pending': (
        lambda w, u: w.exceptions.list_pending(u),
        {'denied': (MON_A, MON_B, STU_A, STU_B), 'allowed': (ADMIN,)}),
    'approve': (
        lambda w, u: w.with_request().exceptions.approve(u, w.request_id, 'ok'),
        {'denied': (MON_A, MON_B, STU_A, STU_B), 'allowed': (ADMIN,)}),
    'reject': (
        lambda w, u: w.with_request().exceptions.reject(u, w.request_id, 'não'),
        {'denied': (MON_A, MON_B, STU_A, STU_B), 'allowed': (ADMIN,)}),
    'submit_feedback': (
        lambda w, u: w.feedback.submit(u, w.booking.id, 5),
        {'denied': (ADMIN, MON_A, MON_B, STU_B), 'allowed': (STU_A,)}),
    'list_pending_feedback': (
        lambda w, u: w.feedback.list_pending(u),
        {'denied': (ADMIN, MON_A, MON_B), 'allowed': (STU_A, STU_B)}),
    'mark_attendance': (
        lambda w, u: w.attendance.mark(u, w.booking.id, 'PRESENT'),
        {'denied': (MON_B, STU_A, STU_B), 'allowed': (ADMIN, MON_A)}),
    'list_pending_attendance': (
        lambda w, u: w.attendance.list_pending(u),
        {'denied': (STU_A, STU_B), 'allowed': (ADMIN, MON_A, MON_B)}),
    'history_of_student_a': (
        lambda w, u: w.attendance.history(u, STU_A.id),
        {'denied': (STU_B,), 'allowed': (ADMIN, MON_A, MON_B, STU_A)}),
    'semester_absences_of_student_a': (
        lambda w, u: w.attendance.semester_absences(u, STU_A.id),
        {'denied': (MON_A, MON_B, STU_B), 'allowed': (ADMIN, STU_A)}),
    'monthly_report': (
        lambda w, u: w.reports.monthly_hours(u, 2026, 10),
        {'denied': (MON_A, MON_B, STU_A, STU_B), 'allowed': (ADMIN,)}),
    'questions_report': (
        lambda w, u: w.reports.questions_by_subject(u),
        {'denied': (MON_A, MON_B, STU_A, STU_B), 'allowed': (ADMIN,)}),
}


class PermissionMatrixTests(unittest.TestCase):
    def attempt(self, operation, user):
        world = World()
        self.addCleanup(world.repo.close)
        return OPERATIONS[operation][0](world, user)

    def test_every_operation_classifies_each_user_exactly_once(self):
        for name, (_, rules) in OPERATIONS.items():
            with self.subTest(operation=name):
                self.assertEqual(set(rules['denied']) | set(rules['allowed']), set(EVERYONE))
                self.assertFalse(set(rules['denied']) & set(rules['allowed']))

    def test_denied_users_are_blocked(self):
        for name, (_, rules) in OPERATIONS.items():
            for user in rules['denied']:
                with self.subTest(operation=name, user=user.name), self.assertRaises(PermissionDeniedError):
                    self.attempt(name, user)

    def test_allowed_users_are_not_blocked_by_permissions(self):
        for name, (_, rules) in OPERATIONS.items():
            for user in rules['allowed']:
                with self.subTest(operation=name, user=user.name):
                    try:
                        self.attempt(name, user)
                    except PermissionDeniedError as error:
                        self.fail(f'{user.name} não deveria ser barrado em {name}: {error}')
                    except ValueError:
                        pass  # regra de negócio (prazo, estado) não é problema de permissão

    def test_denied_attempts_leave_no_trace(self):
        world = World()
        self.addCleanup(world.repo.close)
        snapshot = lambda: (world.repo.list_slots(), world.repo.list_bookings(),
                            world.repo.list_exception_requests(), world.repo.list_feedback(),
                            world.repo.list_attendance())
        before = snapshot()
        for name in ('create_slot', 'book', 'request_exception', 'submit_feedback', 'mark_attendance'):
            for user in OPERATIONS[name][1]['denied']:
                with self.assertRaises(PermissionDeniedError):
                    OPERATIONS[name][0](world, user)
        self.assertEqual(before, snapshot())

    def test_visibility_of_bookings_and_feedback_by_profile(self):
        world = World()
        self.addCleanup(world.repo.close)
        other_slot = world.schedule.create_slot(MON_B, 'Physics', NOW + timedelta(days=5), 1)
        other = world.bookings.book(STU_B, other_slot.id, 'Força')
        ids = lambda user: sorted(b.id for b in world.bookings.list_bookings(user))
        self.assertEqual(ids(STU_A), [world.booking.id])
        self.assertEqual(ids(STU_B), [other.id])
        self.assertEqual(ids(MON_A), [world.booking.id])
        self.assertEqual(ids(MON_B), [other.id])
        self.assertEqual(ids(ADMIN), sorted([world.booking.id, other.id]))
        world.now = other_slot.ends_at
        world.attendance.mark(MON_A, world.booking.id, 'PRESENT')
        world.attendance.mark(MON_B, other.id, 'PRESENT')
        world.feedback.submit(STU_A, world.booking.id, 5)
        world.feedback.submit(STU_B, other.id, 2)
        owners = {u.name: [f.booking_id for f in world.feedback.list_for(u)] for u in EVERYONE}
        self.assertEqual(owners, {'Admin': [world.booking.id, other.id], 'Monitor A': [world.booking.id],
                                  'Monitor B': [other.id], 'Aluno A': [world.booking.id],
                                  'Aluno B': [other.id]})


if __name__ == '__main__':
    unittest.main()
