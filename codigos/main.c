#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <pthread.h>
#include "patient.h"

UTISystem    sys;
volatile int server_running = 1;

static void handle_sigint(int sig) {
    (void)sig;
    server_running = 0;
    printf("\n[SERVER] Encerrando...\n");
    pthread_cond_broadcast(&sys.cond_alarm);
}

int main(void) {
    signal(SIGINT, handle_sigint);
    sys_init(&sys);

    printf("╔══════════════════════════════════════╗\n");
    printf("║   Monitor de UTI Simulado — UFSM    ║\n");
    printf("╠══════════════════════════════════════╣\n");
    printf("║  Porta TCP  : %-5d                  ║\n", PORT);
    printf("║  Pacientes  : ate %-2d                 ║\n", MAX_PATIENTS);
    printf("║  Ctrl+C     : encerrar               ║\n");
    printf("╚══════════════════════════════════════╝\n\n");

    pthread_t t_vitals, t_alarm, t_history, t_network;

    if (pthread_create(&t_vitals,  NULL, thread_vitals,  NULL) != 0 ||
        pthread_create(&t_alarm,   NULL, thread_alarm,   NULL) != 0 ||
        pthread_create(&t_history, NULL, thread_history, NULL) != 0 ||
        pthread_create(&t_network, NULL, thread_network, NULL) != 0) {
        perror("pthread_create");
        sys_destroy(&sys);
        return EXIT_FAILURE;
    }

    pthread_join(t_vitals,  NULL);
    pthread_join(t_alarm,   NULL);
    pthread_join(t_history, NULL);
    pthread_join(t_network, NULL);

    sys_destroy(&sys);
    printf("[SERVER] Encerrado.\n");
    return EXIT_SUCCESS;
}
