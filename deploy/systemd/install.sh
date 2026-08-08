#!/usr/bin/env bash
# Instala libras2 como serviço systemd + cache rotation via cron.
# uso: sudo ./deploy/systemd/install.sh
set -euo pipefail

REPO=${LIBRAS2_REPO:-/opt/libras2}
SERVICE_SRC="$REPO/deploy/systemd/libras2.service"
SERVICE_DST=/etc/systemd/system/libras2.service
CRON_SRC="$REPO/deploy/cron/libras2-cache-rotate"
CRON_DST=/etc/cron.d/libras2-cache-rotate

# garante que estamos no path certo
[[ -f "$SERVICE_SRC" ]] || { echo "FATAL: $SERVICE_SRC não existe"; exit 1; }
[[ -d "$REPO/venv" ]] || { echo "FATAL: $REPO/venv não existe (rode: python3 -m venv $REPO/venv)"; exit 1; }

# 1. systemd unit
install -m 644 "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload
systemctl enable libras2.service
systemctl restart libras2.service

# 2. cron
if [[ -f "$CRON_SRC" ]]; then
    install -m 644 "$CRON_SRC" "$CRON_DST"
else
    # fallback inline
    cat > "$CRON_DST" <<EOF
# Rotate /opt/libras2/data/cache (apaga MP4/GIF > 7 dias) — 3h da manha todo dia
0 3 * * * root $REPO/scripts/rotate-cache.sh 7 >> /var/log/libras2-rotate.log 2>&1
EOF
    chmod 644 "$CRON_DST"
fi

# 3. garante permissões de execução nos scripts
chmod +x "$REPO/scripts/"*.sh "$REPO/scripts/"*.py 2>/dev/null || true
chmod +x "$REPO/clients/"*.sh 2>/dev/null || true

# 3. sanity
sleep 2
echo "--- status ---"
systemctl status libras2 --no-pager | head -8
echo "--- health ---"
curl -sS --max-time 3 http://127.0.0.1:8088/health | head -c 200
echo
echo "OK — libras2 instalado e rodando"
