"""
network.py — Gerencia a conexão TCP com o servidor em thread separada.

A comunicação é assíncrona: os dados recebidos são entregues via
callback `on_message`, e o status da conexão via `on_status`.
"""

import socket
import threading
import queue
from typing import Callable

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
CONNECT_TIMEOUT = 3.0


class NetworkClient:
    """
    Cliente TCP não-bloqueante.

    Parâmetros
    ----------
    on_message : Callable[[str], None]
        Chamado para cada linha recebida do servidor.
    on_status : Callable[[bool], None]
        Chamado quando o estado da conexão muda (True = conectado).
    """

    def __init__(
        self,
        on_message: Callable[[str], None],
        on_status:  Callable[[bool], None],
    ):
        self._sock:    socket.socket | None = None
        self._thread:  threading.Thread | None = None
        self._running: bool = False
        self.on_message = on_message
        self.on_status  = on_status

    # ------------------------------------------------------------------
    #  Conexão / desconexão
    # ------------------------------------------------------------------
    def connect(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
        """Tenta conectar ao servidor. Retorna True em caso de sucesso."""
        try:
            self._sock = socket.create_connection((host, port),
                                                  timeout=CONNECT_TIMEOUT)
            self._sock.settimeout(None)   # modo bloqueante no recv
            self._running = True
            self._thread = threading.Thread(
                target=self._recv_loop, daemon=True, name="net-recv"
            )
            self._thread.start()
            self.on_status(True)
            return True

        except (ConnectionRefusedError, TimeoutError, OSError) as exc:
            self.on_message(f"[ERRO] Não foi possível conectar: {exc}")
            self.on_status(False)
            return False

    def disconnect(self):
        """Encerra a conexão de forma limpa."""
        self._running = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self.on_status(False)

    # ------------------------------------------------------------------
    #  Envio de comandos
    # ------------------------------------------------------------------
    def send(self, command: str):
        """Envia um comando (adiciona \\n automaticamente)."""
        if self._sock and self._running:
            try:
                payload = (command.strip() + "\n").encode("utf-8")
                self._sock.sendall(payload)
            except OSError as exc:
                self.on_message(f"[ERRO] Falha ao enviar: {exc}")
                self.disconnect()

    # ------------------------------------------------------------------
    #  Loop de recepção (thread de rede)
    # ------------------------------------------------------------------
    def _recv_loop(self):
        """Recebe dados do servidor e entrega linha a linha via callback."""
        buf = ""
        try:
            while self._running:
                data = self._sock.recv(1024)
                if not data:
                    break
                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.on_message(line)
        except OSError:
            pass
        finally:
            if self._running:   # encerramento inesperado
                self.on_message("[INFO] Conexão com o servidor encerrada.")
                self.on_status(False)
