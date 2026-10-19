from datetime import datetime

from monitoring.models import Role, User
from monitoring.repository import InMemoryScheduleRepository
from monitoring.schedule import ScheduleService


DEMO_USERS = {
    '1': User(1, 'Administrador', Role.ADMIN),
    '2': User(2, 'Monitor', Role.MONITOR),
    '3': User(3, 'Aluno', Role.STUDENT),
}


def run(service: ScheduleService | None = None) -> None:
    if service is None:
        service = ScheduleService(InMemoryScheduleRepository())
    print('Monitorias — demonstração em memória (dados perdidos ao sair).')
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
            user_menu(service, user)
    except (EOFError, KeyboardInterrupt):
        print('\nEncerrado.')


def user_menu(service: ScheduleService, user: User) -> None:
    while True:
        print(f'\n{user.name} ({user.role.value})')
        print('1 Publicar vaga | 2 Consultar agenda | 0 Trocar usuário')
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
                slots = service.list_slots(subject or None)
                print('Agenda publicada; ocupação por reservas ainda não implementada.')
                if not slots:
                    print('Nenhum horário encontrado.')
                for slot in slots:
                    print(f'#{slot.id} | {slot.subject} | monitor {slot.monitor_id} | '
                          f'{slot.starts_at:%Y-%m-%d %H:%M}–{slot.ends_at:%H:%M} | '
                          f'capacidade {slot.capacity}')
            else:
                print('Opção inválida.')
        except (ValueError, PermissionError) as error:
            print(f'Erro: {error}')
