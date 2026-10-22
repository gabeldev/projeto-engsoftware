"""Um teste de sucesso e um de falha para cada critério de aceitação (Escopo_inicial.md).

Na saída detalhada (`-v`) cada teste aparece com o nome do escopo, em Teste_*.
"""
import unittest
from datetime import datetime, timedelta

from monitoring.bookings import BookingService
from monitoring.models import Role, User
from monitoring.schedule import PermissionDeniedError, ScheduleService
from monitoring.sqlite_repository import SQLiteScheduleRepository

NOW = datetime(2026, 10, 19, 10)  # segunda-feira


class AcceptanceCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteScheduleRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.monitor = User(2, 'Monitor', Role.MONITOR)
        self.students = [User(10 + i, f'Aluno {i}', Role.STUDENT) for i in range(4)]
        self.schedule = ScheduleService(self.repo, clock=lambda: NOW)
        self.service = BookingService(self.repo, clock=lambda: NOW)
        self.start = NOW + timedelta(days=4)  # sexta, mesma semana de todos os slots abaixo

    def slot(self, subject='Calculus', minutes=0, capacity=2):
        return self.schedule.create_slot(self.monitor, subject,
                                         self.start + timedelta(minutes=minutes), capacity)

    # CA1 — lista só horários com vaga da disciplina escolhida
    def test_lista_disponivel(self):
        """Teste_Lista_Disponivel (CA1)"""
        free, full = self.slot(capacity=2), self.slot(minutes=30, capacity=1)
        self.slot('Physics', minutes=60)
        self.service.book(self.students[0], full.id, 'Limites')
        self.assertEqual(self.service.list_available_slots('Calculus'), [free])

    def test_lista_vazia(self):
        """Teste_Lista_Vazia (CA1, falha)"""
        self.assertEqual(self.service.list_available_slots('Calculus'), [])
        only = self.slot(capacity=1)
        self.service.book(self.students[0], only.id, 'Limites')
        self.assertEqual(self.service.list_available_slots('Calculus'), [])
        self.assertEqual(self.service.list_available_slots('Chemistry'), [])

    # CA2 — a reserva é registrada e consome uma posição
    def test_consome_vaga(self):
        """Teste_Consome_Vaga (CA2)"""
        slot = self.slot(capacity=2)
        booking = self.service.book(self.students[0], slot.id, 'Derivadas')
        self.assertEqual((booking.student_id, booking.slot_id, booking.status),
                         (self.students[0].id, slot.id, 'ACTIVE'))
        self.assertEqual(self.service.list_bookings(self.students[0]), [booking])
        self.assertEqual(self.service.list_available_slots('Calculus'), [slot])  # sobrou 1
        self.service.book(self.students[1], slot.id, 'Derivadas')
        self.assertEqual(self.service.list_available_slots('Calculus'), [])  # esgotou

    def test_consumo_inexistente(self):
        """Teste_Consumo_Inexistente (CA2, falha)"""
        with self.assertRaisesRegex(ValueError, 'Vaga inexistente'):
            self.service.book(self.students[0], 999, 'Derivadas')
        self.assertEqual(self.repo.list_bookings(), [])

    # CA3 — recusa de horário lotado, com erro claro
    def test_recusa_reserva(self):
        """Teste_Recusa_Reserva (CA3)"""
        slot = self.slot(capacity=1)
        self.service.book(self.students[0], slot.id, 'Limites')
        with self.assertRaisesRegex(ValueError, 'lotada'):
            self.service.book(self.students[1], slot.id, 'Limites')

    def test_erro_reserva(self):
        """Teste_Erro_Reserva (CA3, falha)"""
        slot = self.slot(capacity=1)
        first = self.service.book(self.students[0], slot.id, 'Limites')
        with self.assertRaises(ValueError):
            self.service.book(self.students[1], slot.id, 'Limites')
        self.assertEqual([b.id for b in self.repo.list_bookings()], [first.id])  # nada gravado
        self.service.cancel(self.students[0], first.id)  # cancelar libera o lugar
        self.assertEqual(self.service.book(self.students[1], slot.id, 'Limites').slot_id, slot.id)

    # CA4 — ementa obrigatória e visível aos alunos da mesma vaga
    def test_ementa_feita(self):
        """Teste_Ementa_Feita (CA4)"""
        slot = self.slot(capacity=3)
        self.service.book(self.students[0], slot.id, '  Derivadas ')
        self.service.book(self.students[1], slot.id, 'Integrais')
        self.assertEqual(self.service.list_questions(self.students[0], slot.id),
                         ['Derivadas', 'Integrais'])
        self.assertEqual(self.service.list_questions(self.students[1], slot.id),
                         ['Derivadas', 'Integrais'])

    def test_sem_ementa(self):
        """Teste_Sem_Ementa (CA4, falha)"""
        slot = self.slot(capacity=3)
        for question in ('', '   ', None):
            with self.subTest(question=question), self.assertRaisesRegex(ValueError, 'conteúdo'):
                self.service.book(self.students[0], slot.id, question)
        self.assertEqual(self.repo.list_bookings(), [])
        self.service.book(self.students[1], slot.id, 'Integrais')
        with self.assertRaises(PermissionDeniedError):  # quem não está na vaga não vê
            self.service.list_questions(self.students[2], slot.id)

    # CA5 — limite semanal configurável
    def test_limite_semanal(self):
        """Teste_Limite_Semanal (CA5)"""
        slots = [self.slot(minutes=30 * i) for i in range(3)]
        for slot in slots[:2]:
            self.service.book(self.students[0], slot.id, 'Limites')
        with self.assertRaisesRegex(ValueError, 'Limite semanal'):
            self.service.book(self.students[0], slots[2].id, 'Limites')

    def test_limite_semanal_aceita_outra_semana_ou_disciplina(self):
        """Teste_Limite_Semanal_Aceita (CA5, sucesso)"""
        slots = [self.slot(minutes=30 * i) for i in range(2)]
        physics = self.slot('Physics', minutes=90)
        next_week = self.schedule.create_slot(self.monitor, 'Calculus', datetime(2026, 10, 26, 9), 2)
        for slot in slots:
            self.service.book(self.students[0], slot.id, 'Limites')
        self.assertEqual(self.service.book(self.students[0], physics.id, 'Força').slot_id, physics.id)
        self.assertEqual(self.service.book(self.students[0], next_week.id, 'Séries').slot_id, next_week.id)


if __name__ == '__main__':
    unittest.main()
