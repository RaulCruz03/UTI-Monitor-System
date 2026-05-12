"""
gui.py — Interface gráfica Tkinter do Monitor de UTI.

Layout:
  ┌─────────────────────────────────────────────────────┐
  │  Header (título + status + alerta)                  │
  ├─────────────────────────┬───────────────────────────┤
  │  Sinais Vitais          │  Log de Respostas         │
  │  Conexão                │                           │
  │  Controles              │  [ Entrada de comando ]   │
  │  Paciente               │                           │
  └─────────────────────────┴───────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from network import NetworkClient

# ── Paleta de cores ────────────────────────────────────────────────────
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
FONT_BIG  = ("Consolas", 20, "bold")


class UTIGui(tk.Tk):
    """Janela principal do Monitor de UTI."""

    def __init__(self):
        super().__init__()
        self.title("Monitor de UTI Simulado — UFSM")
        self.configure(bg=DARK_BG)
        self.geometry("1050x720")
        self.minsize(800, 600)

        self._connected = False
        self._net = NetworkClient(
            on_message=self._on_message,
            on_status=self._on_status,
        )

        self._build_ui()
        self._schedule_poll()

    # ==================================================================
    #  Construção da interface
    # ==================================================================
    def _build_ui(self):
        self._build_header()

        content = tk.Frame(self, bg=DARK_BG)
        content.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._build_left_panel(content)
        self._build_right_panel(content)

    # ── Cabeçalho ─────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=CARD_BG, pady=10)
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="🏥  Monitor de UTI Simulado",
            font=("Segoe UI", 14, "bold"), bg=CARD_BG, fg=TEXT_FG
        ).pack(side="left", padx=16)

        self._lbl_alarm = tk.Label(
            hdr, text="", font=FONT_BOLD, bg=CARD_BG, fg=YELLOW)
        self._lbl_alarm.pack(side="right", padx=16)

        self._lbl_conn = tk.Label(
            hdr, text="● Desconectado",
            font=FONT_BOLD, bg=CARD_BG, fg=RED)
        self._lbl_conn.pack(side="right", padx=8)

    # ── Painel esquerdo ────────────────────────────────────────────────
    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=DARK_BG)
        left.pack(side="left", fill="both", padx=(0, 8))

        self._build_vitals_panel(left)
        self._build_conn_panel(left)
        self._build_ctrl_panel(left)
        self._build_patient_panel(left)

    # Sinais vitais
    def _build_vitals_panel(self, parent):
        frame = tk.LabelFrame(
            parent, text=" Sinais Vitais ",
            bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
            pady=8, padx=12, bd=1, relief="solid")
        frame.pack(fill="x", pady=(8, 6))

        vitals_def = [
            ("fc",   "❤  Freq. Cardíaca",   "bpm",  GREEN),
            ("spo2", "🫁 SpO₂",              "%",    GREEN),
            ("pas",  "💉 P.A. Sistólica",   "mmHg", GREEN),
            ("pad",  "💉 P.A. Diastólica",  "mmHg", GREEN),
            ("temp", "🌡  Temperatura",      "°C",   GREEN),
        ]
        self._vit_labels: dict[str, tk.Label] = {}
        self._vit_colors: dict[str, str]      = {}

        for key, label, unit, color in vitals_def:
            self._vit_colors[key] = color
            row = tk.Frame(frame, bg=PANEL_BG)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=label, width=22, anchor="w",
                     bg=PANEL_BG, fg=TEXT_FG, font=FONT_UI).pack(side="left")

            lbl_val = tk.Label(row, text="--   ", width=7,
                               bg=PANEL_BG, fg=color,
                               font=FONT_BIG, anchor="e")
            lbl_val.pack(side="left")

            tk.Label(row, text=unit, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MONO, width=5, anchor="w").pack(side="left")

            self._vit_labels[key] = lbl_val

    # Conexão
    def _build_conn_panel(self, parent):
        frame = tk.LabelFrame(
            parent, text=" Conexão ",
            bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
            pady=6, padx=12, bd=1, relief="solid")
        frame.pack(fill="x", pady=6)

        row1 = tk.Frame(frame, bg=PANEL_BG)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Host:", bg=PANEL_BG,
                 fg=TEXT_FG, font=FONT_UI, width=6, anchor="w").pack(side="left")
        self._e_host = tk.Entry(row1, width=15, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_host.insert(0, "127.0.0.1")
        self._e_host.pack(side="left", padx=(0, 8))
        tk.Label(row1, text="Porta:", bg=PANEL_BG,
                 fg=TEXT_FG, font=FONT_UI, width=6, anchor="w").pack(side="left")
        self._e_port = tk.Entry(row1, width=6, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_port.insert(0, "8080")
        self._e_port.pack(side="left")

        row2 = tk.Frame(frame, bg=PANEL_BG)
        row2.pack(fill="x", pady=(4, 0))
        self._btn_conn = tk.Button(
            row2, text="Conectar", command=self._connect,
            bg=GREEN, fg=DARK_BG, font=FONT_BOLD,
            relief="flat", width=13, cursor="hand2")
        self._btn_conn.pack(side="left", padx=(0, 6))
        self._btn_disc = tk.Button(
            row2, text="Desconectar", command=self._disconnect,
            bg=RED, fg=TEXT_FG, font=FONT_BOLD,
            relief="flat", width=13, cursor="hand2", state="disabled")
        self._btn_disc.pack(side="left")

    # Controles
    def _build_ctrl_panel(self, parent):
        frame = tk.LabelFrame(
            parent, text=" Controles ",
            bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
            pady=8, padx=12, bd=1, relief="solid")
        frame.pack(fill="x", pady=6)

        buttons = [
            ("▶  Iniciar Monitor", "START_MONITOR",  GREEN),
            ("⏸  Parar Monitor",   "STOP_MONITOR",   YELLOW),
            ("📊  Atualizar Status","GET_STATUS",     CYAN),
            ("📋  Ver Histórico",   "GET_HISTORY",    CYAN),
            ("🔕  Silenciar Alarme","SILENCE_ALARM",  YELLOW),
            ("🗑   Reset Alarmes",  "RESET_ALARMS",   RED),
        ]
        for idx, (label, cmd, color) in enumerate(buttons):
            btn = tk.Button(
                frame, text=label, width=22,
                command=lambda c=cmd: self._send(c),
                bg=CARD_BG, fg=color, font=FONT_BOLD,
                relief="flat", pady=4, cursor="hand2",
                activebackground=PANEL_BG, activeforeground=color)
            btn.grid(row=idx // 2, column=idx % 2, padx=3, pady=3, sticky="ew")

    # Paciente
    def _build_patient_panel(self, parent):
        frame = tk.LabelFrame(
            parent, text=" Paciente ",
            bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
            pady=6, padx=12, bd=1, relief="solid")
        frame.pack(fill="x", pady=6)

        row = tk.Frame(frame, bg=PANEL_BG)
        row.pack(fill="x")
        tk.Label(row, text="Nome:", bg=PANEL_BG,
                 fg=TEXT_FG, font=FONT_UI).pack(side="left")
        self._e_name = tk.Entry(row, width=18, bg=CARD_BG, fg=TEXT_FG,
                                font=FONT_MONO, insertbackground=TEXT_FG,
                                relief="flat", bd=4)
        self._e_name.pack(side="left", padx=6)
        tk.Button(row, text="Definir",
                  command=self._set_patient,
                  bg=CARD_BG, fg=ACCENT, font=FONT_BOLD,
                  relief="flat", cursor="hand2").pack(side="left")

    # ── Painel direito: log ────────────────────────────────────────────
    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=DARK_BG)
        right.pack(side="left", fill="both", expand=True)

        log_frame = tk.LabelFrame(
            right, text=" Log de Respostas ",
            bg=PANEL_BG, fg=ACCENT, font=FONT_BOLD,
            pady=4, padx=4, bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, pady=(8, 6))

        self._log = scrolledtext.ScrolledText(
            log_frame, bg=DARK_BG, fg=GREEN, font=FONT_MONO,
            state="disabled", wrap="word", relief="flat",
            insertbackground=GREEN)
        self._log.pack(fill="both", expand=True)

        # Entrada de comando livre
        cmd_row = tk.Frame(right, bg=DARK_BG)
        cmd_row.pack(fill="x")
        self._e_cmd = tk.Entry(
            cmd_row, bg=CARD_BG, fg=TEXT_FG, font=FONT_MONO,
            insertbackground=TEXT_FG, relief="flat", bd=4)
        self._e_cmd.pack(side="left", fill="x", expand=True)
        self._e_cmd.bind("<Return>", lambda _: self._send_raw())
        tk.Button(
            cmd_row, text="Enviar", command=self._send_raw,
            bg=ACCENT, fg=DARK_BG, font=FONT_BOLD,
            relief="flat", width=8, cursor="hand2").pack(side="left", padx=(6, 0))

    # ==================================================================
    #  Callbacks de rede (chegam de thread secundária → redireciona
    #  para a thread principal via after())
    # ==================================================================
    def _on_message(self, msg: str):
        self.after(0, self._handle_message, msg)

    def _on_status(self, connected: bool):
        self.after(0, self._handle_status, connected)

    # ==================================================================
    #  Handlers na thread principal
    # ==================================================================
    def _handle_message(self, msg: str):
        self._log_append(msg)

        if msg.startswith("STATUS|"):
            self._update_vitals(msg)

    def _update_vitals(self, msg: str):
        """Analisa mensagem STATUS| e atualiza os labels de sinais vitais."""
        try:
            parts = {}
            for token in msg.split("|")[1:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    parts[k] = v

            mapping = {
                "fc":   "fc",
                "spo2": "spo2",
                "pas":  "pas",
                "pad":  "pad",
                "temp": "temp",
            }
            alarm_on = parts.get("alarme", "OK") == "ATIVO"
            fg_color = RED if alarm_on else GREEN

            for srv_key, gui_key in mapping.items():
                if srv_key in parts:
                    # Formata com 1 decimal
                    try:
                        val = f"{float(parts[srv_key]):.1f}"
                    except ValueError:
                        val = parts[srv_key]
                    self._vit_labels[gui_key].config(text=val, fg=fg_color)

            self._lbl_alarm.config(
                text="⚠  ALARME ATIVO !" if alarm_on else "",
                fg=YELLOW)
        except Exception:
            pass   # mensagem malformada — ignora

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
            for lbl in self._vit_labels.values():
                lbl.config(text="--   ", fg=GREEN)

    # ==================================================================
    #  Ações do usuário
    # ==================================================================
    def _connect(self):
        host = self._e_host.get().strip() or "127.0.0.1"
        try:
            port = int(self._e_port.get().strip())
        except ValueError:
            port = 8080
        self._log_append(f"[INFO] Conectando a {host}:{port}...")
        self._net.connect(host, port)

    def _disconnect(self):
        self._net.disconnect()

    def _send(self, cmd: str):
        if not self._connected:
            self._log_append("[AVISO] Não conectado ao servidor.")
            return
        self._log_append(f"→ {cmd}")
        self._net.send(cmd)

    def _send_raw(self):
        cmd = self._e_cmd.get().strip()
        if cmd:
            self._send(cmd)
            self._e_cmd.delete(0, "end")

    def _set_patient(self):
        name = self._e_name.get().strip()
        if name:
            self._send(f"SET_PATIENT {name}")

    # ==================================================================
    #  Polling automático de status a cada 2 s
    # ==================================================================
    def _schedule_poll(self):
        if self._connected:
            self._net.send("GET_STATUS")
        self.after(2000, self._schedule_poll)

    # ==================================================================
    #  Helpers
    # ==================================================================
    def _log_append(self, msg: str):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")
