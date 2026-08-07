#!/usr/bin/env bash
# Wrapper CLI pra vlibras API.
# uso:  ./cli.sh "bom dia"
#       ./cli.sh "bom dia" --gif
#       ./cli.sh --health
#
# Requer: curl, jq
set -euo pipefail

API=${VLIBRAS_API:-http://127.0.0.1:8088}
FMT=mp4
TEXT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --api)  API="$2"; shift 2 ;;
        --gif)  FMT=gif; shift ;;
        --mp4)  FMT=mp4; shift ;;
        --health) curl -sS "$API/health" | jq . && exit 0 ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        --*)    echo "unknown flag: $1" >&2; exit 1 ;;
        *)      TEXT="$1"; shift ;;
    esac
done

if [[ -z "$TEXT" ]]; then
    echo "uso: $0 'sua frase aqui' [--gif|--mp4] [--api URL]"
    exit 1
fi

tmp=$(mktemp -d)
trap "rm -rf $tmp" EXIT

echo "→ traduzindo: $TEXT (fmt=$FMT)"

resp=$(curl -sS -X POST "$API/translate" \
    -H 'content-type: application/json' \
    -d "$(jq -nc --arg t "$TEXT" --arg f "$FMT" '{text:$t, format:$f}')")

echo "$resp" | jq '{text, gloss, missing, format, video_url}'

filename=$(echo "$resp" | jq -r '.video_url' | sed 's|^/videos/||')
out="libras_${TEXT// /_}.${FMT}"

echo "↓ baixando vídeo pra ./$out"
curl -sS -o "$out" "$API/videos/$filename"
ls -lh "$out"
