from datetime import datetime

from monitoring.models import Role, User
from monitoring.bookings import BookingService
from monitoring.exception_requests import ExceptionRequestService
from monitoring.sqlite_repository import SQLiteScheduleRepository
from monitoring.schedule import ScheduleService


DEMO_USERS = {
    '1': User(1, 'Administrador', Role.ADMIN),
    '2': User(2, 'Monitor', Role.MONITOR),
    '3': User(3, 'Aluno', Role.STUDENT),
}


def run(service: ScheduleService | None = None, bookings: BookingService | None = None,
        exceptions: ExceptionRequestService | None = None) -> None:
    owned_repository = None
    if service is None:
        owned_repository = SQLiteScheduleRepository()
        service = ScheduleService(owned_repository)
        bookings = BookingService(owned_repository)
        exceptions = ExceptionRequestService(
            owned_repository,
            admin_ids=[u.id for u in DEMO_USERS.values() if u.role == Role.ADMIN])
    print('Monitorias — agenda e reservas.')
    print('Seleção de perfis demonstrativa, sem autenticação.')
    try:
        while True:
            print('\n1 ADMIN | 2 MONITOR | 3 STUDENT | 0 Sair')
            choice = input('Usuário: ').strip()
            if choice == '0':
                break
            user = DEMO_USERS.get(choice)
            if user is None:
                print('Opção inválida.')
                continue
            user_menu(service, user, bookings, exceptions)
    except (EOFError, KeyboardInterrupt):
        print('\nEncerrado.')
    finally:
        if owned_repository is not None:
            owned_repository.close()


def user_menu(service: ScheduleService, user: User, bookings: BookingService | None = None,
              exceptions: ExceptionRequestService | None = None) -> None:
    while True:
        print(f'\n{user.name} ({user.role.value})')
        print('1 Publicar vaga | 2 Consultar agenda | 0 Trocar usuário')
        if bookings is not None:
            print('3 Reservar | 4 Minhas reservas | 5 Cancelar reserva | 6 Avisos | 7 Dúvidas da vaga')
        if exceptions is not None:
            print('8 Pedir exceção de cancelamento | 9 Analisar exceções (ADMIN)')
        choice = input('Opção: ').strip()
        if choice == '0':
            return
        try:
            if choice == '1':
                if user.role != Role.MONITOR:
                    print('Somente monitores podem publicar vagas próprias.')
                    continue
                subject = input('Disciplina: ')
                starts_at = datetime.strptime(input('Início (AAAA-MM-DD HH:MM): '), '%Y-%m-%d %H:%M')
                capacity = int(input('Capacidade: '))
                slot = service.create_slot(user, subject, starts_at, capacity)
                print(f'Vaga criada: {slot.id}.')
            elif choice == '2':
                subject = input('Disciplina (vazio para todas): ').strip()
                slots = (bookings.list_available_slots(subject or None) if bookings is not None
                         else service.list_slots(subject or None))
                print('Horários disponíveis.' if bookings is not None else 'Agenda publicada.')
                if not slots:
                    print('Nenhum horário encontrado.')
                for slot in slots:
                    print(f'#{slot.id} | {slot.subject} | monitor {slot.monitor_id} | '
                          f'{slot.starts_at:%Y-%m-%d %H:%M}–{slot.ends_at:%H:%M} | '
                          f'capacidade {slot.capacity}')
            elif bookings is not None and choice == '3':
                slot_id = int(input('Vaga: '))
                question = input('Conteúdo da dúvida: ')
                booking = bookings.book(user, slot_id, question)
                print(f'Reserva criada: {booking.id}.')
            elif bookings is not None and choice == '4':
                items = bookings.list_bookings(user)
                if not items:
                    print('Nenhuma reserva encontrada.')
                for booking in items:
                    print(f'#{booking.id} | vaga {booking.slot_id} | {booking.status} | {booking.question}')
            elif bookings is not None and choice == '5':
                booking_id = int(input('Reserva: '))
                reason = input('Motivo (obrigatório para exceção ADMIN): ')
                bookings.cancel(user, booking_id, reason)
                print('Reserva cancelada. Avisos registrados.')
            elif bookings is not None and choice == '6':
                notices = bookings.repository.list_notifications(user.id)
                if not notices:
                    print('Nenhum aviso.')
                for notice in notices:
                    print(f'{notice.created_at:%Y-%m-%d %H:%M} | {notice.message}')
            elif bookings is not None and choice == '7':
                for question in bookings.list_questions(user, int(input('Vaga: '))):
                    print(question)
            elif exceptions is not None and choice == '8':
                if user.role == Role.ADMIN:
                    print('O ADMIN cancela direto com justificativa; não pede exceção.')
                    continue
                for booking in bookings.list_bookings(user):
                    if booking.status == 'ACTIVE':
                        print(f'#{booking.id} | vaga {booking.slot_id} | {booking.question}')
                booking_id = int(input('Reserva: '))
                request = exceptions.request(user, booking_id, input('Motivo: '))
                print(f'Solicitação #{request.id} enviada ao ADMIN.')
            elif exceptions is not None and choice == '9':
                pending = exceptions.list_pending(user)
                if not pending:
                    print('Nenhuma solicitação pendente.')
                    continue
                for request in pending:
                    print(f'#{request.id} | reserva {request.booking_id} | '
                          f'solicitante {request.requester_id} | {request.reason}')
                request_id = int(input('Solicitação (0 para voltar): '))
                if request_id == 0:
                    continue
                decision = input('A aprovar / R recusar: ').strip().upper()
                note = input('Observação: ')
                if decision == 'A':
                    exceptions.approve(user, request_id, note)
                    print('Exceção aprovada.')
                elif decision == 'R':
                    exceptions.reject(user, request_id, note)
                    print('Exceção recusada.')
                else:
                    print('Opção inválida.')
            else:
                print('Opção inválida.')
        except (ValueError, PermissionError) as error:
            print(f'Erro: {error}')
