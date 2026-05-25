# Função de cada arquivo do projeto

## Visão geral da arquitetura
┌─────────────────────────────────────────┐
│           SERVIDOR (C)                  │
│                                         │
│  main.c ──── inicializa tudo            │
│  patient.h ── define as estruturas      │
│  patient.c ── gerencia os pacientes     │
│  vitals.c ─── simula os sinais vitais   │
│  network.c ── fala com o cliente        │
└─────────────────┬───────────────────────┘
                  │ TCP Socket (porta 8080)
┌─────────────────┴───────────────────────┐
│           CLIENTE (Python)              │
│                                         │
│  main.py ───── inicia o programa        │
│  network.py ── fala com o servidor      │
│  gui.py ─────── desenha a tela          │
└─────────────────────────────────────────┘

# Servidor em C
*   patient.h — O plano de toda a estrutura
        É o arquivo de cabeçalho que define como os dados são organizados. Nenhum dado é armazenado aqui — ele apenas descreve o que existe.
        Define duas estruturas principais:
        Patient — representa um paciente individual com todos os seus dados:

        Identificação: id, name
        Sinais vitais atuais: heart_rate, spo2, systolic_bp, diastolic_bp, temperature
        Baselines: os valores de equilíbrio em torno dos quais a simulação oscila
        Limites de alarme: mínimo e máximo para cada sinal
        Estado: se está monitorando, se tem alarme ativo, etc.
        Histórico: últimos 100 eventos de alarme

*   UTISystem — representa o sistema inteiro:

        Um banco com até 20 pacientes (db[MAX_PATIENTS])
        Qual paciente está ativo no momento (current_idx)
        O próximo ID a ser gerado (next_id)
        Os primitivos de sincronização: mutex e variável de condição

        Também declara as assinaturas de todas as funções e threads usadas nos outros arquivos.

*   patient.c — O gerenciador de pacientes
        Implementa as operações de cadastro e busca de pacientes. É como um banco de dados simples na memória.

        sys_init — inicializa o sistema zerado, cria o mutex e a variável de condição
        sys_destroy — libera o mutex e a variável de condição ao encerrar
        patient_defaults — preenche um paciente novo com valores fisiológicos normais (FC 75 bpm, SpO₂ 98%, etc.) e limites de alarme padrão
        patient_new — encontra um slot vazio no banco, atribui um ID automático e cadastra o paciente
        patient_find_id — percorre o banco procurando um paciente pelo número ID
        patient_find_name — percorre o banco procurando pelo nome (sem diferenciar maiúsculas)
        patient_current — retorna o paciente que está selecionado no momento
        patient_delete — remove um paciente do banco pelo ID


*   vitals.c — O simulador de sinais vitais
        Contém as três threads que ficam rodando em paralelo o tempo todo.
        thread_vitals — acorda a cada 1 segundo e atualiza os sinais do paciente ativo. Usa uma fórmula de mean-reversion: o valor oscila aleatoriamente mas sempre é puxado de volta para o baseline, evitando que os números fujam para valores impossíveis. Aplica clamping fisiológico (FC nunca abaixo de 20 nem acima de 220, etc.).
        thread_alarm — acorda a cada 500 ms e compara cada sinal com seus limites mínimo e máximo. Se algum valor estiver fora da faixa, marca o alarme como ativo, registra o evento no histórico do paciente e sinaliza a variável de condição para acordar a thread de histórico.
        thread_history — fica dormindo eficientemente com pthread_cond_wait, sem consumir CPU. Só acorda quando a thread de alarme a sinaliza. Ao acordar, pega o último evento do histórico e grava no arquivo uti_history.log em disco.

*   network.c — A ponte entre servidor e cliente
        Gerencia toda a comunicação TCP e interpreta os comandos recebidos.
        thread_network — cria o socket TCP na porta 8080, fica aguardando conexões com select() (com timeout de 1s para poder verificar se o servidor deve encerrar), e quando um cliente conecta passa o controle para handle_client.
        handle_client — lê os bytes que chegam do cliente e os acumula até encontrar um \n, garantindo que comandos fragmentados pelo TCP sejam processados completos.
        process_command — trava o mutex, identifica o comando recebido e executa a ação correspondente, depois libera o mutex. Implementa todos os 12 comandos do protocolo: NEW_PATIENT, SELECT_PATIENT, LIST_PATIENTS, DELETE_PATIENT, SET_VITAL, SET_LIMIT, GET_STATUS, START_MONITOR, STOP_MONITOR, SILENCE_ALARM, GET_HISTORY e RESET_ALARMS.

*   main.c — O ponto de partida do servidor
        É o arquivo principal que coloca tudo em movimento.

        Registra o tratador de SIGINT (Ctrl+C) para encerrar o servidor de forma limpa
        Chama sys_init para inicializar o sistema
        Cria as 4 threads com pthread_create: vitals, alarm, history e network
        Fica bloqueado em pthread_join esperando todas as threads terminarem
        Ao final, chama sys_destroy e encerra


## Cliente em Python
*   main.py — O ponto de partida do cliente
        Arquivo mínimo — apenas importa e instancia a GUI:
        pythonapp = UTIGui()
        app.mainloop()
        O mainloop() do Tkinter mantém a janela aberta e processando eventos até o usuário fechar.

*   network.py — A comunicação com o servidor
        Gerencia a conexão TCP pelo lado do cliente em uma thread separada, para não travar a interface gráfica.

        connect — tenta conectar ao servidor com timeout de 3s. Se conectar, inicia a thread de recepção e notifica a GUI via callback on_status(True)
        disconnect — encerra a conexão de forma limpa
        send — envia um comando ao servidor adicionando \n automaticamente
        _recv_loop — thread que fica recebendo dados do servidor e entrega linha a linha para a GUI via callback on_message. Roda em paralelo sem bloquear a tela

        O uso de callbacks é fundamental: a thread de rede não pode mexer na GUI diretamente (isso travaria o Tkinter), então ela apenas chama on_message(linha) e a GUI decide o que fazer.

*   gui.py — A interface gráfica
        É o arquivo mais extenso — desenha e controla toda a janela.
        Está organizado em painéis:

        Cabeçalho — título, status de conexão, indicador de alarme e botão de som
        Sinais Vitais — 5 labels grandes que atualizam automaticamente a cada 2 segundos com os valores recebidos do servidor
        Conexão — campos de host/porta e botões Conectar/Desconectar
        Pacientes — cadastro, seleção, listagem e remoção de pacientes
        Definir Sinal Vital — campos para SET_VITAL e SET_LIMIT
        Controles — botões para os comandos principais
        Log de Respostas — área de texto que exibe tudo que chega do servidor

        A classe AlarmSound gera um beep senoidal em memória usando wave + struct, salva em arquivo temporário e toca via aplay. O beep fica em loop em uma thread separada enquanto o alarme estiver ativo, e para automaticamente ao silenciar.
        O método _schedule_poll usa after(2000, ...) do Tkinter para enviar GET_STATUS ao servidor a cada 2 segundos, mantendo os sinais vitais atualizados na tela sem precisar de uma thread extra.