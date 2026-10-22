**História escolhida (Alta):** Como aluno, eu quero escolher uma disciplina, ver os horários livres e reservar um atendimento de 30 minutos, para não combinar por mensagem nem chegar e encontrar o monitor ocupado ou ausente.

**Critérios de aceitação**

1. Ao escolher uma disciplina, o sistema lista apenas os horários com vaga disponível do monitor daquela disciplina.  
   “A ideia é que o aluno escolha a disciplina, veja os horários livres e reserve um atendimento “  
   
2. Ao reservar um horário livre, a reserva é registrada e consome uma posição da vaga; a capacidade da vaga é definida pelo monitor (1 \= individual, maior que 1 \= grupo).   
   “Cada atendimento dura 30 minutos, mas alguns monitores preferem atender em grupo, quando várias pessoas têm a mesma dúvida. “  
   “Na semana passada, um monitor de Cálculo tinha três alunos marcados no mesmo horário, enquanto outros passaram a tarde inteira sem ninguém. “  

3. O sistema recusa a reserva de um horário sem vaga restante (lotado), com erro claro.  
   “Isso tem gerado confusão. Na semana passada, um monitor de Cálculo tinha três alunos marcados no mesmo horário, enquanto outros passaram a tarde inteira sem ninguém. “  

4. Ao reservar, o aluno informa o conteúdo (ementa) da dúvida; a reserva sem conteúdo é recusada, e o conteúdo fica visível aos demais alunos da mesma vaga. 

	“Os professores das disciplinas gostariam de saber quais conteúdos geram mais dúvidas, para reforçar em aula. “

“...mas alguns monitores preferem atender em grupo, quando várias pessoas têm a mesma dúvida. “

**Funções e classes e suas responsabilidades**

* **Vaga:** representa um horário de 30 min de um monitor, com disciplina, início, ementa e  capacidade (1 para individual, mais de 1 para grupo).  
* **Reserva:** liga um aluno a uma vaga e guarda a data da reserva.  
* **RepositorioAgendamento:** única parte que fala com o SQLite. Cria as tabelas, grava e consulta vagas e reservas. Os testes usam banco de memória.  
* **ServicoAgendamento:** concentra as regras de negócio.

`listar_horarios_livres(disciplina)`: devolve só vagas com capacidade ainda não esgotada (CA1).

valida as regras e registra a reserva (`reservar(aluno, vaga)`CA2).

Auxiliar que conta as reservas do aluno na disciplina dentro da semana da vaga, usada para aplicar o limite (CA4).

* **Erros próprios:** vaga inexistente, vaga lotada e limite semanal excedido, falta de resposta do monitor. Os testes de falha verificam essas exceções.

Nenhuma função lê dados digitados: tudo recebe parâmetros, então os testes chamam direto (requisito mínimo 3).

**Nomenclatura dos testes que verifica cada critério :**

1. Teste\_Lista\_Disponivel   
2. Teste\_Consome\_Vaga  
3. Teste\_Recusa\_Reserva  
4. Teste\_Ementa\_Feita

**Nomenclatura das Falha/exceção dos critérios:**

1. Teste\_Lista\_Vazia  
2. Teste\_Consumo\_Inexistente  
3. Teste\_Erro\_Reserva  
4. Teste\_Sem\_Ementa

   

 



## Refinamento antes da integração — 18/10/2026

Os nomes da implementação serão em inglês. As definições abaixo corrigem as
ambiguidades das responsabilidades descritas acima:

- `User` e `Role`: usuário e perfil (`ADMIN`, `MONITOR`, `STUDENT`).
- `AppointmentSlot`: vaga de 30 minutos, monitor, disciplina, início e capacidade.
  O conteúdo da dúvida não pertence à vaga.
- `Booking`: reserva com aluno, vaga, conteúdo obrigatório da dúvida (`question`)
  e data de criação. O conteúdo será consultável pelos alunos da mesma vaga.
- `ScheduleRepository`: contrato da agenda; `InMemoryScheduleRepository` é o
  adaptador provisório. Implementaremos o adaptador SQLite.
- `ScheduleService.create_slot(actor, subject, starts_at, capacity=1)` publica
  uma vaga própria do monitor, validando capacidade e conflitos de horário.
- `ScheduleService.list_slots(subject=None)` consulta a agenda futura publicada.
  A filtragem por capacidade restante (CA1) depende da integração com reservas.
- Futuro `BookingService.book(student, slot_id, question)`: valida e registra a
  reserva. Recusa vaga inexistente, lotação, conteúdo vazio e limite semanal.

**CA5 adicional:** o limite semanal é configurável, com padrão de duas reservas
por aluno/disciplina na semana da vaga (segunda a domingo). Recusar uma terceira
reserva nessa semana; aceitar em outra semana ou disciplina, havendo capacidade.
Este critério é independente do CA4, que trata do conteúdo da dúvida.

Testes futuros de reservas: `test_booking_consumes_capacity`,
`test_full_slot_rejected`, `test_unknown_slot_rejected`,
`test_question_required`, `test_question_visible_to_slot_students`,
`test_weekly_limit_rejected`, `test_other_week_allowed` e
`test_other_subject_allowed`. Implementaremos esses testes na etapa de reservas.
A falta de resposta do monitor não integra os critérios de reservas desta etapa.

Os testes já implementados em `tests/` verificam inicialmente agenda,
perfis, permissões e fluxo do terminal. Ainda não comprovam CA1–CA5 integrados.
