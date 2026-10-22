# Agendamento de monitorias

Aplicação de terminal em Python 3.10+, com SQLite e testes `unittest`.
Não requer pacotes externos.

## Executar

Na raiz do projeto:

```bash
python3 -m monitoring
```

O banco `monitoring.sqlite3` é criado no diretório atual e preservado ao sair.
A seleção de perfis é demonstrativa, sem login ou autenticação real.
Datas usam `AAAA-MM-DD HH:MM`, no horário local, sem fuso.

- MONITOR publica vagas próprias de 30 minutos, com disciplina e capacidade.
- A consulta mostra horários futuros com capacidade restante.
- STUDENT reserva informando o id da vaga e o conteúdo da dúvida.
- Minhas reservas mostra os registros autorizados para cada perfil, inclusive cancelados.
- Cancelar reserva exige pelo menos 72 horas de antecedência. Alunos cancelam
  reservas próprias; monitores cancelam reservas de suas vagas. Fora do prazo,
  ADMIN pode cancelar um atendimento futuro com justificativa obrigatória.
- Pedir exceção (aluno da reserva ou monitor da vaga): dentro das 72 horas, o pedido com motivo vai para o ADMIN. Analisar exceções (ADMIN) aprova ou recusa uma única vez; recusar exige justificativa. Com a exceção aprovada, quem pediu consegue cancelar a reserva normalmente (opção 5).
- Avisos mostra as notificações internas de cancelamento e de exceções.
- Avaliar atendimento (STUDENT, opção 10): nota de 1 a 5 e comentário opcional, uma vez por
  reserva, só se compareceu e depois que o atendimento terminou. Ver avaliações (opção 11): aluno vê as suas,
  monitor as das suas vagas, ADMIN todas.
- Registrar presença (opção 14, monitor da vaga ou ADMIN): marca P (presente) ou F (faltou) para
  reservas ativas de atendimentos já iniciados; cada reserva recebe uma única marcação. A falta
  avisa o aluno; a terceira falta no semestre (1º: jan–jun, 2º: jul–dez, somando as disciplinas)
  avisa também o ADMIN e reforça o aviso ao aluno.
- Histórico e faltas (opção 15): reservas com a presença de cada uma, inclusive canceladas. Aluno
  vê o próprio histórico e o total de faltas do semestre; monitor vê o das suas vagas; ADMIN vê
  todos e pode filtrar por aluno.
- Relatório mensal de horas (ADMIN, opção 12): por monitor, atendimentos realizados no mês,
  horas (0,5 h cada), reservas, presentes, faltas, cancelamentos e nota média. Só conta vaga que já terminou e
  teve ao menos um aluno presente.
- Dúvidas por disciplina (ADMIN, opção 13): conteúdos agrupados e contados, mais frequentes
  primeiro, para repassar aos professores.
- Dúvidas da vaga permite consultar os conteúdos aos participantes ativos,
  ao monitor responsável e ao ADMIN.

Cada aluno pode manter até duas reservas ativas por disciplina na mesma semana
(segunda a domingo). O limite pode ser configurado no construtor de
`BookingService(weekly_limit=...)`. Reservas canceladas deixam de consumir
capacidade e limite. Reservas duplicadas ativas são recusadas.

## Testar

```bash
python3 -m unittest discover -v
```

A suíte usa bancos temporários e em memória, sem alterar o banco da aplicação.
Inclui reabertura de banco, disputa por uma única vaga, permissões, limite semanal,
fronteira das 72 horas, avisos e fluxo completo no terminal.

## Estrutura

| Arquivo | Responsabilidade |
| --- | --- |
| `monitoring/models.py` | Perfis, usuários, vagas, reservas e avisos |
| `monitoring/schedule.py` | Publicação de vagas, conflitos e agenda |
| `monitoring/repository.py` | Contrato de agenda e adaptador em memória |
| `monitoring/sqlite_repository.py` | SQL, persistência e transações |
| `monitoring/bookings.py` | Reservas, limites, cancelamentos e acesso às dúvidas |
| `monitoring/exception_requests.py` | Pedido e análise (ADMIN) de exceções à regra das 72 h |
| `monitoring/attendance.py` | Presença, faltas por semestre, avisos e histórico |
| `monitoring/feedback.py` | Avaliação dos atendimentos pelos alunos |
| `monitoring/reports.py` | Relatório mensal de horas e dúvidas agrupadas (ADMIN) |
| `monitoring/errors.py` | Erros de solicitação duplicada/já analisada e exceção desnecessária |
| `monitoring/cli.py` | Menus e entrada/saída do terminal |
| `tests/` | Regras e integração |

Validação e gravação de reservas/cancelamentos usam transações `BEGIN IMMEDIATE`.
Cancelamentos preservam o histórico e salvam os avisos na mesma transação.
A agenda base consulta horários publicados; `BookingService.list_available_slots`
aplica o filtro de capacidade restante.

A presença registrada não pode ser alterada. Os avisos são internos, sem envio por e-mail.

Documentação: [decisões iniciais](docs/implementation-plan.md) e
[reservas e cancelamentos](docs/booking-plan.md) e
[cobertura dos testes](docs/testes.md).
