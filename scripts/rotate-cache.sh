#!/usr/bin/env bash
# Apaga MP4/GIF do cache com mais de N dias (default 7).
# uso: ./scripts/rotate-cache.sh [dias]
set -euo pipefail

CACHE=${VLIBRAS_CACHE_DIR:-/opt/vlibras/data/cache}
DAYS=${1:-7}

if [[ ! -d "$CACHE" ]]; then
    echo "cache dir not found: $CACHE"
    exit 0
fi

count=$(find "$CACHE" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.gif" \) -mtime +$DAYS | wc -l)
find "$CACHE" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.gif" \) -mtime +$DAYS -print -delete
echo "removed $count file(s) older than $DAYS days from $CACHE"
