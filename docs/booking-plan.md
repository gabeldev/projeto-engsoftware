# Persistência, reservas e cancelamentos

SQLite mantém vagas e reservas; transações IMMEDIATE serializam validação e
alteração de capacidade. Reservas exigem perfil STUDENT e dúvida preenchida,
respeitam capacidade e limite configurável (padrão 2 por disciplina/semana).
Somente reservas ativas contam para esses limites. A semana vai de segunda a domingo.

Aluno pode cancelar a própria reserva com pelo menos 72 horas de antecedência.
Monitor pode cancelar reservas de suas próprias vagas com a mesma antecedência.
ADMIN pode autorizar cancelamentos fora do prazo, registrando justificativa.
Cancelamentos não apagam histórico e geram avisos internos para aluno e monitor.
O terminal lista reservas e permite reservar/cancelar; banco padrão monitoring.sqlite3.
A seleção de perfis continua demonstrativa, sem autenticação.

Testar em SQLite em memória: capacidade, duplicidade, limites, dúvida obrigatória,
permissões, fronteira de 72 horas, exceção ADMIN, avisos e persistência após reabrir.

## Feedback e relatórios (ADMIN)

Feedback: nota inteira de 1 a 5 e comentário opcional (até 500 caracteres), gravado
na tabela `feedback` com uma avaliação por reserva (`UNIQUE`). Só o aluno da reserva avalia,
se foi marcado como presente, e só depois do fim do atendimento (início + 30 min); reservas canceladas não são avaliadas.
Monitor vê as avaliações das suas vagas; ADMIN vê todas.

Relatório mensal de horas: para cada monitor com vaga terminada no mês, conta os
atendimentos (vaga terminada com ao menos um aluno presente), as horas (0,5 h por
atendimento), reservas ativas, canceladas e a nota média. Vaga sem reserva ou sem presença registrada não gera hora.
Exclusivo do ADMIN. Dúvidas por disciplina: agrupa por disciplina e conteúdo (sem diferenciar
maiúsculas ou espaços), só reservas ativas, ordenadas da mais frequente para a menos.

## Presença, faltas e histórico

Tabela `attendance`: uma marcação por reserva (`UNIQUE`), `PRESENT` ou `ABSENT`, com quem marcou
e quando. Só o monitor da vaga ou o ADMIN marcam, em reservas ativas, a partir do início do
atendimento; a marcação não é alterada depois. Cada falta avisa o aluno. A terceira falta no
semestre (1º: janeiro a junho; 2º: julho a dezembro; todas as disciplinas somadas, pela data da vaga)
avisa o aluno e todos os ADMINs informados; da quarta em diante só vai o aviso comum de falta.
O histórico lista as reservas (também canceladas) com a presença; aluno só vê as próprias,
monitor as das suas vagas, ADMIN todas. Banco criado antes desta versão continua válido: a tabela
nova é criada na primeira execução.
