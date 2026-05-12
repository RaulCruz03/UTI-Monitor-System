#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <pthread.h>
#include "patient.h"

/* ------------------------------------------------------------------ */
/*  Variáveis globais                                                   */
/* ------------------------------------------------------------------ */
Patient      patient;
volatile int server_running = 1;

/* ------------------------------------------------------------------ */
/*  Tratador de SIGINT (Ctrl+C)                                         */
/* ------------------------------------------------------------------ */
static void handle_sigint(int sig) {
    (void)sig;
    server_running = 0;
    printf("\n[SERVER] Sinal de encerramento recebido...\n");

    /* Acorda thread_history caso esteja em pthread_cond_wait */
    pthread_cond_broadcast(&patient.cond_alarm);
}

/* ------------------------------------------------------------------ */
/*  main                                                                */
/* ------------------------------------------------------------------ */
int main(void) {
    signal(SIGINT, handle_sigint);

    patient_init(&patient);

    printf("╔══════════════════════════════════════╗\n");
    printf("║        Monitor de UTI Simulado       ║\n");
    printf("╠══════════════════════════════════════╣\n");
    printf("║  Porta TCP  : %-5d                  ║\n", PORT);
    printf("║  Threads    : 4 (vitals/alarm/       ║\n");
    printf("║               history/network)       ║\n");
    printf("║  Ctrl+C     : encerrar               ║\n");
    printf("╚══════════════════════════════════════╝\n\n");

    pthread_t t_vitals, t_alarm, t_history, t_network;

    if (pthread_create(&t_vitals,  NULL, thread_vitals,  NULL) != 0 ||
        pthread_create(&t_alarm,   NULL, thread_alarm,   NULL) != 0 ||
        pthread_create(&t_history, NULL, thread_history, NULL) != 0 ||
        pthread_create(&t_network, NULL, thread_network, NULL) != 0) {
        perror("pthread_create");
        patient_destroy(&patient);
        return EXIT_FAILURE;
    }

    /* Aguarda todas as threads finalizarem */
    pthread_join(t_vitals,  NULL);
    pthread_join(t_alarm,   NULL);
    pthread_join(t_history, NULL);
    pthread_join(t_network, NULL);

    patient_destroy(&patient);
    printf("[SERVER] Encerrado com sucesso.\n");
    return EXIT_SUCCESS;
}
