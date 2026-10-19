# Perfis e agenda — Gabriel

Aplicação de terminal em Python 3.10+, sem dependências externas. Identificadores
em inglês; instruções e mensagens para o usuário em português.

## Escopo e decisões
- `Role`: ADMIN, MONITOR e STUDENT. `User`: id, name e role.
- `AppointmentSlot`: id, monitor_id, subject, starts_at e capacity; ends_at
  calculado com duração fixa de 30 minutos.
- `ScheduleService`: apenas MONITOR publica vagas próprias; todos os perfis
  podem consultar a agenda. Recusa horários passados, capacidade inválida,
  disciplina vazia e sobreposição para o mesmo monitor.
- Horários locais sem fuso, com precisão de minuto. Intervalos adjacentes são válidos.
- `ScheduleRepository` define o contrato; `InMemoryScheduleRepository` permite
  executar a parte de Gabriel antes da implementação SQLite de Ives.
- Selecionar usuário no terminal é uma simulação de perfil, sem autenticação.
- Banco, reservas, lotação e limite semanal ficam com Ives. Consulta de agenda
  nesta etapa não garante vaga restante, pois ainda não existem reservas.

## Execução
1. Escrever e executar testes das permissões, validações, consultas e conflitos.
2. Implementar modelos, contrato e serviço até os testes passarem.
3. Adicionar menu para selecionar usuário, publicar vaga e consultar disciplina.
4. Documentar execução e contrato de integração; verificar testes e fluxo terminal.

## Integração
`SQLiteScheduleRepository` será implementado com os métodos de
`ScheduleRepository`, preservando ids, tipos e ordenação do serviço.
Reservas devem conter `student_id`, `slot_id`, `question` e `created_at`.
O futuro `BookingService.book(student, slot_id, question)` validará perfil,
conteúdo obrigatório, capacidade e limite configurável (padrão 2 por
aluno/disciplina por semana, segunda a domingo). Validação e gravação devem
ser atômicas para evitar reservas acima da capacidade.
