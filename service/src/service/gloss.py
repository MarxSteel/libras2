"""Normalização PT-BR para gloss.

TODO Fase 1: integrar com tokenizador mais sofisticado (spaCy pt_core_news_sm)
ou com o tokenizador nativo do sign-language-translator.
Por enquanto: lowercase + strip acentos + remove pontuação + split em whitespace.
"""
from __future__ import annotations

import re
import unicodedata

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_pt(text: str) -> list[str]:
    """Devolve a lista de tokens normalizados para lookup no dicionário.

    - lowercase
    - remove acentos (lookup geralmente usa versão sem acento)
    - remove pontuação
    - colapsa whitespace
    """
    text = text.lower().strip()
    text = _strip_accents(text)
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text.split() if text else []
