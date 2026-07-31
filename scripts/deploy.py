"""
Deploy para o servidor cPanel (Passenger) por SSH/SFTP.

    python scripts/deploy.py            # envia os ficheiros alterados desde o último deploy
    python scripts/deploy.py --all      # envia todos os ficheiros versionados
    python scripts/deploy.py --since <commit>

O que faz, por esta ordem:
  1. envia os ficheiros versionados (a lista vem do git, por isso nunca
     inclui `.env`, `media/`, `staticfiles/` nem a base local);
  2. envia uma cópia do `.env` adaptada ao servidor;
  3. `check --deploy`, `collectstatic` e reinício da aplicação.

Nunca corre `migrate`: as migrações são executadas de propósito à parte,
depois de rever o que vai ser aplicado (ver DEPLOYMENT.md §14).

Credenciais lidas do `.env`: SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD.
Requer `paramiko` (requirements-dev.txt).
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import environ
    import paramiko
except ImportError:  # pragma: no cover
    sys.exit("Faltam dependências: pip install -r requirements-dev.txt")

env = environ.Env()
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(str(BASE_DIR / ".env"))

APP_ROOT = env("DEPLOY_APP_ROOT", default="/home/salacsth/meuconvite")
VENV_BIN = env("DEPLOY_VENV_BIN", default="/home/salacsth/virtualenv/meuconvite/3.12/bin")
APP_NAME = env("DEPLOY_APP_NAME", default="meuconvite")

# Variáveis que só fazem sentido na máquina de desenvolvimento e que não
# devem existir no servidor (nomeadamente as credenciais de SSH).
LOCAL_ONLY_PREFIXES = ("SSH_", "DEV_DB_", "DEMO_USER_PASSWORD")


def build_server_env(local_env_text: str) -> str:
    """Adapta o `.env` local ao servidor: activa as settings de produção e retira o que é local."""
    lines = []
    for line in local_env_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(LOCAL_ONLY_PREFIXES):
            continue
        if stripped == "# DJANGO_SETTINGS_MODULE=config.settings.production":
            lines.append("DJANGO_SETTINGS_MODULE=config.settings.production")
            continue
        lines.append(line)
    text = "\n".join(lines) + "\n"
    if "\nDJANGO_SETTINGS_MODULE=config.settings.production" not in f"\n{text}":
        raise SystemExit(
            "O `.env` não define DJANGO_SETTINGS_MODULE de produção — deploy cancelado."
        )
    return text


def files_to_send(since: str | None, send_all: bool) -> list[str]:
    """
    Ficheiros a enviar.

    `--all` envia tudo o que o git conhece **e** os ficheiros novos que
    ainda não foram adicionados — respeitando sempre o `.gitignore`, para
    que `.env`, `media/` e a base local nunca sejam enviados por aqui.
    Sem isto, uma funcionalidade nova (ficheiros ainda por comitar) chegava
    ao servidor pela metade.
    """
    if send_all or not since:
        command = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    else:
        command = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{since}..HEAD"]
    result = subprocess.run(command, cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    return sorted({line for line in result.stdout.splitlines() if line.strip()})


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    current = ""
    for part in remote_dir.strip("/").split("/"):
        current = f"{current}/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def run(client: paramiko.SSHClient, command: str, label: str, timeout: int = 900) -> int:
    print(f"\n===== {label} =====")
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace").strip()
    err = stderr.read().decode("utf-8", "replace").strip()
    encoding = sys.stdout.encoding or "utf-8"
    if out:
        print(out.encode(encoding, "replace").decode(encoding))
    if err:
        print(err.encode(encoding, "replace").decode(encoding))
    return stdout.channel.recv_exit_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy do MeuConvite para o cPanel.")
    parser.add_argument("--all", action="store_true", help="Enviar todos os ficheiros versionados.")
    parser.add_argument("--since", default="HEAD~1", help="Enviar o que mudou desde este commit.")
    args = parser.parse_args()

    paths = files_to_send(args.since, args.all)
    if not paths:
        print("Nada para enviar.")
        return 0

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=env("SSH_HOST"),
        port=env.int("SSH_PORT", default=22),
        username=env("SSH_USER"),
        password=env("SSH_PASSWORD", default="") or None,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )

    sftp = client.open_sftp()
    created: set[str] = set()
    sent = 0
    for relative in paths:
        local_path = BASE_DIR / relative
        if not local_path.is_file():
            continue
        remote_path = f"{APP_ROOT}/{relative}"
        parent = str(pathlib.PurePosixPath(remote_path).parent)
        if parent not in created:
            sftp_mkdirs(sftp, parent)
            created.add(parent)
        sftp.put(str(local_path), remote_path)
        sent += 1
        print(f"  {relative}")

    server_env = build_server_env((BASE_DIR / ".env").read_text(encoding="utf-8"))
    with sftp.open(f"{APP_ROOT}/.env", "w") as handle:
        handle.write(server_env)
    sftp.chmod(f"{APP_ROOT}/.env", 0o600)
    sftp.close()
    print(f"\n{sent} ficheiro(s) enviado(s) + .env (600)")

    run(client, f"cd {APP_ROOT} && {VENV_BIN}/python manage.py check --deploy 2>&1 | tail -8", "check --deploy")
    run(client, f"cd {APP_ROOT} && {VENV_BIN}/python manage.py collectstatic --noinput 2>&1 | tail -3", "collectstatic")
    run(
        client,
        f"cloudlinux-selector restart --json --interpreter python --app-root {APP_NAME} 2>&1 | head -3",
        "reiniciar aplicação",
        timeout=300,
    )
    run(client, "curl -sS -o /dev/null -w 'https://meuconvite.co.mz/ -> %{http_code}\\n' https://meuconvite.co.mz/", "verificação")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
