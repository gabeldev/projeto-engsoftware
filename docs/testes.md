# Cobertura dos testes

Execução: `python -m unittest discover -v` (todos usam SQLite em memória ou arquivo temporário).

## Critérios de aceitação

| Critério | Sucesso | Falha/exceção | Arquivo |
| --- | --- | --- | --- |
| CA1 Lista só vagas livres da disciplina | `Teste_Lista_Disponivel` | `Teste_Lista_Vazia` | `tests/test_criteria.py` |
| CA2 Reserva registrada e consome vaga | `Teste_Consome_Vaga` | `Teste_Consumo_Inexistente` | `tests/test_criteria.py` |
| CA3 Recusa de vaga lotada | `Teste_Recusa_Reserva` | `Teste_Erro_Reserva` | `tests/test_criteria.py` |
| CA4 Ementa obrigatória e visível na vaga | `Teste_Ementa_Feita` | `Teste_Sem_Ementa` | `tests/test_criteria.py` |
| CA5 Limite semanal configurável | `Teste_Limite_Semanal_Aceita` | `Teste_Limite_Semanal` | `tests/test_criteria.py` |

Na saída com `-v`, cada teste aparece com o nome do escopo.

## Demais regras

| Regra | Arquivo |
| --- | --- |
| Agenda, conflitos e perfis | `tests/test_schedule.py` |
| Reservas, cancelamento (72 h), concorrência e persistência | `tests/test_bookings.py` |
| Exceções de cancelamento e avisos | `tests/test_exceptions.py` |
| Presença, faltas por semestre, avisos e histórico | `tests/test_attendance.py` |
| Feedback dos alunos | `tests/test_feedback.py` |
| Relatório mensal de horas e dúvidas agrupadas | `tests/test_reports.py` |
| Matriz de permissões: cada operação × cada perfil | `tests/test_permissions.py` |
| Fluxos do terminal | `tests/test_cli.py` |

## Permissões verificadas

`tests/test_permissions.py` executa cada operação com os cinco usuários (ADMIN, dois
monitores, dois alunos): quem deve ser barrado precisa receber `PermissionDeniedError`
e a tentativa não pode deixar vaga, reserva, solicitação ou avaliação gravada; quem pode
tentar não pode ser barrado por permissão. Também confere o que cada perfil enxerga em
reservas e avaliações.
