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

   

 


