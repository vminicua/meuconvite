"""
Túnel SSH para desenvolvimento contra a base de dados de produção.

A base de dados do cPanel só aceita ligações a partir do próprio servidor,
por isso o ambiente local liga-se através de um túnel SSH encriptado:

    127.0.0.1:<DEV_DB_PORT>  ->  (SSH)  ->  servidor 127.0.0.1:3306

Como usar (deixar a correr numa janela à parte):

    python scripts/dev_tunnel.py

Depois, noutra janela:

    python manage.py runserver

O túnel mantém-se vivo com keepalives e **reconecta-se automaticamente**
se a ligação SSH cair. Se o transporte estiver em baixo, as ligações são
recusadas de imediato em vez de ficarem à espera — o Django dá então um
erro claro em vez de "Lost connection ... reading initial communication
packet".

Credenciais lidas do `.env` (que nunca vai para o repositório):

    SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD  (ou SSH_KEY_FILE)
    DEV_DB_PORT            porta local do túnel (por omissão 3307)
    DEV_DB_REMOTE_HOST     destino no servidor (por omissão 127.0.0.1)
    DEV_DB_REMOTE_PORT     porta no servidor (por omissão 3306)

Requer `paramiko` (ver requirements-dev.txt).
"""

from __future__ import annotations

import select
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import environ
    import paramiko
except ImportError:  # pragma: no cover - dependência opcional
    sys.exit(
        "Faltam dependências de desenvolvimento. Instale com:\n"
        "    pip install -r requirements-dev.txt"
    )

env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

KEEPALIVE_SECONDS = 30
RECONNECT_DELAY_SECONDS = 3
MAX_RECONNECT_DELAY_SECONDS = 30


def log(message: str) -> None:
    """Escreve com flush: o output tem de aparecer mesmo redireccionado."""
    print(f"[tunel] {message}", flush=True)


class SSHConnection:
    """
    Ligação SSH partilhada, capaz de se restabelecer sozinha.

    Cada ligação local pede o transporte a esta classe; se estiver em
    baixo, é reconstruído uma vez (com bloqueio, para não abrir várias
    sessões SSH ao mesmo tempo).
    """

    def __init__(self, **connect_kwargs) -> None:
        self._connect_kwargs = connect_kwargs
        self._client: paramiko.SSHClient | None = None
        self._lock = threading.Lock()

    def _open(self) -> paramiko.Transport:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(**self._connect_kwargs)

        transport = client.get_transport()
        if transport is None:
            client.close()
            raise ConnectionError("o servidor não devolveu um transporte SSH")

        # Sem isto, a ligação cai em silêncio depois de alguns minutos
        # sem tráfego e o túnel fica a aceitar ligações que não chegam
        # a nenhum lado.
        transport.set_keepalive(KEEPALIVE_SECONDS)

        self._client = client
        return transport

    @property
    def transport(self) -> paramiko.Transport | None:
        client = self._client
        if client is None:
            return None
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            return None
        return transport

    def get_transport(self) -> paramiko.Transport:
        """Transporte activo, reconectando se necessário."""
        transport = self.transport
        if transport is not None:
            return transport

        with self._lock:
            # Outra thread pode ter reconectado enquanto esperávamos.
            transport = self.transport
            if transport is not None:
                return transport

            if self._client is not None:
                log("ligação SSH em baixo — a reconectar…")
                try:
                    self._client.close()
                except Exception:  # noqa: BLE001
                    pass
                self._client = None

            transport = self._open()
            log("ligação SSH restabelecida.")
            return transport

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


