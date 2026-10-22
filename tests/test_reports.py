import unittest
from datetime import datetime, timedelta

from monitoring.attendance import AttendanceService
from monitoring.bookings import BookingService
from monitoring.feedback import FeedbackService
from monitoring.models import Role, User
from monitoring.reports import QuestionGroup, ReportService
from monitoring.schedule import PermissionDeniedError, ScheduleService
from monitoring.sqlite_repository import SQLiteScheduleRepository

EARLY = datetime(2026, 10, 1, 8)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = EARLY
        clock = lambda: self.now
        self.admin = User(1, 'Admin', Role.ADMIN)
        self.m2, self.m5 = User(2, 'M2', Role.MONITOR), User(5, 'M5', Role.MONITOR)
        self.students = [User(10 + i, f'A{i}', Role.STUDENT) for i in range(6)]
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.feedback = FeedbackService(self.repo, clock=clock)
        self.reports = ReportService(self.repo, clock=clock)
        self.attendance = AttendanceService(self.repo, clock=clock)

    def present(self, monitor, *bookings):
        for booking in bookings:
            self.attendance.mark(monitor, booking.id, 'PRESENT')

    def slot(self, monitor, subject, when, capacity=3):
        return self.schedule.create_slot(monitor, subject, when, capacity)

    def test_monthly_hours_counts_finished_slots_with_active_bookings(self):
        a = self.slot(self.m2, 'Calculus', datetime(2026, 10, 5, 14))
        b = self.slot(self.m2, 'Calculus', datetime(2026, 10, 6, 14))
        self.slot(self.m2, 'Calculus', datetime(2026, 10, 7, 14))  # sem reserva: não gera horas
        c = self.slot(self.m5, 'Physics', datetime(2026, 10, 8, 14))
        november = self.slot(self.m2, 'Calculus', datetime(2026, 11, 3, 14))
        b1 = self.bookings.book(self.students[0], a.id, 'x')
        b2 = self.bookings.book(self.students[1], a.id, 'y')
        b3 = self.bookings.book(self.students[2], b.id, 'z')
        gone = self.bookings.book(self.students[3], b.id, 'w')
        self.bookings.cancel(self.students[3], gone.id)
        b4 = self.bookings.book(self.students[4], c.id, 'v')
        no_show = self.bookings.book(self.students[3], c.id, 't')
        b6 = self.bookings.book(self.students[5], november.id, 'u')
        self.now = datetime(2026, 11, 20)
        self.present(self.m2, b1, b2, b3, b6)
        self.present(self.m5, b4)
        self.attendance.mark(self.m5, no_show.id, 'ABSENT')
        self.feedback.submit(self.students[0], b1.id, 5)
        self.feedback.submit(self.students[1], b2.id, 4)
        self.feedback.submit(self.students[4], b4.id, 3)
        rows = self.reports.monthly_hours(self.admin, 2026, 10)
        self.assertEqual([r.monitor_id for r in rows], [2, 5])
        first, second = rows
        self.assertEqual((first.sessions, first.hours, first.active_bookings, first.present, first.absent,
                          first.cancelled_bookings, first.feedback_count, first.average_rating),
                         (2, 1.0, 3, 3, 0, 1, 2, 4.5))
        self.assertEqual((second.sessions, second.hours, second.active_bookings, second.present,
                          second.absent, second.average_rating), (1, 0.5, 2, 1, 1, 3.0))
        november_rows = self.reports.monthly_hours(self.admin, 2026, 11)
        self.assertEqual([(r.monitor_id, r.sessions, r.average_rating) for r in november_rows], [(2, 1, None)])

    def test_session_without_any_present_student_gives_zero_hours(self):
        slot = self.slot(self.m2, 'Calculus', datetime(2026, 10, 5, 14))
        unmarked = self.bookings.book(self.students[0], slot.id, 'x')
        absent = self.bookings.book(self.students[1], slot.id, 'y')
        self.now = datetime(2026, 11, 1)
        self.attendance.mark(self.m2, absent.id, 'ABSENT')
        row = self.reports.monthly_hours(self.admin, 2026, 10)[0]
        self.assertEqual((row.sessions, row.hours, row.active_bookings, row.present, row.absent),
                         (0, 0.0, 2, 0, 1))
        self.attendance.mark(self.m2, unmarked.id, 'PRESENT')
        self.assertEqual(self.reports.monthly_hours(self.admin, 2026, 10)[0].hours, 0.5)

    def test_empty_slot_gives_zero_hours_and_future_slots_are_excluded(self):
        self.slot(self.m2, 'Calculus', datetime(2026, 10, 5, 14))
        self.slot(self.m5, 'Physics', datetime(2026, 12, 5, 14))
        self.now = datetime(2026, 11, 1)
        rows = self.reports.monthly_hours(self.admin, 2026, 10)
        self.assertEqual([(r.monitor_id, r.sessions, r.hours) for r in rows], [(2, 0, 0.0)])
        self.assertEqual(self.reports.monthly_hours(self.admin, 2026, 12), [])

    def test_month_boundaries_and_december_rollover(self):
        last = self.slot(self.m2, 'Calculus', datetime(2026, 10, 31, 23, 30))
        first = self.slot(self.m2, 'Physics', datetime(2026, 11, 1, 0, 0))
        december = self.slot(self.m5, 'Calculus', datetime(2026, 12, 31, 23, 30))
        january = self.slot(self.m5, 'Physics', datetime(2027, 1, 1, 0, 0))
        booked = [(slot, self.bookings.book(self.students[index], slot.id, 'x'))
                  for index, slot in enumerate((last, first, december, january))]
        self.now = datetime(2027, 2, 1)
        for slot, booking in booked:
            self.present(self.m2 if slot.monitor_id == 2 else self.m5, booking)
        sessions = lambda y, m: {r.monitor_id: r.sessions for r in self.reports.monthly_hours(self.admin, y, m)}
        self.assertEqual(sessions(2026, 10), {2: 1})
        self.assertEqual(sessions(2026, 11), {2: 1})
        self.assertEqual(sessions(2026, 12), {5: 1})
        self.assertEqual(sessions(2027, 1), {5: 1})

    def test_session_in_progress_is_not_counted_yet(self):
        slot = self.slot(self.m2, 'Calculus', datetime(2026, 10, 5, 14))
        booking = self.bookings.book(self.students[0], slot.id, 'x')
        self.now = slot.ends_at - timedelta(minutes=1)
        self.present(self.m2, booking)
        self.assertEqual(self.reports.monthly_hours(self.admin, 2026, 10), [])
        self.now = slot.ends_at
        self.assertEqual(self.reports.monthly_hours(self.admin, 2026, 10)[0].sessions, 1)

    def test_invalid_period_is_rejected(self):
        for year, month in ((2026, 0), (2026, 13), (1999, 5), (2101, 5), ('2026', 5), (2026, '5'),
                            (2026.0, 5), (True, 5), (None, 5)):
            with self.subTest(year=year, month=month), self.assertRaises(ValueError):
                self.reports.monthly_hours(self.admin, year, month)

    def test_reports_are_admin_only(self):
        for actor in (self.m2, self.students[0]):
            with self.subTest(role=actor.role):
                with self.assertRaises(PermissionDeniedError):
                    self.reports.monthly_hours(actor, 2026, 10)
                with self.assertRaises(PermissionDeniedError):
                    self.reports.questions_by_subject(actor)

    def test_questions_are_grouped_by_subject_and_content(self):
        calc1 = self.slot(self.m2, 'Calculus', datetime(2026, 10, 5, 14))
        calc2 = self.slot(self.m2, 'calculus ', datetime(2026, 10, 6, 14))
        phys = self.slot(self.m5, 'Physics', datetime(2026, 10, 7, 14))
        self.bookings.book(self.students[0], calc1.id, 'Derivadas')
        self.bookings.book(self.students[1], calc1.id, '  derivadas ')
        self.bookings.book(self.students[2], calc2.id, 'Integrais  por   partes')
        self.bookings.book(self.students[0], phys.id, 'Atrito')
        cancelled = self.bookings.book(self.students[3], phys.id, 'Atrito')
        self.bookings.cancel(self.students[3], cancelled.id)
        groups = self.reports.questions_by_subject(self.admin)
        self.assertEqual(groups, [
            QuestionGroup('Calculus', 'Derivadas', 2),
            QuestionGroup('Calculus', 'Integrais por partes', 1),
            QuestionGroup('Physics', 'Atrito', 1),
        ])
        self.assertEqual([g.question for g in self.reports.questions_by_subject(self.admin, ' PHYSICS ')],
                         ['Atrito'])
        self.assertEqual(self.reports.questions_by_subject(self.admin, 'Chemistry'), [])


if __name__ == '__main__':
    unittest.main()
