#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include "patient.h"

#define BUF_SIZE 2048

static void net_send(int sock, const char *msg) {
    send(sock, msg, strlen(msg), 0);
}

/* ------------------------------------------------------------------ */
/*  Índice de um paciente no array db[]                                */
/* ------------------------------------------------------------------ */
static int patient_index(UTISystem *s, Patient *p) {
    if (!p) return -1;
    return (int)(p - s->db);   // retorna o índice do paciente no array
}

/* ------------------------------------------------------------------ */
/*  process_command                                                     */
/* ------------------------------------------------------------------ */
static void process_command(int sock, char *cmd) {
    cmd[strcspn(cmd, "\r\n")] = '\0'; // trocando \r\n por \0 para facilitar comparação  windows e linux
    if (cmd[0] == '\0') return;
    printf("[network] CMD: %s\n", cmd);

    pthread_mutex_lock(&sys.mutex);

    /* ── NEW_PATIENT <nome> ───────────────────────────────────────── */
    if (strncmp(cmd, "NEW_PATIENT", 11) == 0) {
        const char *name = (strlen(cmd) > 12) ? cmd + 12 : "Sem Nome"; //sserver suporta nome vazio, mas evita string vazia
        Patient *p = patient_new(&sys, name);
        if (!p) { net_send(sock, "ERR: Limite de pacientes atingido\n"); goto done; } // volta pro mutex unlock
        char buf[128];
        snprintf(buf, sizeof(buf), "OK: Paciente criado ID=%d nome=%s\n",
                 p->id, p->name);
        net_send(sock, buf);

    /* ── SELECT_PATIENT <id|nome> ────────────────────────────────── */
    } else if (strncmp(cmd, "SELECT_PATIENT", 14) == 0) {
        const char *arg = (strlen(cmd) > 15) ? cmd + 15 : "";
        Patient *p = NULL;
        int id = atoi(arg);
        if (id > 0) p = patient_find_id(&sys, id);
        if (!p)     p = patient_find_name(&sys, arg);
        if (!p)     { net_send(sock, "ERR: Paciente nao encontrado\n"); goto done; }
        sys.current_idx = patient_index(&sys, p);
        char buf[128];
        snprintf(buf, sizeof(buf), "OK: Monitorando ID=%d nome=%s\n",
                 p->id, p->name);
        net_send(sock, buf);

    /* ── LIST_PATIENTS ───────────────────────────────────────────── */
    } else if (strcmp(cmd, "LIST_PATIENTS") == 0) {
        if (sys.count == 0) {
            net_send(sock, "LIST|vazio\n");
        } else {
            char buf[256];
            for (int i = 0; i < MAX_PATIENTS; i++) {
                Patient *p = &sys.db[i];
                if (!p->in_use) continue;
                const char *ativo = (i == sys.current_idx) ? "ATIVO" : "---";
                snprintf(buf, sizeof(buf),
                    "LIST|id:%d|nome:%s|status:%s\n",
                    p->id, p->name, ativo);
                net_send(sock, buf);
            }
            net_send(sock, "LIST|END\n");
        }

    /* ── DELETE_PATIENT <id> ─────────────────────────────────────── */
    } else if (strncmp(cmd, "DELETE_PATIENT", 14) == 0) {
        int id = atoi(cmd + 15);
        if (patient_delete(&sys, id))
            net_send(sock, "OK: Paciente removido\n");
        else
            net_send(sock, "ERR: ID nao encontrado\n");

    /* ── SET_VITAL <sinal> <valor> ────────────────────────────────── */
    } else if (strncmp(cmd, "SET_VITAL", 9) == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "ERR: Nenhum paciente selecionado\n"); goto done; }
        char  signal[16];
        float val;
        if (sscanf(cmd + 10, "%15s %f", signal, &val) != 2) {
            net_send(sock, "ERR: Uso: SET_VITAL <sinal> <valor>\n"); goto done;
        }
        /* Atualiza valor atual E baseline (simulação oscila em torno do novo valor) */
        if      (strcmp(signal, "HR")   == 0) { p->heart_rate   = p->base_hr   = val; }
        else if (strcmp(signal, "SPO2") == 0) { p->spo2         = p->base_spo2 = val; }
        else if (strcmp(signal, "BPS")  == 0) { p->systolic_bp  = p->base_bps  = val; }
        else if (strcmp(signal, "BPD")  == 0) { p->diastolic_bp = p->base_bpd  = val; }
        else if (strcmp(signal, "TEMP") == 0) { p->temperature  = p->base_temp = val; }
        else { net_send(sock, "ERR: Sinal invalido. Use: HR SPO2 BPS BPD TEMP\n"); goto done; }
        net_send(sock, "OK: Sinal vital atualizado\n");

    /* ── START_MONITOR ───────────────────────────────────────────── */
    } else if (strcmp(cmd, "START_MONITOR") == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "ERR: Selecione um paciente primeiro\n"); goto done; }
        p->monitoring_active = true;
        p->alarm_silenced    = false;
        net_send(sock, "OK: Monitoramento iniciado\n");

    /* ── STOP_MONITOR ────────────────────────────────────────────── */
    } else if (strcmp(cmd, "STOP_MONITOR") == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "ERR: Nenhum paciente selecionado\n"); goto done; }
        p->monitoring_active = false;
        net_send(sock, "OK: Monitoramento pausado\n");

    /* ── SET_LIMIT <sinal> <min> <max> ───────────────────────────── */
    } else if (strncmp(cmd, "SET_LIMIT", 9) == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "ERR: Nenhum paciente selecionado\n"); goto done; }
        char  signal[16];
        float vmin, vmax;
        if (sscanf(cmd + 10, "%15s %f %f", signal, &vmin, &vmax) != 3) {
            net_send(sock, "ERR: Uso: SET_LIMIT <sinal> <min> <max>\n"); goto done;
        }
        if      (strcmp(signal, "HR")   == 0) { p->hr_min = vmin;     p->hr_max = vmax; }
        else if (strcmp(signal, "SPO2") == 0) { p->spo2_min = vmin;   p->spo2_max = vmax; }
        else if (strcmp(signal, "BPS")  == 0) { p->bp_sys_min = vmin; p->bp_sys_max = vmax; }
        else if (strcmp(signal, "BPD")  == 0) { p->bp_dia_min = vmin; p->bp_dia_max = vmax; }
        else if (strcmp(signal, "TEMP") == 0) { p->temp_min = vmin;   p->temp_max = vmax; }
        else { net_send(sock, "ERR: Sinal invalido. Use: HR SPO2 BPS BPD TEMP\n"); goto done; }
        net_send(sock, "OK: Limite atualizado\n");

    /* ── GET_STATUS ──────────────────────────────────────────────── */
    } else if (strcmp(cmd, "GET_STATUS") == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "STATUS|nenhum\n"); goto done; }
        char buf[BUF_SIZE];
        snprintf(buf, sizeof(buf),
            "STATUS|id:%d|paciente:%s|fc:%.1f|spo2:%.1f"
            "|pas:%.1f|pad:%.1f|temp:%.1f|alarme:%s\n",
            p->id, p->name,
            (double)p->heart_rate,  (double)p->spo2,
            (double)p->systolic_bp, (double)p->diastolic_bp,
            (double)p->temperature,
            p->alarm_active ? "ATIVO" : "OK");
        net_send(sock, buf);

    /* ── SILENCE_ALARM ───────────────────────────────────────────── */
    } else if (strcmp(cmd, "SILENCE_ALARM") == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "ERR: Nenhum paciente selecionado\n"); goto done; }
        p->alarm_silenced = true;
        p->alarm_active   = false;
        net_send(sock, "OK: Alarme silenciado\n");

    /* ── GET_HISTORY ─────────────────────────────────────────────── */
    } else if (strcmp(cmd, "GET_HISTORY") == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "HISTORY|nenhum paciente\n"); goto done; }
        if (p->history_count == 0) {
            net_send(sock, "HISTORY|vazio\n");
        } else {
            char buf[BUF_SIZE];
            for (int i = 0; i < p->history_count; i++) {
                snprintf(buf, sizeof(buf), "HISTORY|%s\n", p->history[i]);
                net_send(sock, buf);
            }
            net_send(sock, "HISTORY|END\n");
        }

    /* ── RESET_ALARMS ────────────────────────────────────────────── */
    } else if (strcmp(cmd, "RESET_ALARMS") == 0) {
        Patient *p = patient_current(&sys);
        if (!p) { net_send(sock, "ERR: Nenhum paciente selecionado\n"); goto done; }
        p->history_count  = 0;
        p->alarm_active   = false;
        p->alarm_silenced = false;
        sys.alarm_pending = false;
        net_send(sock, "OK: Historico e alarmes resetados\n");

    /* ── Desconhecido ────────────────────────────────────────────── */
    } else {
        net_send(sock,
            "ERR: Comando desconhecido\n"
            "ERR: Comandos: NEW_PATIENT SELECT_PATIENT LIST_PATIENTS "
            "DELETE_PATIENT SET_VITAL SET_LIMIT GET_STATUS "
            "START_MONITOR STOP_MONITOR SILENCE_ALARM GET_HISTORY RESET_ALARMS\n");
    }

