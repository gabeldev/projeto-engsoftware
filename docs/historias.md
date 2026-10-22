# Histórias de usuário

## H1 — Reservar atendimento — Alta (escolhida)

Como aluno, quero escolher uma disciplina, consultar horários livres e reservar
uma monitoria de 30 minutos, para organizar meu atendimento sem combinar por mensagem.

Justificativa: é o fluxo central, depende de capacidade consistente e fundamenta os demais.

Trecho: “A ideia é que o aluno escolha a disciplina, veja os horários livres e reserve um atendimento.”

1. CA1: listar apenas vagas futuras da disciplina escolhida com capacidade restante.
2. CA2: gravar a reserva e consumir uma posição da capacidade da vaga.
3. CA3: recusar vaga lotada ou inexistente sem gravar reserva.
4. CA4: exigir o conteúdo da dúvida e permitir sua consulta pelos alunos da mesma vaga.
5. CA5: limitar a duas reservas ativas por aluno/disciplina/semana, com limite configurável;
   semanas de segunda a domingo, cancelamento libera a posição e o limite.

Rastreabilidade: `tests/test_criteria.py` cobre sucesso e falha de CA1–CA5;
`tests/test_bookings.py` cobre persistência e concorrência.

## H2 — Organizar agenda e atendimentos em grupo — Alta

Como monitor, quero publicar vagas por disciplina e definir capacidade individual
ou coletiva, para organizar os atendimentos e reunir alunos com dúvidas relacionadas.

Justificativa: disponibilizar vagas é pré-requisito para reservas.

Trecho: “Cada atendimento dura 30 minutos, mas alguns monitores preferem atender em grupo”.

1. Somente MONITOR publica vagas próprias, com disciplina não vazia e início futuro.
2. Toda vaga dura 30 minutos e possui capacidade inteira positiva.
3. Recusar sobreposição de vagas do mesmo monitor, inclusive em disciplinas diferentes.
4. Permitir horários adjacentes e horários simultâneos de monitores diferentes.
5. O monitor responsável pode consultar as dúvidas dos alunos de suas vagas.

Rastreabilidade: `tests/test_schedule.py`, `tests/test_permissions.py` e `tests/test_bookings.py`.

## H3 — Acompanhar resultados e horas — Média

Como ADMIN, quero consultar histórico, dúvidas agrupadas, avaliações e horas
mensais por monitor, para orientar melhorias e apoiar o acompanhamento das bolsas.

Justificativa: usa os registros de atendimentos e exige restrição das informações de bolsa.

Trecho: “A coordenação precisa de um relatório mensal com as horas atendidas por cada monitor”.

1. Restringir relatórios mensais de horas e agrupamento de dúvidas ao ADMIN.
2. Contar 0,5 hora por vaga encerrada com pelo menos um aluno presente, sem multiplicar pelo grupo.
3. Agrupar dúvidas das reservas ativas por disciplina e conteúdo, normalizando caixa e espaços.
4. Aluno com presença pode avaliar uma vez após o fim, com nota inteira de 1 a 5.
5. Aluno vê seu histórico e avaliações; monitor vê os de suas vagas; ADMIN vê todos.

Rastreabilidade: `tests/test_reports.py`, `tests/test_feedback.py`,
`tests/test_attendance.py` e `tests/test_permissions.py`.

## H4 — Registrar presença e avisar faltas — Média

Como monitor, quero registrar presença ou falta e gerar avisos, para reduzir
horários perdidos sem bloquear automaticamente os alunos.

Justificativa: responsabiliza pelas ausências sem adotar bloqueio não consensual.

Trecho: “Quando o aluno reserva e não aparece, o horário fica perdido.”

1. Apenas monitor da vaga ou ADMIN registra presença após o início do atendimento.
2. Cada reserva ativa recebe uma única marcação; canceladas não recebem presença.
3. Cada falta gera aviso interno ao aluno.
4. A terceira falta no semestre gera aviso adicional ao aluno e ao ADMIN.
5. Somar faltas entre disciplinas e reiniciar a contagem a cada semestre civil.

Rastreabilidade: `tests/test_attendance.py` e `tests/test_cli.py`.

## H5 — Cancelar com transparência — Alta

Como aluno ou monitor responsável, quero cancelar uma reserva com aviso aos
envolvidos e pedir exceção quando necessário, para evitar deslocamentos sem atendimento.

Justificativa: cancelamentos inesperados geram conflito e exigem uma regra clara.

Trecho: “Os alunos reclamam que só descobrem o cancelamento quando chegam na sala.”

1. Aluno cancela sua reserva; monitor cancela reservas de suas vagas, com antecedência mínima de 72 horas.
2. Dentro das 72 horas, aluno ou monitor pode pedir exceção com motivo ao ADMIN.
3. Apenas ADMIN aprova ou recusa uma única vez; recusa exige justificativa.
4. Exceção aprovada permite cancelar antes do início; ADMIN pode cancelar diretamente com justificativa fora do prazo.
5. Preservar o registro cancelado, liberar capacidade e registrar avisos internos aos envolvidos.

Rastreabilidade: `tests/test_exceptions.py`, `tests/test_bookings.py` e `tests/test_cli.py`.
