"""
gui.py — Interface gráfica Tkinter do Monitor de UTI (multi-paciente + som).
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from network import NetworkClient
import threading
import wave
import struct
import math
import subprocess
import tempfile
import os

# ── Paleta ────────────────────────────────────────────────────────────
DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
CARD_BG  = "#21262d"
ACCENT   = "#58a6ff"
TEXT_FG  = "#c9d1d9"
GREEN    = "#3fb950"
YELLOW   = "#d29922"
RED      = "#f85149"
CYAN     = "#56d364"

FONT_UI   = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 10)
FONT_BIG  = ("Consolas", 18, "bold")


# ── Gerador de beep ───────────────────────────────────────────────────
def _make_wav(freq: float = 880.0, duration: float = 0.25,
              volume: float = 0.6) -> str:
    """Gera um arquivo WAV temporário com um tom senoidal."""
    rate   = 44100
    frames = int(rate * duration)
    # Fade in/out de 10 ms para evitar clique
    fade   = int(rate * 0.01)
    samples = []
    for i in range(frames):
        s = math.sin(2 * math.pi * freq * i / rate)
        if i < fade:
            s *= i / fade
        elif i > frames - fade:
            s *= (frames - i) / fade
        samples.append(int(32767 * volume * s))

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{frames}h", *samples))
    return path


def _detect_player() -> list[str] | None:
    """Retorna o comando do primeiro player de áudio disponível."""
    for player in ["aplay", "paplay", "pw-play", "ffplay"]:
        try:
            subprocess.run(["which", player],
                           capture_output=True, check=True)
            if player == "ffplay":
                return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
            return [player, "-q"]
        except subprocess.CalledProcessError:
            pass
    return None


PLAYER_CMD = _detect_player()


class AlarmSound:
    """Toca um beep repetitivo enquanto o alarme estiver ativo."""

    def __init__(self):
        self._active   = False
        self._thread   = None
        self._wav_high = _make_wav(freq=880.0, duration=0.20)
        self._wav_low  = _make_wav(freq=660.0, duration=0.15)

    def start(self):
        if self._active or not PLAYER_CMD:
            return
        self._active = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="alarm-sound")
        self._thread.start()

    def stop(self):
        self._active = False

    def _play(self, wav_path: str):
        try:
            subprocess.run(PLAYER_CMD + [wav_path],
                           capture_output=True, timeout=2)
        except Exception:
            pass

    def _loop(self):
        while self._active:
            self._play(self._wav_high)
            if not self._active:
                break
            self._play(self._wav_low)
            # Pausa de 0.8 s entre sequências
            for _ in range(8):
                if not self._active:
                    return
                threading.Event().wait(0.1)

    def cleanup(self):
        self.stop()
        for f in [self._wav_high, self._wav_low]:
            try:
                os.unlink(f)
            except OSError:
                pass


class UTIGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Monitor de UTI — UFSM")
        self.configure(bg=DARK_BG)
        self.geometry("1150x760")
        self.minsize(900, 620)

        self._connected  = False
        self._alarm_on   = False
        self._sound      = AlarmSound()
        self._net = NetworkClient(
            on_message=self._on_message,
            on_status=self._on_status,
        )

        self._build_ui()
        self._schedule_poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not PLAYER_CMD:
            self._log_append(
                "[AVISO] Nenhum player de áudio encontrado. "
                "Instale 'alsa-utils' para ativar o som:\n"
                "  sudo apt install alsa-utils")

    def _on_close(self):
        self._sound.cleanup()
        self.destroy()

    # ==================================================================
    #  UI
    # ==================================================================
    def _build_ui(self):
        self._build_header()
        content = tk.Frame(self, bg=DARK_BG)
        content.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._build_left(content)
        self._build_right(content)

    def _build_header(self):
        hdr = tk.Frame(self, bg=CARD_BG, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🏥  Monitor de UTI Simulado",
                 font=("Segoe UI", 14, "bold"), bg=CARD_BG, fg=TEXT_FG
                 ).pack(side="left", padx=16)

        # Botão mudo
        self._sound_on = tk.BooleanVar(value=True)
        self._btn_mute = tk.Checkbutton(
            hdr, text="🔊 Som", variable=self._sound_on,
            bg=CARD_BG, fg=TEXT_FG, selectcolor=CARD_BG,
            font=FONT_BOLD, cursor="hand2",
            command=self._toggle_sound)
        self._btn_mute.pack(side="right", padx=16)

        self._lbl_alarm = tk.Label(hdr, text="", font=FONT_BOLD,
                                   bg=CARD_BG, fg=YELLOW)
        self._lbl_alarm.pack(side="right", padx=16)
        self._lbl_conn = tk.Label(hdr, text="● Desconectado",
                                  font=FONT_BOLD, bg=CARD_BG, fg=RED)
        self._lbl_conn.pack(side="right", padx=8)

    def _toggle_sound(self):
        if not self._sound_on.get():
            self._sound.stop()

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=DARK_BG)
        left.pack(side="left", fill="both", padx=(0, 8))
        self._build_vitals(left)
        self._build_conn_panel(left)
        self._build_patients_panel(left)
        self._build_vitals_ctrl(left)
        self._build_ctrl(left)

    def _build_vitals(self, parent):
        frame = tk.LabelFrame(parent, text=" Sinais Vitais ",
                              bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
                              pady=6, padx=10, bd=1, relief="solid")
        frame.pack(fill="x", pady=(8, 4))

        defs = [
            ("fc",   "❤  Freq. Cardíaca",  "bpm"),
            ("spo2", "🫁 SpO₂",             "%"),
            ("pas",  "💉 P.A. Sistólica",  "mmHg"),
            ("pad",  "💉 P.A. Diastólica", "mmHg"),
            ("temp", "🌡  Temperatura",     "°C"),
        ]
        self._vit: dict[str, tk.Label] = {}
        for key, label, unit in defs:
            row = tk.Frame(frame, bg=PANEL_BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, width=22, anchor="w",
                     bg=PANEL_BG, fg=TEXT_FG, font=FONT_UI).pack(side="left")
            lv = tk.Label(row, text="--  ", width=6,
                          bg=PANEL_BG, fg=GREEN, font=FONT_BIG, anchor="e")
            lv.pack(side="left")
            tk.Label(row, text=unit, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MONO, width=5, anchor="w").pack(side="left")
            self._vit[key] = lv

    def _build_conn_panel(self, parent):
        frame = tk.LabelFrame(parent, text=" Conexão ",
                              bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
                              pady=6, padx=10, bd=1, relief="solid")
        frame.pack(fill="x", pady=4)

        row1 = tk.Frame(frame, bg=PANEL_BG)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Host:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI, width=6, anchor="w").pack(side="left")
        self._e_host = tk.Entry(row1, width=14, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_host.insert(0, "127.0.0.1")
        self._e_host.pack(side="left", padx=(0, 6))
        tk.Label(row1, text="Porta:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI, width=6, anchor="w").pack(side="left")
        self._e_port = tk.Entry(row1, width=6, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_port.insert(0, "8080")
        self._e_port.pack(side="left")

        row2 = tk.Frame(frame, bg=PANEL_BG)
        row2.pack(fill="x", pady=(4, 0))
        self._btn_conn = tk.Button(row2, text="Conectar",
                                   command=self._connect,
                                   bg=GREEN, fg=DARK_BG, font=FONT_BOLD,
                                   relief="flat", width=12, cursor="hand2")
        self._btn_conn.pack(side="left", padx=(0, 6))
        self._btn_disc = tk.Button(row2, text="Desconectar",
                                   command=self._disconnect,
                                   bg=RED, fg=TEXT_FG, font=FONT_BOLD,
                                   relief="flat", width=12, cursor="hand2",
                                   state="disabled")
        self._btn_disc.pack(side="left")

    def _build_patients_panel(self, parent):
        frame = tk.LabelFrame(parent, text=" Pacientes ",
                              bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
                              pady=6, padx=10, bd=1, relief="solid")
        frame.pack(fill="x", pady=4)

        row1 = tk.Frame(frame, bg=PANEL_BG)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Nome:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._e_pname = tk.Entry(row1, width=14, bg=CARD_BG, fg=TEXT_FG,
                                 font=FONT_MONO, insertbackground=TEXT_FG,
                                 relief="flat", bd=4)
        self._e_pname.pack(side="left", padx=6)
        tk.Button(row1, text="+ Cadastrar",
                  command=self._new_patient,
                  bg=GREEN, fg=DARK_BG, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left")

        row2 = tk.Frame(frame, bg=PANEL_BG)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="ID/Nome:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._e_sel = tk.Entry(row2, width=14, bg=CARD_BG, fg=TEXT_FG,
                               font=FONT_MONO, insertbackground=TEXT_FG,
                               relief="flat", bd=4)
        self._e_sel.pack(side="left", padx=6)
        tk.Button(row2, text="Selecionar",
                  command=self._select_patient,
                  bg=ACCENT, fg=DARK_BG, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left")

        row3 = tk.Frame(frame, bg=PANEL_BG)
        row3.pack(fill="x", pady=(4, 0))
        tk.Button(row3, text="📋 Listar Pacientes",
                  command=lambda: self._send("LIST_PATIENTS"),
                  bg=CARD_BG, fg=CYAN, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(row3, text="🗑 Deletar (ID)",
                  command=self._delete_patient,
                  bg=CARD_BG, fg=RED, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left")

        self._lbl_active = tk.Label(frame, text="Nenhum paciente selecionado",
                                    bg=PANEL_BG, fg=YELLOW, font=FONT_BOLD)
        self._lbl_active.pack(anchor="w", pady=(4, 0))

    def _build_vitals_ctrl(self, parent):
        frame = tk.LabelFrame(parent, text=" Definir Sinal Vital ",
                              bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
                              pady=6, padx=10, bd=1, relief="solid")
        frame.pack(fill="x", pady=4)

        row = tk.Frame(frame, bg=PANEL_BG)
        row.pack(fill="x")
        tk.Label(row, text="Sinal:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._var_signal = tk.StringVar(value="HR")
        ttk.Combobox(row, textvariable=self._var_signal,
                     values=["HR", "SPO2", "BPS", "BPD", "TEMP"],
                     width=6, state="readonly").pack(side="left", padx=6)
        tk.Label(row, text="Valor:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._e_vital_val = tk.Entry(row, width=7, bg=CARD_BG, fg=TEXT_FG,
                                     font=FONT_MONO, insertbackground=TEXT_FG,
                                     relief="flat", bd=4)
        self._e_vital_val.pack(side="left", padx=6)
        tk.Button(row, text="Aplicar", command=self._set_vital,
                  bg=YELLOW, fg=DARK_BG, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left")

        row2 = tk.Frame(frame, bg=PANEL_BG)
        row2.pack(fill="x", pady=(6, 0))
        tk.Label(row2, text="Limite:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._var_lim_sig = tk.StringVar(value="HR")
        ttk.Combobox(row2, textvariable=self._var_lim_sig,
                     values=["HR", "SPO2", "BPS", "BPD", "TEMP"],
                     width=6, state="readonly").pack(side="left", padx=4)
        tk.Label(row2, text="Min:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._e_lmin = tk.Entry(row2, width=5, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_lmin.pack(side="left", padx=4)
        tk.Label(row2, text="Max:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_UI).pack(side="left")
        self._e_lmax = tk.Entry(row2, width=5, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_lmax.pack(side="left", padx=4)
        tk.Button(row2, text="Definir", command=self._set_limit,
                  bg=ACCENT, fg=DARK_BG, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left")

    def _build_ctrl(self, parent):
        frame = tk.LabelFrame(parent, text=" Controles ",
                              bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
                              pady=6, padx=10, bd=1, relief="solid")
        frame.pack(fill="x", pady=4)

        btns = [
            ("▶ Iniciar Monitor",  "START_MONITOR",  GREEN),
            ("⏸ Parar Monitor",    "STOP_MONITOR",   YELLOW),
            ("📊 Atualizar Status", "GET_STATUS",     CYAN),
            ("📋 Ver Histórico",    "GET_HISTORY",    CYAN),
            ("🔕 Silenciar Alarme", "SILENCE_ALARM",  YELLOW),
            ("🗑 Reset Alarmes",    "RESET_ALARMS",   RED),
        ]
        for i, (label, cmd, color) in enumerate(btns):
            tk.Button(frame, text=label, width=20,
                      command=lambda c=cmd: self._send(c),
                      bg=CARD_BG, fg=color, font=FONT_BOLD,
                      relief="flat", pady=3, cursor="hand2"
                      ).grid(row=i // 2, column=i % 2,
                             padx=3, pady=2, sticky="ew")

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=DARK_BG)
        right.pack(side="left", fill="both", expand=True)

        log_frame = tk.LabelFrame(right, text=" Log de Respostas ",
                                  bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
                                  pady=4, padx=4, bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, pady=(8, 6))

        self._log = scrolledtext.ScrolledText(
            log_frame, bg=DARK_BG, fg=GREEN, font=FONT_MONO,
            state="disabled", wrap="word", relief="flat")
        self._log.pack(fill="both", expand=True)

        cmd_row = tk.Frame(right, bg=DARK_BG)
        cmd_row.pack(fill="x")
        self._e_cmd = tk.Entry(cmd_row, bg=CARD_BG, fg=TEXT_FG,
                               font=FONT_MONO, insertbackground=TEXT_FG,
                               relief="flat", bd=4)
        self._e_cmd.pack(side="left", fill="x", expand=True)
        self._e_cmd.bind("<Return>", lambda _: self._send_raw())
        tk.Button(cmd_row, text="Enviar", command=self._send_raw,
                  bg=ACCENT, fg=DARK_BG, font=FONT_BOLD,
                  relief="flat", width=8, cursor="hand2"
                  ).pack(side="left", padx=(6, 0))

    # ==================================================================
    #  Callbacks de rede
    # ==================================================================
    def _on_message(self, msg: str):
        self.after(0, self._handle_message, msg)

    def _on_status(self, connected: bool):
        self.after(0, self._handle_status, connected)

    def _handle_message(self, msg: str):
        self._log_append(msg)
        if msg.startswith("STATUS|"):
            self._update_vitals(msg)
        elif msg.startswith("OK: Monitorando"):
            try:
                name = msg.split("nome=", 1)[1]
                pid  = msg.split("ID=",   1)[1].split()[0]
                self._lbl_active.config(text=f"Ativo: [{pid}] {name}", fg=CYAN)
            except Exception:
                pass

    def _update_vitals(self, msg: str):
        try:
            parts = {}
            for token in msg.split("|")[1:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    parts[k] = v

            alarm_on = parts.get("alarme", "OK") == "ATIVO"
            color = RED if alarm_on else GREEN

            mapping = {"fc": "fc", "spo2": "spo2",
                       "pas": "pas", "pad": "pad", "temp": "temp"}
            for srv, gui in mapping.items():
                if srv in parts:
                    try:    val = f"{float(parts[srv]):.1f}"
                    except: val = parts[srv]
                    self._vit[gui].config(text=val, fg=color)

            # Atualiza label do paciente ativo
            nome = parts.get("paciente", "")
            pid  = parts.get("id", "")
            if nome:
                self._lbl_active.config(
                    text=f"Ativo: [{pid}] {nome}",
                    fg=CYAN if not alarm_on else YELLOW)

            # Gerencia alarme sonoro
            if alarm_on and not self._alarm_on:
                self._alarm_on = True
                self._lbl_alarm.config(text="⚠  ALARME ATIVO !", fg=RED)
                if self._sound_on.get():
                    self._sound.start()
            elif not alarm_on and self._alarm_on:
                self._alarm_on = False
                self._lbl_alarm.config(text="", fg=YELLOW)
                self._sound.stop()

        except Exception:
            pass

    def _handle_status(self, connected: bool):
        self._connected = connected
        if connected:
            self._lbl_conn.config(text="● Conectado", fg=GREEN)
            self._btn_conn.config(state="disabled")
            self._btn_disc.config(state="normal")
        else:
            self._lbl_conn.config(text="● Desconectado", fg=RED)
            self._btn_conn.config(state="normal")
            self._btn_disc.config(state="disabled")
            for lv in self._vit.values():
                lv.config(text="--  ", fg=GREEN)
            self._lbl_active.config(
                text="Nenhum paciente selecionado", fg=YELLOW)
            self._sound.stop()
            self._alarm_on = False

    # ==================================================================
    #  Ações dos botões
    # ==================================================================
    def _connect(self):
        host = self._e_host.get().strip() or "127.0.0.1"
        try:   port = int(self._e_port.get().strip())
        except: port = 8080
        self._log_append(f"[INFO] Conectando a {host}:{port}...")
        self._net.connect(host, port)

    def _disconnect(self):
        self._net.disconnect()

    def _send(self, cmd: str):
        if not self._connected:
            self._log_append("[AVISO] Não conectado.")
            return
        self._log_append(f"→ {cmd}")
        self._net.send(cmd)
        # Silenciar pelo botão também para o som
        if cmd in ("SILENCE_ALARM", "RESET_ALARMS"):
            self._sound.stop()
            self._alarm_on = False
            self._lbl_alarm.config(text="", fg=YELLOW)

    def _send_raw(self):
        cmd = self._e_cmd.get().strip()
        if cmd:
            self._send(cmd)
            self._e_cmd.delete(0, "end")

    def _new_patient(self):
        name = self._e_pname.get().strip()
        if not name:
            messagebox.showwarning("Aviso", "Digite o nome do paciente.")
            return
        self._send(f"NEW_PATIENT {name}")
        self._e_pname.delete(0, "end")

    def _select_patient(self):
        sel = self._e_sel.get().strip()
        if not sel:
            messagebox.showwarning("Aviso", "Digite o ID ou nome.")
            return
        self._send(f"SELECT_PATIENT {sel}")

    def _delete_patient(self):
        sel = self._e_sel.get().strip()
        if not sel:
            messagebox.showwarning("Aviso", "Digite o ID no campo ID/Nome.")
            return
        if messagebox.askyesno("Confirmar", f"Deletar paciente '{sel}'?"):
            self._send(f"DELETE_PATIENT {sel}")

    def _set_vital(self):
        signal = self._var_signal.get()
        val    = self._e_vital_val.get().strip()
        if not val:
            messagebox.showwarning("Aviso", "Digite o valor do sinal.")
            return
        self._send(f"SET_VITAL {signal} {val}")

    def _set_limit(self):
        signal = self._var_lim_sig.get()
        vmin   = self._e_lmin.get().strip()
        vmax   = self._e_lmax.get().strip()
        if not vmin or not vmax:
            messagebox.showwarning("Aviso", "Preencha Min e Max.")
            return
        self._send(f"SET_LIMIT {signal} {vmin} {vmax}")

    # ==================================================================
    #  Polling automático
    # ==================================================================
    def _schedule_poll(self):
        if self._connected:
            self._net.send("GET_STATUS")
        self.after(2000, self._schedule_poll)

    def _log_append(self, msg: str):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")