done:
    pthread_mutex_unlock(&sys.mutex);
}

/* ------------------------------------------------------------------ */
/*  handle_client                                                       */
/* ------------------------------------------------------------------ */
static void handle_client(int fd) {
    char    buf[BUF_SIZE];
    char    line[BUF_SIZE * 2];
    int     llen = 0;
    ssize_t n;

    while ((n = recv(fd, buf, sizeof(buf) - 1, 0)) > 0) {
        buf[n] = '\0';
        for (int i = 0; i < (int)n; i++) {
            if (buf[i] == '\n') {
                line[llen] = '\0';
                process_command(fd, line);
                llen = 0;
            } else if (llen < (int)sizeof(line) - 1) {
                line[llen++] = buf[i];
            }
        }
    }
}

/* ------------------------------------------------------------------ */
/*  thread_network                                                      */
/* ------------------------------------------------------------------ */
void *thread_network(void *arg) {
    (void)arg;

    int sfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sfd < 0) { perror("socket"); return NULL; }

    int opt = 1;
    setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family      = AF_INET,
        .sin_port        = htons(PORT),
        .sin_addr.s_addr = INADDR_ANY,
    };

    if (bind(sfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); close(sfd); return NULL;
    }
    if (listen(sfd, 5) < 0) {
        perror("listen"); close(sfd); return NULL;
    }

    printf("[network] Aguardando conexoes na porta %d...\n", PORT);

    while (server_running) {
        fd_set rfds; FD_ZERO(&rfds); FD_SET(sfd, &rfds);
        struct timeval tv = {1, 0};
        if (select(sfd + 1, &rfds, NULL, NULL, &tv) <= 0) continue;

        struct sockaddr_in ca; socklen_t cl = sizeof(ca);
        int cfd = accept(sfd, (struct sockaddr *)&ca, &cl);
        if (cfd < 0) { perror("accept"); continue; }

        printf("[network] Cliente: %s:%d\n",
               inet_ntoa(ca.sin_addr), ntohs(ca.sin_port));

        handle_client(cfd);
        close(cfd);
        printf("[network] Cliente desconectado.\n");
    }

    close(sfd);
    printf("[network] Thread encerrada.\n");
    return NULL;
}