# Documentação final

## Execução e ambiente

Python 3.10 ou superior; SQLite e unittest da biblioteca padrão. Não é necessário
instalar dependências. Na pasta do projeto, execute `python3 -m monitoring`.
Para testes: `python3 -m unittest discover -v`. O banco `monitoring.sqlite3`
é criado no diretório atual. Excluir esse arquivo remove os dados da demonstração.

## Roteiro de uso

Selecione 2 (MONITOR), opção 1, informe disciplina, data futura no formato
AAAA-MM-DD HH:MM e capacidade. Volte com 0 e selecione 3 (STUDENT).
Consulte a agenda (2), reserve pelo id (3) e informe a dúvida. Consulte suas
reservas (4), dúvidas da vaga (7) e avisos (6). Cancele pela opção 5.
Com menos de 72 horas, peça exceção (8); ADMIN analisa pela opção 9.
A aprovação permite ao interessado efetuar o cancelamento pela opção 5.

Após o início, o monitor registra presença/falta (14). O histórico fica em 15.
Depois do término, aluno presente avalia em 10; avaliações são consultadas em 11.
ADMIN consulta horas mensais em 12 e dúvidas agrupadas em 13. Para demonstrar
presença sem esperar, use os cenários com relógio controlado dos testes; o menu
não permite criar vaga passada nem manipular o relógio.

## Arquitetura e dados

`models.py` define usuários, perfis, vagas, reservas, avisos, pedidos de exceção,
avaliações e presença. `schedule.py` trata agenda e conflitos; `bookings.py`
trata capacidade, limites e cancelamento. Serviços separados cuidam de exceções,
presença, feedback e relatórios. `sqlite_repository.py` é a única camada SQL.
`cli.py` cuida dos menus. Não há serviços externos ou credenciais necessárias.

Tabelas: slots, bookings, notifications, exception_requests, feedback e attendance.
Reservas referenciam vagas; presença e avaliação são únicas por reserva.
Índices restringem reserva ativa duplicada e pedidos de exceção abertos.
Transações BEGIN IMMEDIATE protegem alterações de reserva e cancelamento.
Cancelados permanecem no histórico; vagas de grupo contam uma vez nas horas.

## Verificação e limites

A suíte tem 90 testes; veja docs/testes.md para a cobertura por critério.
A seleção de usuário simula os três perfis e não é login seguro. Os usuários
demonstrativos têm ids fixos; não há cadastro ou dados de contato. O histórico
registra atendimentos e presença, sem medir desempenho acadêmico. Feedback é
do aluno sobre o atendimento. Avisos não são enviados por e-mail. A interface
é de terminal, sem versão móvel. Conferimos a entrega com base nos documentos de requisitos e no plano de execução.

Mantivemos o escopo inicial como registro da concepção anterior
à implementação, ajustando as referências de autoria para refletir o trabalho conjunto. Expressões como “futuro” nesse arquivo descrevem aquele momento;
a situação atual está no README e neste documento. O relatório de execução
explica os refinamentos sem reescrever o registro original.