class ForwardHandler(socketserver.BaseRequestHandler):
    """Liga cada ligação local a um canal SSH para o servidor de base de dados."""

    connection: SSHConnection
    remote_host: str
    remote_port: int

    def handle(self) -> None:
        try:
            transport = self.connection.get_transport()
        except Exception as exc:  # noqa: BLE001
            log(f"! sem ligação SSH ({type(exc).__name__}: {exc}) — ligação recusada")
            self.request.close()
            return

        try:
            channel = transport.open_channel(
                "direct-tcpip",
                (self.remote_host, self.remote_port),
                self.request.getpeername(),
            )
        except Exception as exc:  # noqa: BLE001
            log(f"! não foi possível abrir o canal: {exc}")
            self.request.close()
            return

        if channel is None:
            log("! o servidor recusou o encaminhamento")
            self.request.close()
            return

        try:
            while True:
                readable, _, _ = select.select([self.request, channel], [], [], 60)
                if not readable:
                    if not transport.is_active():
                        break
                    continue
                if self.request in readable:
                    data = self.request.recv(16384)
                    if not data:
                        break
                    channel.sendall(data)
                if channel in readable:
                    data = channel.recv(16384)
                    if not data:
                        break
                    self.request.sendall(data)
        except (OSError, socket.error):
            pass
        finally:
            try:
                channel.close()
            except Exception:  # noqa: BLE001
                pass
            self.request.close()


class ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    ssh_host = env("SSH_HOST", default="")
    ssh_user = env("SSH_USER", default="")
    if not ssh_host or not ssh_user:
        log("Defina SSH_HOST, SSH_PORT, SSH_USER e SSH_PASSWORD no ficheiro .env.")
        return 1

    ssh_key_file = env("SSH_KEY_FILE", default="")
    local_port = env.int("DEV_DB_PORT", default=3307)
    remote_host = env("DEV_DB_REMOTE_HOST", default="127.0.0.1")
    remote_port = env.int("DEV_DB_REMOTE_PORT", default=3306)

    connection = SSHConnection(
        hostname=ssh_host,
        port=env.int("SSH_PORT", default=22),
        username=ssh_user,
        password=env("SSH_PASSWORD", default="") or None,
        key_filename=ssh_key_file or None,
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
        allow_agent=False,
        look_for_keys=bool(ssh_key_file),
    )

    log(f"a ligar a {ssh_user}@{ssh_host}…")
    try:
        connection.get_transport()
    except Exception as exc:  # noqa: BLE001
        # O alojamento pode bloquear temporariamente a porta SSH (por exemplo,
        # após várias ligações pelo cPanel). O encaminhador deve continuar
        # disponível: cada ligação local volta a tentar estabelecer o SSH,
        # sem obrigar o programador a reiniciar este processo.
        log(
            f"SSH temporariamente indisponível: {type(exc).__name__}: {exc}\n"
            "       o túnel continuará ativo e tentará restabelecer-se sozinho."
        )

    handler = type(
        "Handler",
        (ForwardHandler,),
        {
            "connection": connection,
            "remote_host": remote_host,
            "remote_port": remote_port,
        },
    )

    try:
        server = ForwardServer(("127.0.0.1", local_port), handler)
    except OSError as exc:
        log(
            f"não foi possível abrir a porta {local_port}: {exc}\n"
            f"       Provavelmente já existe um túnel a correr. Feche-o e tente de novo."
        )
        connection.close()
        return 1

    log(
        f"pronto: 127.0.0.1:{local_port}  ->  {remote_host}:{remote_port} (no servidor). "
        "Deixe esta janela aberta; Ctrl+C para fechar."
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Vigia a ligação: se cair, reconecta antes de o Django tentar usá-la.
    delay = RECONNECT_DELAY_SECONDS
    try:
        while True:
            time.sleep(KEEPALIVE_SECONDS)
            if connection.transport is not None:
                delay = RECONNECT_DELAY_SECONDS
                continue
            try:
                connection.get_transport()
                delay = RECONNECT_DELAY_SECONDS
            except Exception as exc:  # noqa: BLE001
                log(f"reconexão falhou ({exc}); nova tentativa em {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, MAX_RECONNECT_DELAY_SECONDS)
    except KeyboardInterrupt:
        log("a fechar…")
    finally:
        server.shutdown()
        server.server_close()
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
