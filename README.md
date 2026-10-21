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
- Avisos mostra as notificações internas de cancelamento para aluno e monitor.
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
| `monitoring/cli.py` | Menus e entrada/saída do terminal |
| `tests/` | Regras e integração |

Validação e gravação de reservas/cancelamentos usam transações `BEGIN IMMEDIATE`.
Cancelamentos preservam o histórico e salvam os avisos na mesma transação.
A agenda base consulta horários publicados; `BookingService.list_available_slots`
aplica o filtro de capacidade restante.

Histórico de presença, penalidades por faltas, feedback e relatórios de bolsas
continuam fora desta versão. Os avisos são internos, sem envio por e-mail.

Documentação: [decisões iniciais](docs/implementation-plan.md) e
[reservas e cancelamentos](docs/booking-plan.md).
