#!/bin/bash
# =====================================================================
# MeuConvite — daily database backup (cPanel cron job)
#
# Credentials are read from a MySQL defaults file (chmod 600) so the
# password never appears in the crontab or in the process list.
#
#   ~/.meuconvite.my.cnf
#   [client]
#   user=...
#   password=...
#
# Install as a cron job (daily, 02:00):
#   0 2 * * * /home/<UTILIZADOR>/meuconvite/scripts/backup_db.sh >> /home/<UTILIZADOR>/meuconvite/logs/backup.log 2>&1
# =====================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
DEFAULTS_FILE="${DEFAULTS_FILE:-$HOME/.meuconvite.my.cnf}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# Read the database name from .env without exposing any other value.
DB_NAME="$(grep -E '^DB_NAME=' "$APP_DIR/.env" | head -1 | cut -d= -f2-)"

if [ -z "$DB_NAME" ]; then
    echo "$(date '+%F %T') ERRO: DB_NAME não encontrado em $APP_DIR/.env" >&2
    exit 1
fi

if [ ! -f "$DEFAULTS_FILE" ]; then
    echo "$(date '+%F %T') ERRO: ficheiro de credenciais $DEFAULTS_FILE não existe" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F_%H%M)"
TARGET="$BACKUP_DIR/meuconvite_${STAMP}.sql.gz"

mysqldump --defaults-extra-file="$DEFAULTS_FILE" \
    --single-transaction --quick --default-character-set=utf8mb4 \
    --routines --triggers --events \
    "$DB_NAME" | gzip -9 > "$TARGET"

chmod 600 "$TARGET"

# Refuse to keep an obviously broken (empty) dump.
if [ ! -s "$TARGET" ]; then
    echo "$(date '+%F %T') ERRO: o backup ficou vazio, ficheiro removido" >&2
    rm -f "$TARGET"
    exit 1
fi

SIZE="$(du -h "$TARGET" | cut -f1)"
echo "$(date '+%F %T') backup criado: $TARGET ($SIZE)"

# Remove only this project's old dumps, never anything else.
find "$BACKUP_DIR" -maxdepth 1 -name 'meuconvite_*.sql.gz' -type f \
    -mtime +"$RETENTION_DAYS" -print -delete
