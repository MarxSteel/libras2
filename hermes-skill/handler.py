"""Skill Libras pro Hermes Agent.

Como o Hermes carrega:
1. Coloque esta pasta em ~/.hermes/skills/libras/
2. O Hermes descobre via skill.yml abaixo
3. A skill exporta uma função `handle(message, context)` que retorna uma resposta

Convenção de mensagem:
- !libras <texto>  → tradução explícita
- Frases que contenham "em libras", "em sinais", "libras por favor" → intent automático
- Caso contrário → resposta em texto padrão do Hermes (a skill não intercepta)
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("vlibras-skill")

API_URL = os.getenv("VLIBRAS_API_URL", "http://127.0.0.1:8088")
AUTO_TRIGGER = re.compile(
    r"\b(em\s+libras|em\s+sinais?|libras\s+por\s+favor|significa\s+em\s+libras)\b",
    re.IGNORECASE,
)

SKILL_NAME = "libras"
SKILL_VERSION = "0.1.0"


def _extract_text(message: str) -> tuple[str, str]:
    """Devolve (mode, text). mode é 'explicit' | 'auto' | 'none'."""
    m = re.match(r"^\s*!?libras?\s+(.+)$", message, re.IGNORECASE | re.DOTALL)
    if m:
        return "explicit", m.group(1).strip()
    if AUTO_TRIGGER.search(message):
        # tira o gatilho e usa o resto
        cleaned = AUTO_TRIGGER.sub("", message).strip(" .,!?")
        return "auto", cleaned
    return "none", ""


def handle(message: str, context: dict[str, Any]) -> dict[str, Any] | None:
    """Entrypoint chamado pelo Hermes em cada mensagem recebida.

    Retorno:
      None            → deixa o Hermes seguir com a resposta padrão
      dict            → resposta da skill (com mídia se houver)
    """
    mode, text = _extract_text(message)
    if mode == "none" or not text:
        return None

    logger.info("libras skill triggered (%s): %r", mode, text)

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{API_URL}/translate", json={"text": text, "format": "mp4"})
    except httpx.HTTPError as e:
        logger.error("vlibras API unreachable: %s", e)
        return {
            "text": "⚠️ Serviço de Libras indisponível. Tenta de novo em alguns segundos.",
            "media": None,
        }

    if r.status_code != 200:
        logger.warning("vlibras API %s: %s", r.status_code, r.text[:200])
        return {
            "text": f"❌ Não consegui traduzir. ({r.status_code})",
            "media": None,
        }

    body = r.json()
    media_path = _download_media(body["video_url"])
    missing_note = ""
    if body.get("missing"):
        missing_note = (
            f"\n_(palavras sem sinal no vocabulário: "
            f"{', '.join(body['missing'])})_"
        )

    caption = (
        f"🤟 *Libras*: {body['text']}\n"
        f"📝 Gloss: `{' '.join(body['gloss'])}`"
        f"{missing_note}"
    )

    return {
        "text": caption,
        "media": {
            "path": str(media_path),
            "type": "video" if body["format"] == "mp4" else "image",
            "filename": f"libras_{body['text'][:20].strip()}.{body['format']}",
        },
    }


def _download_media(url: str) -> Path:
    """Baixa o MP4/GIF do serviço pro disco local (Hermes espera arquivo)."""
    cache = Path(os.getenv("VLIBRAS_MEDIA_CACHE", "/tmp/vlibras-media"))
    cache.mkdir(parents=True, exist_ok=True)
    fname = url.rsplit("/", 1)[-1]
    out = cache / fname
    if out.exists():
        return out
    with httpx.Client(timeout=30.0) as c:
        r = c.get(f"{API_URL}{url}")
        r.raise_for_status()
        out.write_bytes(r.content)
    return out


# Catálogo pra o Hermes listar a skill na UI
SKILL_MANIFEST = {
    "name": SKILL_NAME,
    "version": SKILL_VERSION,
    "description": (
        "Traduz mensagens em Português para Libras e responde com vídeo. "
        "Use '!libras <texto>' ou peça 'em libras'."
    ),
    "triggers": ["!libras", "em libras", "em sinais"],
    "author": "MarxSteel",
    "homepage": "https://github.com/MarxSteel/vlibras",
}
