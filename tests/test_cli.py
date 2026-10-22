import unittest
from datetime import datetime, timedelta
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


class PersistentTerminalTests(unittest.TestCase):
    def test_booking_cancellation_and_notifications(self):
        from monitoring.bookings import BookingService
        from monitoring.sqlite_repository import SQLiteScheduleRepository
        from monitoring.models import User, Role
        with SQLiteScheduleRepository(':memory:') as repo:
            clock = lambda: datetime(2026, 10, 19)
            schedule = ScheduleService(repo, clock=clock)
            schedule.create_slot(User(2, 'Monitor', Role.MONITOR), 'Calculus', datetime(2026, 10, 25, 14), 1)
            bookings = BookingService(repo, clock=clock)
            answers = ['3', '3', '1', 'Derivadas', '4', '5', '1', 'Outro compromisso',
                       '6', '0', '0']
            with patch('builtins.input', side_effect=answers), patch('sys.stdout', new_callable=StringIO) as output:
                run(schedule, bookings)
            self.assertIn('Reserva criada', output.getvalue())
            self.assertIn('Reserva cancelada', output.getvalue())
            self.assertIn('Outro compromisso', output.getvalue())
            self.assertEqual(repo.list_bookings()[0].status, 'CANCELLED')


class ExceptionTerminalTests(unittest.TestCase):
    def test_student_requests_admin_approves_student_cancels(self):
        from monitoring.bookings import BookingService
        from monitoring.exception_requests import ExceptionRequestService
        from monitoring.models import Role, User
        from monitoring.sqlite_repository import SQLiteScheduleRepository
        with SQLiteScheduleRepository(':memory:') as repo:
            clock = lambda: datetime(2026, 10, 19)
            schedule = ScheduleService(repo, clock=clock)
            schedule.create_slot(User(2, 'Monitor', Role.MONITOR), 'Calculus', datetime(2026, 10, 20, 14), 1)
            bookings = BookingService(repo, clock=clock)
            exceptions = ExceptionRequestService(repo, admin_ids=[1], clock=clock)
            answers = ['3', '3', '1', 'Derivadas',
                       '5', '1', '',            # recusado: menos de 72 h
                       '8', '1', 'Consulta', '0',
                       '1', '6', '9', '1', 'A', 'Ok', '0',
                       '3', '6', '5', '1', 'Consulta', '0', '0']
            with patch('builtins.input', side_effect=answers), patch('sys.stdout', new_callable=StringIO) as output:
                run(schedule, bookings, exceptions)
            text = output.getvalue()
            self.assertIn('Cancelamento exige pelo menos 72 horas', text)
            self.assertIn('Solicitação #1 enviada', text)
            self.assertIn('Nova solicitação de exceção #1', text)
            self.assertIn('Exceção aprovada', text)
            self.assertIn('Reserva cancelada', text)
            self.assertEqual(repo.list_bookings()[0].status, 'CANCELLED')

    def test_only_admin_reviews(self):
        from monitoring.bookings import BookingService
        from monitoring.exception_requests import ExceptionRequestService
        from monitoring.sqlite_repository import SQLiteScheduleRepository
        with SQLiteScheduleRepository(':memory:') as repo:
            schedule = ScheduleService(repo)
            with patch('builtins.input', side_effect=['3', '9', '0', '1', '9', '0', '0']), \
                    patch('sys.stdout', new_callable=StringIO) as output:
                run(schedule, BookingService(repo), ExceptionRequestService(repo, admin_ids=[1]))
            self.assertIn('Somente o ADMIN', output.getvalue())
            self.assertIn('Nenhuma solicitação pendente', output.getvalue())


