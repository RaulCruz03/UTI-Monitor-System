# 🏥 Monitor de UTI Simulado — Sistema Cliente-Servidor Multithread

Este projeto consiste em um sistema de monitoramento de sinais vitais para uma Unidade de Tratamento Intensivo (UTI). O sistema utiliza uma arquitetura **cliente-servidor** para simular o monitoramento em tempo real de pacientes, empregando técnicas de **programação concorrente**, **sincronização de threads** e **comunicação via sockets TCP/IP**.

Este trabalho foi desenvolvido como projeto final para a disciplina de Sistemas Operacionais / Sistemas Embarcados na **UFSM**.

---

## 📋 Requisitos Atendidos

O sistema foi projetado para cumprir rigorosamente os seguintes requisitos técnicos:

* **Servidor (Linguagem C):**
    * Mínimo de 4 threads em execução.
    * Uso de threads periódicas para simulação de sensores.
    * Sincronização via **Mutex** e **Variáveis de Condição**.
    * Comunicação de rede via Sockets BSD.
* **Cliente (Linguagem Python):**
    * Interface Gráfica (GUI) funcional.
    * Conexão e envio de comandos em tempo real.
    * Visualização do estado do sistema e log de respostas.

---

## ⚙️ Arquitetura do Sistema

O servidor simula o hardware de monitoramento à beira do leito, enquanto o cliente representa a estação de trabalho da enfermagem.

### Gerenciamento de Threads (Servidor)

| Thread | Tipo | Responsabilidade |
| :--- | :--- | :--- |
| `thread_vitals` | Periódica (1s) | Simula sensores (ECG, SpO2, Pressão) com variações realistas. |
| `thread_alarm` | Periódica (0.5s) | Verifica se os sinais estão fora dos limites e sinaliza alertas. |
| `thread_network` | Rede (Evento) | Gerencia conexões TCP e processa o protocolo de comandos. |
| `thread_history` | Condição | Aguarda sinalização para gravar eventos críticos em log. |

### Mecanismos de Sincronização

1.  **Mutex (`mutex_patient`):** Protege a estrutura global `Patient`, impedindo que a thread de rede leia dados enquanto a thread de sensores os atualiza (evitando inconsistências).
2.  **Variável de Condição (`cond_alarm`):** A thread de histórico permanece em bloqueio eficiente (`pthread_cond_wait`), sendo "acordada" pela thread de alarme apenas quando uma anomalia real é detectada.

---

## 📡 Protocolo de Comunicação

A comunicação utiliza mensagens de texto simples separadas por `\n`.

| Comando | Parâmetros | Descrição |
| :--- | :--- | :--- |
| `START_MONITOR` | - | Inicia a simulação de sinais vitais. |
| `STOP_MONITOR` | - | Pausa a simulação no servidor. |
| `SET_LIMIT` | `<sinal> <min> <max>` | Define faixas de alerta (Ex: `SET_LIMIT SPO2 90 100`). |
| `GET_STATUS` | - | Solicita os valores atuais de todos os sinais. |
| `SILENCE_ALARM` | - | Silencia o alarme visual/sonoro ativo no servidor. |
| `GET_HISTORY` | - | Retorna a lista de ocorrências registradas. |
| `SET_PATIENT` | `<nome>` | Define o nome do paciente monitorado. |
| `RESET_ALARMS` | - | Limpa o histórico de alertas registrados. |

---

## 📂 Estrutura do Projeto

```text
uti-monitor/
├── server/
│   ├── main.c           # Inicialização e criação de threads
│   ├── vitals.c         # Lógica dos sinais vitais
│   ├── network.c        # Gerenciamento de sockets em C
│   └── patient.h        # Definição da Struct e Sincronização
├── client/
│   ├── main.py          # Ponto de entrada do cliente
│   ├── gui.py           # Interface Tkinter
│   └── network.py       # Thread de comunicação Python
└── README.md
