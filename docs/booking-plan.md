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
