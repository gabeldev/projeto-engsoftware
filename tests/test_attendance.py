import os
import tempfile
import unittest
from datetime import datetime, timedelta

from monitoring.attendance import (
    ABSENCE_LIMIT, AttendanceService, HistoryEntry, semester_bounds, semester_label,
)
from monitoring.bookings import BookingService
from monitoring.models import AttendanceStatus, Role, User
from monitoring.schedule import PermissionDeniedError, ScheduleService
from monitoring.sqlite_repository import SQLiteScheduleRepository

EARLY = datetime(2026, 2, 2, 8)


class AttendanceTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = EARLY
        clock = lambda: self.now
        self.admin, self.admin2 = User(1, 'Admin', Role.ADMIN), User(6, 'Admin 2', Role.ADMIN)
        self.monitor, self.other_monitor = User(2, 'Monitor', Role.MONITOR), User(5, 'Outro monitor', Role.MONITOR)
        self.student, self.other_student = User(3, 'Aluno', Role.STUDENT), User(4, 'Outro aluno', Role.STUDENT)
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.service = AttendanceService(self.repo, admin_ids=[self.admin.id, self.admin2.id], clock=clock)

    def booked(self, when, student=None, subject='Calculus', monitor=None):
        slot = self.schedule.create_slot(monitor or self.monitor, subject, when, 3)
        return slot, self.bookings.book(student or self.student, slot.id, 'Derivadas')

    def messages(self, user):
        return [n.message for n in self.repo.list_notifications(user.id)]

    # --- registro
    def test_monitor_marks_present_and_admin_can_mark_too(self):
        slot, first = self.booked(datetime(2026, 3, 2, 14))
        second = self.bookings.book(self.other_student, slot.id, 'x')
        self.now = slot.starts_at
        mark = self.service.mark(self.monitor, first.id, 'PRESENT')
        self.assertEqual((mark.booking_id, mark.status, mark.marked_by, mark.marked_at),
                         (first.id, AttendanceStatus.PRESENT, self.monitor.id, slot.starts_at))
        self.assertEqual(self.service.mark(self.admin, second.id, AttendanceStatus.ABSENT).marked_by, self.admin.id)
        self.assertEqual(self.messages(self.student), [])  # presença não gera aviso

    def test_only_the_slot_monitor_or_admin_may_mark(self):
        slot, booking = self.booked(datetime(2026, 3, 2, 14))
        self.now = slot.starts_at
        for actor in (self.student, self.other_student, self.other_monitor):
            with self.subTest(actor=actor.name), self.assertRaises(PermissionDeniedError):
                self.service.mark(actor, booking.id, 'PRESENT')
        self.assertEqual(self.repo.list_attendance(), [])

    def test_validation_rules(self):
        slot, booking = self.booked(datetime(2026, 3, 2, 14))
        with self.assertRaisesRegex(ValueError, 'não começou'):
            self.service.mark(self.monitor, booking.id, 'PRESENT')
        self.now = slot.starts_at - timedelta(minutes=1)
        with self.assertRaises(ValueError):
            self.service.mark(self.monitor, booking.id, 'PRESENT')
        self.now = slot.starts_at  # fronteira: exatamente no início já vale
        for status in ('presente', '', None, 'P', 1):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'PRESENT'):
                self.service.mark(self.monitor, booking.id, status)
        with self.assertRaises(ValueError):
            self.service.mark(self.monitor, 999, 'PRESENT')
        self.service.mark(self.monitor, booking.id, 'PRESENT')
        with self.assertRaisesRegex(ValueError, 'já foi registrada'):
            self.service.mark(self.monitor, booking.id, 'ABSENT')
        self.assertEqual([m.status for m in self.repo.list_attendance()], [AttendanceStatus.PRESENT])

    def test_cancelled_booking_has_no_attendance(self):
        slot, booking = self.booked(datetime(2026, 3, 2, 14))
        self.bookings.cancel(self.student, booking.id)
        self.now = slot.starts_at
        with self.assertRaisesRegex(ValueError, 'canceladas'):
            self.service.mark(self.monitor, booking.id, 'ABSENT')
        self.assertEqual(self.service.semester_absences(self.admin, self.student.id), 0)

    def test_pending_attendance_by_profile(self):
        slot, mine = self.booked(datetime(2026, 3, 2, 14))
        _, theirs = self.booked(datetime(2026, 3, 3, 14), self.other_student, 'Physics', self.other_monitor)
        self.assertEqual(self.service.list_pending(self.monitor), [])  # ainda não começou
        self.now = datetime(2026, 3, 10)
        self.assertEqual(self.service.list_pending(self.monitor), [mine])
        self.assertEqual(self.service.list_pending(self.other_monitor), [theirs])
        self.assertEqual(self.service.list_pending(self.admin), [mine, theirs])
        self.service.mark(self.monitor, mine.id, 'PRESENT')
        self.assertEqual(self.service.list_pending(self.monitor), [])
        with self.assertRaises(PermissionDeniedError):
            self.service.list_pending(self.student)

    # --- faltas e avisos
    def test_absence_warns_the_student_only(self):
        slot, booking = self.booked(datetime(2026, 3, 2, 14))
        self.now = slot.starts_at
        self.service.mark(self.monitor, booking.id, 'ABSENT')
        self.assertEqual(len(self.messages(self.student)), 1)
        self.assertIn(f'reserva #{booking.id}', self.messages(self.student)[0])
        self.assertEqual(self.messages(self.admin), [])
        self.assertEqual(self.messages(self.monitor), [])

    def test_third_absence_in_semester_warns_student_and_all_admins_once(self):
        records = [self.booked(datetime(2026, 3, 2, 14) + timedelta(days=7 * i))[1] for i in range(4)]
        self.now = datetime(2026, 5, 1)
        for number, booking in enumerate(records[:2], start=1):
            self.service.mark(self.monitor, booking.id, 'ABSENT')
            self.assertEqual(self.messages(self.admin), [], number)
            self.assertEqual(len(self.messages(self.student)), number)
        self.service.mark(self.monitor, records[2].id, 'ABSENT')
        self.assertEqual(ABSENCE_LIMIT, 3)
        self.assertEqual(len(self.messages(self.student)), 4)  # 3 avisos de falta + o da terceira
        self.assertIn('3ª falta no semestre 2026.1', self.messages(self.student)[-1])
        for admin in (self.admin, self.admin2):
            self.assertEqual(len(self.messages(admin)), 1)
            self.assertIn(f'Aluno {self.student.id} atingiu 3 faltas no semestre 2026.1', self.messages(admin)[0])
        self.service.mark(self.monitor, records[3].id, 'ABSENT')  # a quarta não repete o aviso ao ADMIN
        self.assertEqual(len(self.messages(self.admin)), 1)
        self.assertEqual(self.service.semester_absences(self.admin, self.student.id), 4)

    def test_presence_and_other_students_do_not_count(self):
        slots = [self.booked(datetime(2026, 3, 2, 14) + timedelta(days=7 * i))[1] for i in range(3)]
        others = [self.booked(datetime(2026, 4, 6, 14) + timedelta(days=7 * i), self.other_student)[1]
                  for i in range(3)]
        self.now = datetime(2026, 6, 1)
        self.service.mark(self.monitor, slots[0].id, 'ABSENT')
        self.service.mark(self.monitor, slots[1].id, 'ABSENT')
        self.service.mark(self.monitor, slots[2].id, 'PRESENT')
        for booking in others:
            self.service.mark(self.monitor, booking.id, 'ABSENT')
        self.assertEqual(self.messages(self.admin).count(f'Aluno {self.student.id} atingiu 3 faltas no semestre 2026.1.'), 0)
        self.assertEqual(self.service.semester_absences(self.admin, self.student.id), 2)
        self.assertEqual(len([m for m in self.messages(self.admin) if f'Aluno {self.other_student.id}' in m]), 1)

    def test_absences_count_across_subjects_but_reset_each_semester(self):
        june = self.booked(datetime(2026, 6, 29, 14))[1]
        physics = self.booked(datetime(2026, 5, 4, 14), subject='Physics', monitor=self.other_monitor)[1]
        calc = self.booked(datetime(2026, 5, 11, 14))[1]
        july = self.booked(datetime(2026, 7, 1, 14))[1]
        late = self.booked(datetime(2026, 12, 31, 23, 30))[1]
        january = self.booked(datetime(2027, 1, 4, 14))[1]
        self.now = datetime(2027, 2, 1)
        for booking, monitor in ((june, self.monitor), (physics, self.other_monitor), (calc, self.monitor)):
            self.service.mark(monitor, booking.id, 'ABSENT')
        self.assertEqual(len([m for m in self.messages(self.admin)]), 1)  # 3 no 1º semestre, entre disciplinas
        for booking in (july, late, january):
            self.service.mark(self.monitor, booking.id, 'ABSENT')
        self.assertEqual(len(self.messages(self.admin)), 1)  # 2 em 2026.2 e 1 em 2027.1: sem novo aviso
        moment = lambda y, m, d: datetime(y, m, d)
        self.assertEqual(self.service.semester_absences(self.admin, self.student.id, moment(2026, 6, 30)), 3)
        self.assertEqual(self.service.semester_absences(self.admin, self.student.id, moment(2026, 7, 1)), 2)
        self.assertEqual(self.service.semester_absences(self.admin, self.student.id, moment(2027, 1, 1)), 1)

    def test_semester_helpers(self):
        self.assertEqual(semester_bounds(datetime(2026, 6, 30, 23, 59)), (datetime(2026, 1, 1), datetime(2026, 7, 1)))
        self.assertEqual(semester_bounds(datetime(2026, 7, 1)), (datetime(2026, 7, 1), datetime(2027, 1, 1)))
        self.assertEqual([semester_label(datetime(2026, m, 1)) for m in (1, 6, 7, 12)],
                         ['2026.1', '2026.1', '2026.2', '2026.2'])

    def test_semester_absences_permissions(self):
        self.assertEqual(self.service.semester_absences(self.student), 0)
        for actor, target in ((self.student, self.other_student.id), (self.monitor, self.student.id)):
            with self.assertRaises(PermissionDeniedError):
                self.service.semester_absences(actor, target)
        with self.assertRaises(ValueError):
            self.service.semester_absences(self.admin)

    # --- histórico
    def test_history_lists_everything_with_attendance_and_respects_visibility(self):
        a, mine = self.booked(datetime(2026, 3, 2, 14))
        b, cancelled = self.booked(datetime(2026, 3, 9, 14))
        c, absent = self.booked(datetime(2026, 3, 16, 14))
        _, theirs = self.booked(datetime(2026, 3, 3, 14), self.other_student, 'Physics', self.other_monitor)
        self.bookings.cancel(self.student, cancelled.id)
        self.now = datetime(2026, 3, 20)
        self.service.mark(self.monitor, mine.id, 'PRESENT')
        self.service.mark(self.monitor, absent.id, 'ABSENT')
        history = self.service.history(self.student)
        self.assertEqual([(e.booking_id, e.booking_status, e.attendance) for e in history],
                         [(mine.id, 'ACTIVE', 'PRESENT'), (cancelled.id, 'CANCELLED', None),
                          (absent.id, 'ACTIVE', 'ABSENT')])
        self.assertIsInstance(history[0], HistoryEntry)
        self.assertEqual((history[0].subject, history[0].starts_at, history[0].question),
                         ('Calculus', a.starts_at, 'Derivadas'))
        self.assertEqual({e.booking_id for e in self.service.history(self.monitor)}, {mine.id, cancelled.id, absent.id})
        self.assertEqual([e.booking_id for e in self.service.history(self.other_monitor)], [theirs.id])
        self.assertEqual(len(self.service.history(self.admin)), 4)
        self.assertEqual([e.student_id for e in self.service.history(self.admin, self.other_student.id)],
                         [self.other_student.id])
        self.assertEqual(self.service.history(self.other_monitor, self.student.id), [])
        with self.assertRaises(PermissionDeniedError):
            self.service.history(self.student, self.other_student.id)
        self.assertEqual(len(self.service.history(self.student, self.student.id)), 3)

    def test_history_survives_reopening_the_database_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'db.sqlite3')
            clock = lambda: self.now
            with SQLiteScheduleRepository(path) as first:
                slot = ScheduleService(first, clock=clock).create_slot(self.monitor, 'Calculus', datetime(2026, 3, 2, 14), 1)
                booking = BookingService(first, clock=clock).book(self.student, slot.id, 'x')
                self.now = slot.starts_at
                AttendanceService(first, [self.admin.id], clock).mark(self.monitor, booking.id, 'ABSENT')
            with SQLiteScheduleRepository(path) as second:
                entries = AttendanceService(second, clock=clock).history(self.admin)
                self.assertEqual([(e.booking_id, e.attendance) for e in entries], [(booking.id, 'ABSENT')])
                self.assertEqual(AttendanceService(second, clock=clock).semester_absences(self.student), 1)


if __name__ == '__main__':
    unittest.main()
