#include <string.h>
#include <strings.h>
#include "patient.h"

/* ------------------------------------------------------------------ */
/*  Valores padrão para um novo paciente                               */
/* ------------------------------------------------------------------ */
void patient_defaults(Patient *p) {
    /* Sinais e baselines iniciais (adulto saudável) */
    p->heart_rate   = p->base_hr   = 75.0f;
    p->spo2         = p->base_spo2 = 98.0f;
    p->systolic_bp  = p->base_bps  = 120.0f;
    p->diastolic_bp = p->base_bpd  = 80.0f;
    p->temperature  = p->base_temp = 36.5f;

    /* Limites padrão */
    p->hr_min      = 50.0f;  p->hr_max      = 110.0f;
    p->spo2_min    = 94.0f;  p->spo2_max    = 100.0f;
    p->bp_sys_min  = 90.0f;  p->bp_sys_max  = 140.0f;
    p->bp_dia_min  = 60.0f;  p->bp_dia_max  =  90.0f;
    p->temp_min    = 36.0f;  p->temp_max    =  38.0f;

    p->monitoring_active = false;
    p->alarm_active      = false;
    p->alarm_silenced    = false;
    p->history_count     = 0;
}

/* ------------------------------------------------------------------ */
/*  Inicialização e destruição do sistema                              */
/* ------------------------------------------------------------------ */
void sys_init(UTISystem *s) {
    memset(s, 0, sizeof(UTISystem));
    s->current_idx = -1;
    s->next_id     = 1;
    pthread_mutex_init(&s->mutex,      NULL);
    pthread_cond_init (&s->cond_alarm, NULL);
}

void sys_destroy(UTISystem *s) {
    pthread_mutex_destroy(&s->mutex);
    pthread_cond_destroy (&s->cond_alarm);
}

/* ------------------------------------------------------------------ */
/*  Cadastro de paciente                                               */
/* ------------------------------------------------------------------ */
Patient *patient_new(UTISystem *s, const char *name) {
    if (s->count >= MAX_PATIENTS) return NULL;
    for (int i = 0; i < MAX_PATIENTS; i++) {
        if (!s->db[i].in_use) {
            Patient *p = &s->db[i];
            memset(p, 0, sizeof(Patient));
            p->in_use = true;
            p->id     = s->next_id++;
            strncpy(p->name, name, MAX_NAME_LEN - 1);
            patient_defaults(p);
            s->count++;
            return p;
        }
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/*  Busca                                                              */
/* ------------------------------------------------------------------ */
Patient *patient_find_id(UTISystem *s, int id) {
    for (int i = 0; i < MAX_PATIENTS; i++)
        if (s->db[i].in_use && s->db[i].id == id)
            return &s->db[i];
    return NULL;
}

Patient *patient_find_name(UTISystem *s, const char *name) {
    for (int i = 0; i < MAX_PATIENTS; i++)
        if (s->db[i].in_use &&
            strncasecmp(s->db[i].name, name, MAX_NAME_LEN) == 0)
            return &s->db[i];
    return NULL;
}

Patient *patient_current(UTISystem *s) {
    if (s->current_idx < 0 || s->current_idx >= MAX_PATIENTS) return NULL;
    return s->db[s->current_idx].in_use ? &s->db[s->current_idx] : NULL;
}

/* ------------------------------------------------------------------ */
/*  Remoção                                                            */
/* ------------------------------------------------------------------ */
bool patient_delete(UTISystem *s, int id) {
    for (int i = 0; i < MAX_PATIENTS; i++) {
        if (s->db[i].in_use && s->db[i].id == id) {
            /* Se é o paciente ativo, desseleciona */
            if (s->current_idx == i) s->current_idx = -1;
            memset(&s->db[i], 0, sizeof(Patient));
            s->count--;
            return true;
        }
    }
    return false;
}