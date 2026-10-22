# Agendamento de monitorias — Parte 1

Gabriel Oliveira de Jesus e Ives Yudy Omura Maruiti

## Descrição da solução

Planejamos em conjunto um sistema em Python com SQLite e três perfis: ADMIN,
monitor e aluno. Cada monitoria dura 30 minutos, com capacidade individual ou
coletiva. Adotamos limite semanal ajustável, inicialmente duas reservas por
aluno e disciplina, cancelamento com antecedência mínima de 72 horas e
exceções analisadas pelo ADMIN, com avisos internos aos envolvidos.

Incluímos histórico, presença e avaliação dos atendimentos. Faltas geram avisos;
a terceira no semestre é comunicada ao ADMIN e ao aluno. Agrupamos dúvidas para
apoiar os professores e restringimos o relatório mensal de horas ao ADMIN.

## Plano de execução conjunto

16/10: analisar as necessidades, definir a solução e preparar o plano da Parte 1.

16/10: criar o repositório e definir cinco histórias, prioridades, justificativas,
trechos da demanda e critérios; selecionar uma história de alta prioridade.

17/10: registrar o projeto inicial textual, responsabilidades das classes e testes
por critério antes da implementação.

18/10: implementar perfis, SQLite, disponibilidades, vagas e reservas com limite semanal.

19/10: implementar cancelamentos, análise de exceções e avisos internos.

20/10: implementar histórico, presença, avisos por faltas, avaliações,
dúvidas agrupadas e relatório mensal restrito.

21/10: concluir testes unittest, verificar permissões e corrigir falhas.

22/10: finalizar o PDF com projeto inicial, relatório de até uma página e
documentação, preparar o ZIP, extrair e executar em outra pasta e entregar até 23h50.

Realizamos o trabalho em conjunto. Este documento apresenta o planejamento da
Parte 1 com autoria conjunta; o relatório de execução registra os ajustes e
as datas efetivas de versionamento.
