# Relatório de execução

Gabriel Oliveira de Jesus e Ives Yudy Omura Maruiti — 22/10/2026

Implementamos em conjunto uma aplicação de terminal em Python com SQLite, organizada em
modelos, serviços de regras de negócio, repositório e interface. A solução contempla
agenda, reservas individuais ou coletivas, limite semanal, cancelamentos, exceções
analisadas pelo ADMIN, avisos internos, histórico, presença, faltas, avaliações,
dúvidas agrupadas e relatório mensal de horas restrito ao ADMIN.

Ajustamos o cronograma durante a execução. O plano da Parte 1 tem data de
16/10; versionamos o escopo inicial em 18/10, antes do primeiro código de
perfis e agenda. Registramos a integração de reservas persistentes e cancelamentos
em 21/10, assim como as exceções e os recursos previstos para 20/10.
Portanto, consolidamos parte da implementação depois das datas planejadas.
Usamos as datas dos commits como referência de registro, sem confundi-las com o
início de cada atividade. Preparamos a documentação final e realizamos a conferência
em 22/10. Acrescentamos as cinco histórias detalhadas nesta etapa.

Refinamos os nomes do projeto inicial para inglês e a dúvida passou a
pertencer à reserva. O limite semanal tornou-se um critério separado (CA5).
As regras recebem parâmetros; entrada e saída ficam no terminal. Reservas e
cancelamentos usam transações para manter capacidade, histórico e avisos consistentes.
A presença passou a fundamentar o cálculo de horas e a permissão de avaliar.

Executamos os 90 testes unittest com sucesso na conferência local, abrangendo os critérios
de aceitação, permissões, persistência, concorrência, cancelamento, exceções,
presença, feedback, relatórios e fluxos do terminal. A entrega inclui o código,
testes, documentos editáveis, PDF consolidado e o plano da Parte 1. A seleção
de perfis é demonstrativa, sem autenticação real; avisos são internos. As datas
usam horário local sem fuso. Preservamos o projeto inicial como registro histórico, com referências à autoria
conjunta, e distinguimos suas previsões do estado final.
