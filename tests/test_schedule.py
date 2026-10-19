import unittest
from datetime import datetime, timedelta

from monitoring.models import Role, User
from monitoring.repository import InMemoryScheduleRepository
from monitoring.schedule import ScheduleService, PermissionDeniedError, ScheduleConflictError


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, 10)
        self.service = ScheduleService(InMemoryScheduleRepository(), clock=lambda: self.now)
        self.monitor = User(1, 'Gabriel', Role.MONITOR)
        self.student = User(2, 'Aluno', Role.STUDENT)
        self.start = self.now + timedelta(days=1)

    def create(self, **changes):
        data = dict(actor=self.monitor, subject='Calculus', starts_at=self.start, capacity=2)
        data.update(changes)
        return self.service.create_slot(**data)

    def test_monitor_creates_thirty_minute_slot(self):
        slot = self.create()
        self.assertEqual(slot.ends_at - slot.starts_at, timedelta(minutes=30))
        self.assertEqual((slot.monitor_id, slot.capacity), (1, 2))
        self.assertEqual(self.service.list_slots('Calculus'), [slot])

    def test_other_roles_cannot_publish(self):
        for role in (Role.STUDENT, Role.ADMIN):
            with self.subTest(role=role), self.assertRaises(PermissionDeniedError):
                self.create(actor=User(3, 'Outro', role))
        self.assertEqual(self.service.list_slots(), [])

    def test_invalid_fields_are_rejected(self):
        for changes in ({'subject': ' '}, {'capacity': 0}, {'capacity': -1},
                        {'capacity': True}, {'capacity': 1.5}, {'starts_at': self.now},
                        {'starts_at': self.start.replace(second=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.create(**changes)
        self.assertEqual(self.service.list_slots(), [])

    def test_overlaps_rejected_even_across_subjects(self):
        self.create()
        for offset in (-29, 0, 29):
            with self.subTest(offset=offset), self.assertRaises(ScheduleConflictError):
                self.create(subject='Physics', starts_at=self.start + timedelta(minutes=offset))

    def test_adjacent_slots_and_different_monitors_allowed(self):
        self.create()
        self.create(starts_at=self.start + timedelta(minutes=30))
        self.create(actor=User(3, 'Ives', Role.MONITOR))
        self.assertEqual(len(self.service.list_slots()), 3)

    def test_query_filters_subject_orders_and_excludes_past(self):
        late = self.create(starts_at=self.start + timedelta(hours=1))
        early = self.create(subject=' Calculus ')
        self.create(subject='Physics', starts_at=self.start + timedelta(hours=2))
        self.assertEqual(self.service.list_slots(' calculus '), [early, late])
        self.assertEqual(self.service.list_slots('Unknown'), [])
        self.now = self.start
        self.assertEqual(self.service.list_slots('Calculus'), [late])

    def test_rejected_conflict_does_not_save_slot(self):
        original = self.create()
        with self.assertRaises(ScheduleConflictError):
            self.create()
        self.assertEqual(self.service.list_slots(), [original])


if __name__ == '__main__':
    unittest.main()
