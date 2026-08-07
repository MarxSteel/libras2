"""Cliente do backend oficial do VLibras (https://traducao2.vlibras.gov.br/translate).

Usado pra traduzir Português → glosa Libras quando não temos dataset local,
ou pra melhorar a qualidade do gloss quando temos.

Cache em memória (LRU simples) por hash do texto.
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)

VLIBRAS_TRANSLATE_URL = "https://traducao2.vlibras.gov.br/translate"
DEFAULT_TIMEOUT = 10.0
CACHE_MAX = 1000


class VLibrasBackend:
    def __init__(
        self,
        url: str = VLIBRAS_TRANSLATE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        cache_max: int = CACHE_MAX,
    ):
        self.url = url
        self.timeout = timeout
        self._cache: OrderedDict[str, list[str]] = OrderedDict()
        self._cache_max = cache_max
        self._client = httpx.Client(timeout=timeout)

    def translate(self, text: str) -> list[str]:
        """Retorna lista de tokens de glosa (uppercase, ordem Libras).

        Levanta httpx.HTTPError em falha de rede.
        Retorna [] se a resposta for vazia ou inválida.
        """
        text = text.strip()
        if not text:
            return []

        cached = self._cache_get(text)
        if cached is not None:
            return cached

        try:
            r = self._client.post(self.url, json={"text": text})
        except httpx.HTTPError as e:
            logger.warning("vlibras backend unreachable: %s", e)
            raise

        if r.status_code != 200:
            logger.warning(
                "vlibras backend %s: %s", r.status_code, r.text[:200]
            )
            return []

        body = (r.text or "").strip()
        # Resposta típica: "BOM DIA" ou "BOM DIA COMO VAI"
        gloss = [t for t in body.split() if t]
        self._cache_put(text, gloss)
        return gloss

    def _cache_get(self, text: str) -> list[str] | None:
        key = self._key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, text: str, gloss: list[str]) -> None:
        key = self._key(text)
        self._cache[key] = gloss
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.lower().encode()).hexdigest()

    def close(self) -> None:
        self._client.close()


# Singleton lazy
_backend: VLibrasBackend | None = None


def get_backend() -> VLibrasBackend:
    global _backend
    if _backend is None:
        _backend = VLibrasBackend(
            url=os.getenv("LIBRAS2_VLIBRAS_URL", VLIBRAS_TRANSLATE_URL),
            timeout=float(os.getenv("LIBRAS2_VLIBRAS_TIMEOUT", DEFAULT_TIMEOUT)),
        )
    return _backend
