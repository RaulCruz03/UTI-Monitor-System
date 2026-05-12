#ifndef PATIENT_H
#define PATIENT_H

#include <pthread.h>
#include <stdbool.h>

/* ------------------------------------------------------------------ */
/*  Constantes                                                          */
/* ------------------------------------------------------------------ */
#define MAX_NAME_LEN    64
#define MAX_HISTORY     100
#define HISTORY_MSG_LEN 256
#define MAX_PATIENTS    20
#define PORT            8080

/* ------------------------------------------------------------------ */
/*  Struct de um paciente individual                                    */
/* ------------------------------------------------------------------ */
typedef struct {
    int  id;
    bool in_use;
    char name[MAX_NAME_LEN];

    /* Sinais vitais em tempo real */
    float heart_rate;
    float spo2;
    float systolic_bp;
    float diastolic_bp;
    float temperature;

    /* Baselines individuais (ponto de equilíbrio da simulação) */
    float base_hr, base_spo2, base_bps, base_bpd, base_temp;

    /* Limites de alerta */
    float hr_min,     hr_max;
    float spo2_min,   spo2_max;
    float bp_sys_min, bp_sys_max;
    float bp_dia_min, bp_dia_max;
    float temp_min,   temp_max;

    /* Estado */
    bool monitoring_active;
    bool alarm_active;
    bool alarm_silenced;

    /* Histórico de eventos */
    char history[MAX_HISTORY][HISTORY_MSG_LEN];
    int  history_count;
} Patient;

/* ------------------------------------------------------------------ */
/*  Sistema global (cadastro + sincronização)                          */
/* ------------------------------------------------------------------ */
typedef struct {
    Patient db[MAX_PATIENTS]; /* banco de pacientes            */
    int     count;            /* total cadastrados             */
    int     current_idx;      /* índice ativo (-1 = nenhum)    */
    int     next_id;          /* auto-incremento de IDs        */

    pthread_mutex_t mutex;
    pthread_cond_t  cond_alarm;
    bool            alarm_pending;
} UTISystem;

extern UTISystem    sys;
extern volatile int server_running;

/* ------------------------------------------------------------------ */
/*  API                                                                 */
/* ------------------------------------------------------------------ */
void     sys_init          (UTISystem *s);
void     sys_destroy       (UTISystem *s);

Patient *patient_new       (UTISystem *s, const char *name);
Patient *patient_find_id   (UTISystem *s, int id);
Patient *patient_find_name (UTISystem *s, const char *name);
Patient *patient_current   (UTISystem *s);
void     patient_defaults  (Patient *p);
bool     patient_delete    (UTISystem *s, int id);

void *thread_vitals  (void *arg);
void *thread_alarm   (void *arg);
void *thread_history (void *arg);
void *thread_network (void *arg);

#endif /* PATIENT_H */