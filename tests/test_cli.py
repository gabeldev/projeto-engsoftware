import unittest
from datetime import datetime
from io import StringIO
from unittest.mock import patch

from monitoring.cli import run
from monitoring.repository import InMemoryScheduleRepository
from monitoring.schedule import ScheduleService


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.service = ScheduleService(InMemoryScheduleRepository(),
                                       clock=lambda: datetime(2026, 10, 18))

    def execute(self, answers):
        with patch('builtins.input', side_effect=answers), patch('sys.stdout', new_callable=StringIO) as output:
            run(self.service)
        return output.getvalue()

    def test_monitor_publishes_and_student_consults_same_schedule(self):
        output = self.execute(['2', '1', 'Calculus', '2026-10-19 14:00', '2',
                               '0', '3', '2', 'Calculus', '0', '0'])
        self.assertIn('Vaga criada', output)
        self.assertIn('Calculus', output)
        self.assertIn('14:30', output)
        self.assertEqual(len(self.service.list_slots()), 1)

    def test_student_cannot_publish_and_invalid_input_recovers(self):
        output = self.execute(['invalid', '3', '1', '0', '0'])
        self.assertIn('Opção inválida', output)
        self.assertIn('Somente monitores', output)
        self.assertEqual(self.service.list_slots(), [])

    def test_invalid_date_recovers_and_eof_exits(self):
        output = self.execute(['2', '1', 'Calculus', 'invalid', '0', '0'])
        self.assertIn('Erro:', output)
        output = self.execute([EOFError()])
        self.assertIn('Encerrado', output)
