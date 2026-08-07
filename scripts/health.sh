#!/usr/bin/env bash
# Health check rápido do vlibras + Hermes
# uso: ./scripts/health.sh [webhook_url]

set -euo pipefail

VLIBRAS_URL=${VLIBRAS_URL:-http://127.0.0.1:8088/health}
HERMES_OK=$(systemctl --user is-active hermes-gateway 2>/dev/null || echo "unknown")
VLIBRAS_OK=$(systemctl is-active vlibras 2>/dev/null || echo "unknown")

API=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$VLIBRAS_URL" || echo "000")

echo "vlibras service: ${VLIBRAS_OK}"
echo "  /health HTTP : ${API}"
echo "hermes gateway : ${HERMES_OK}"

if [[ "$VLIBRAS_OK" != "active" || "$API" != "200" ]]; then
    echo "FAIL — vlibras down"
    [[ -n "${1:-}" ]] && curl -sS -X POST "$1" -d "vlibras down: ${VLIBRAS_OK} /health=${API}" || true
    exit 1
fi
echo "OK"
