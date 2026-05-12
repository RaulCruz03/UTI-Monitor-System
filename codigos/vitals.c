#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "patient.h"

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */
static float rand_vary(float current, float baseline, float amplitude) {
    float noise = ((float)rand() / RAND_MAX * 2.0f - 1.0f) * amplitude;
    float pull  = (baseline - current) * 0.05f;  /* mean-reversion */
    return current + noise + pull;
}

static void get_timestamp(char *buf, size_t len) {
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    strftime(buf, len, "%Y-%m-%d %H:%M:%S", t);
}

/* ------------------------------------------------------------------ */
/*  thread_vitals — periódica a cada 1 s                               */
/*  Opera sempre sobre o paciente atualmente selecionado.              */
/* ------------------------------------------------------------------ */
void *thread_vitals(void *arg) {
    (void)arg;
    srand((unsigned)time(NULL));

    while (server_running) {
        pthread_mutex_lock(&sys.mutex);

        Patient *p = patient_current(&sys);
        if (p && p->monitoring_active) {
            p->heart_rate   = rand_vary(p->heart_rate,   p->base_hr,   2.5f);
            p->spo2         = rand_vary(p->spo2,         p->base_spo2, 0.4f);
            p->systolic_bp  = rand_vary(p->systolic_bp,  p->base_bps,  3.0f);
            p->diastolic_bp = rand_vary(p->diastolic_bp, p->base_bpd,  2.0f);
            p->temperature  = rand_vary(p->temperature,  p->base_temp, 0.1f);

            /* Clamping fisiológico */
            if (p->heart_rate   < 20.0f)  p->heart_rate   = 20.0f;
            if (p->heart_rate   > 220.0f) p->heart_rate   = 220.0f;
            if (p->spo2         < 70.0f)  p->spo2         = 70.0f;
            if (p->spo2         > 100.0f) p->spo2         = 100.0f;
            if (p->systolic_bp  < 50.0f)  p->systolic_bp  = 50.0f;
            if (p->systolic_bp  > 220.0f) p->systolic_bp  = 220.0f;
            if (p->diastolic_bp < 30.0f)  p->diastolic_bp = 30.0f;
            if (p->temperature  < 34.0f)  p->temperature  = 34.0f;
            if (p->temperature  > 43.0f)  p->temperature  = 43.0f;
            if (p->systolic_bp <= p->diastolic_bp)
                p->systolic_bp = p->diastolic_bp + 20.0f;
        }

        pthread_mutex_unlock(&sys.mutex);
        sleep(1);
    }

    printf("[vitals ] Thread encerrada.\n");
    return NULL;
}

/* ------------------------------------------------------------------ */
/*  thread_alarm — periódica a cada 500 ms                             */
/* ------------------------------------------------------------------ */
void *thread_alarm(void *arg) {
    (void)arg;
    char ts [32];
    char msg[HISTORY_MSG_LEN];
    struct timespec half = {0, 500000000L};

    while (server_running) {
        pthread_mutex_lock(&sys.mutex);

        Patient *p = patient_current(&sys);
        if (p && p->monitoring_active && !p->alarm_silenced) {
            bool triggered = false;

#define CHECK(val, mn, mx, label, fmt)                                  \
            if ((val) < (mn) || (val) > (mx)) {                         \
                triggered = true;                                       \
                get_timestamp(ts, sizeof(ts));                          \
                snprintf(msg, sizeof(msg),                              \
                    "[%s] ID%d/%s ALARME " label ": " fmt               \
                    " (limite %.1f-%.1f)",                              \
                    ts, p->id, p->name,                                 \
                    (val), (double)(mn), (double)(mx));                 \
            }

            CHECK(p->heart_rate,   p->hr_min,     p->hr_max,     "FC",   "%.1f bpm")
            CHECK(p->spo2,         p->spo2_min,   p->spo2_max,   "SpO2", "%.1f%%")
            CHECK(p->systolic_bp,  p->bp_sys_min, p->bp_sys_max, "PAS",  "%.1f mmHg")
            CHECK(p->diastolic_bp, p->bp_dia_min, p->bp_dia_max, "PAD",  "%.1f mmHg")
            CHECK(p->temperature,  p->temp_min,   p->temp_max,   "TEMP", "%.1f oC")
#undef CHECK

            if (triggered) {
                p->alarm_active = true;
                if (p->history_count < MAX_HISTORY) {
                    strncpy(p->history[p->history_count], msg,
                            HISTORY_MSG_LEN - 1);
                    p->history_count++;
                }
                sys.alarm_pending = true;
                pthread_cond_signal(&sys.cond_alarm);
            }
        }

        pthread_mutex_unlock(&sys.mutex);
        nanosleep(&half, NULL);
    }

    printf("[alarm  ] Thread encerrada.\n");
    return NULL;
}

/* ------------------------------------------------------------------ */
/*  thread_history — aguarda cond_alarm, grava em disco                */
/* ------------------------------------------------------------------ */
void *thread_history(void *arg) {
    (void)arg;

    while (server_running) {
        pthread_mutex_lock(&sys.mutex);

        while (!sys.alarm_pending && server_running)
            pthread_cond_wait(&sys.cond_alarm, &sys.mutex);

        if (!server_running) {
            pthread_mutex_unlock(&sys.mutex);
            break;
        }

        Patient *p = patient_current(&sys);
        if (p && p->history_count > 0) {
            const char *last = p->history[p->history_count - 1];
            FILE *fp = fopen("uti_history.log", "a");
            if (fp) { fprintf(fp, "%s\n", last); fclose(fp); }
            printf("[history] %s\n", last);
        }

        sys.alarm_pending = false;
        pthread_mutex_unlock(&sys.mutex);
    }

    printf("[history] Thread encerrada.\n");
    return NULL;
}