class FeedbackAndReportTerminalTests(unittest.TestCase):
    def setUp(self):
        from monitoring.bookings import BookingService
        from monitoring.exception_requests import ExceptionRequestService
        from monitoring.feedback import FeedbackService
        from monitoring.models import Role, User
        from monitoring.reports import ReportService
        from monitoring.sqlite_repository import SQLiteScheduleRepository
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = datetime(2026, 10, 1, 8)
        clock = lambda: self.now
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.exceptions = ExceptionRequestService(self.repo, admin_ids=[1], clock=clock)
        self.feedback = FeedbackService(self.repo, clock=clock)
        self.reports = ReportService(self.repo, clock=clock)
        from monitoring.attendance import AttendanceService
        self.attendance = AttendanceService(self.repo, admin_ids=[1], clock=clock)
        self.monitor = User(2, 'Monitor', Role.MONITOR)
        slot = self.schedule.create_slot(self.monitor, 'Calculus', datetime(2026, 10, 5, 14), 1)
        self.booking = self.bookings.book(User(3, 'Aluno', Role.STUDENT), slot.id, 'Derivadas')
        self.now = datetime(2026, 11, 2)

    def execute(self, answers):
        with patch('builtins.input', side_effect=answers), patch('sys.stdout', new_callable=StringIO) as output:
            run(self.schedule, self.bookings, self.exceptions, self.feedback, self.reports, self.attendance)
        return output.getvalue()

    def test_student_rates_and_admin_reads_reports(self):
        self.attendance.mark(self.monitor, self.booking.id, 'PRESENT')
        output = self.execute(['3', '10', '1', '5', 'Muito bom', '11', '0',
                               '1', '12', '2026', '10', '13', '', '0', '0'])
        self.assertIn('Avaliação #1 registrada', output)
        self.assertIn('nota 5 | Muito bom', output)
        self.assertIn('Monitor 2 | atendimentos 1 | horas 0.5 | reservas 1 | presentes 1 | faltas 0 | canceladas 0 | nota média 5.00', output)
        self.assertIn('Calculus | 1x | Derivadas', output)

    def test_permissions_and_invalid_input_recover(self):
        self.attendance.mark(self.monitor, self.booking.id, 'PRESENT')
        output = self.execute(['3',
                               '12', '2026', '10',        # aluno não vê relatório
                               '10', '9', '5', 'x',       # reserva inexistente
                               '10', '1', '9', '',        # nota inválida
                               '0', '0'])
        self.assertIn('Relatórios são exclusivos do ADMIN', output)
        self.assertIn('Reserva inexistente', output)
        self.assertIn('A nota deve ser um inteiro de 1 a 5', output)
        self.assertEqual(self.repo.list_feedback(), [])


class AttendanceTerminalTests(unittest.TestCase):
    def setUp(self):
        from monitoring.attendance import AttendanceService
        from monitoring.bookings import BookingService
        from monitoring.models import Role, User
        from monitoring.sqlite_repository import SQLiteScheduleRepository
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = datetime(2026, 3, 1, 8)
        clock = lambda: self.now
        self.schedule = ScheduleService(self.repo, clock=clock)
        self.bookings = BookingService(self.repo, clock=clock)
        self.attendance = AttendanceService(self.repo, admin_ids=[1], clock=clock)
        slot_ids = []
        for week in range(3):
            slot = self.schedule.create_slot(User(2, 'Monitor', Role.MONITOR), 'Calculus',
                                             datetime(2026, 3, 2, 14) + timedelta(days=7 * week), 1)
            self.bookings.book(User(3, 'Aluno', Role.STUDENT), slot.id, f'Tema {week}')
        self.now = datetime(2026, 4, 1)

    def execute(self, answers):
        with patch('builtins.input', side_effect=answers), patch('sys.stdout', new_callable=StringIO) as output:
            run(self.schedule, self.bookings, None, None, None, self.attendance)
        return output.getvalue()

    def test_monitor_marks_absences_and_third_one_alerts_admin_and_student(self):
        output = self.execute(['2', '14', '1', 'F', '14', '2', 'F', '14', '3', 'F', '14', '0',
                               '1', '6', '0', '3', '6', '15', '0', '0'])
        self.assertEqual(output.count('Falta registrada. Aluno avisado.'), 3)
        self.assertIn('Nenhuma presença a registrar', output)
        self.assertIn('Aluno 3 atingiu 3 faltas no semestre 2026.1', output)   # aviso do ADMIN
        self.assertIn('3ª falta no semestre 2026.1', output)                  # aviso do aluno
        self.assertIn('presença: ABSENT', output)
        self.assertIn('Faltas no semestre: 3', output)

    def test_presence_input_errors_recover(self):
        output = self.execute(['3', '14', '15', '0',               # aluno não registra presença; vê o histórico
                               '2', '14', '1', 'X', '14', '99', 'P', '14', '1', 'P', '0', '0'])
        self.assertIn('Somente o monitor ou o ADMIN registram presença', output)
        self.assertIn('Opção inválida', output)
        self.assertIn('Reserva inexistente', output)
        self.assertIn('Presença registrada.', output)
        self.assertEqual([m.status.value for m in self.repo.list_attendance()], ['PRESENT'])
