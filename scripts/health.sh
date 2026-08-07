#!/usr/bin/env bash
# Health check rápido do libras2 + Hermes
# uso: ./scripts/health.sh [webhook_url]

set -euo pipefail

LIBRAS2_URL=${LIBRAS2_URL:-http://127.0.0.1:8088/health}
LIBRAS2_OK=$(systemctl is-active libras2 2>/dev/null || echo "unknown")

API=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$LIBRAS2_URL" || echo "000")

echo "libras2 service: ${LIBRAS2_OK}"
echo "  /health HTTP : ${API}"

if [[ "$LIBRAS2_OK" != "active" || "$API" != "200" ]]; then
    echo "FAIL — libras2 down"
    [[ -n "${1:-}" ]] && curl -sS -X POST "$1" -d "libras2 down: ${LIBRAS2_OK} /health=${API}" || true
    exit 1
fi
echo "OK"
