"""Cliente do dicionário oficial VLibras.

Source: https://dicionario2.vlibras.gov.br
Docs:   https://github.com/spbgovbr-vlibras/vlibras-dictionary-api
        (openapi.json no src/app/doc)

Endpoint GET /{version}/{platform}/{sign} → redireciona pro CDN
com a animação 3D (.glb) do sinal. Aceita 22.498 sinais.

Cache:
  - Memória: LRU de 500 .glb
  - Disco:  /opt/libras2/data/dictionary/{version}/{platform}/{sign}.glb
  - Trie:   /opt/libras2/data/dictionary/signs-trie-{version}.json (índice completo)
"""
from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://dicionario2.vlibras.gov.br"
DEFAULT_VERSION = "2018.3.1"
DEFAULT_PLATFORM = "WEBGL"
DEFAULT_TIMEOUT = 30.0
CACHE_MAX_MEMORY = 500


class Dictionary:
    def __init__(
        self,
        base: str = DEFAULT_BASE,
        version: str = DEFAULT_VERSION,
        platform: str = DEFAULT_PLATFORM,
        cache_dir: Optional[Path] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base = base.rstrip("/")
        self.version = version
        self.platform = platform
        self.cache_dir = cache_dir or Path(
            os.getenv("LIBRAS2_DICT_DIR", "/opt/libras2/data/dictionary")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._mem: OrderedDict[str, bytes] = OrderedDict()
        self._trie: Optional[dict] = None
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    # --- index / trie -------------------------------------------------------

    def get_trie(self, force_refresh: bool = False) -> dict:
        """Carrega o índice completo de sinais (formato trie JSON)."""
        if self._trie is not None and not force_refresh:
            return self._trie
        trie_path = self.cache_dir / f"signs-trie-{self.version}.json"
        if not force_refresh and trie_path.exists():
            logger.info("loading trie from cache: %s", trie_path)
            self._trie = json.loads(trie_path.read_text(encoding="utf-8"))
            return self._trie
        url = f"{self.base}/signs?version={self.version}"
        logger.info("fetching trie from %s", url)
        r = self._client.get(url)
        r.raise_for_status()
        trie_path.write_bytes(r.content)
        self._trie = json.loads(r.content)
        return self._trie

    def has_sign(self, word: str) -> bool:
        """Checa se a palavra existe no dicionário (accent-insensitive)."""
        try:
            return self.find_canonical(word) is not None
        except Exception as e:
            logger.warning("has_sign failed: %s", e)
            return True  # assume que existe se não consegue checar

    def find_canonical(self, word: str) -> Optional[str]:
        """Acha a grafia exata (com acento) no trie, dado o input normalizado.

        Ex: find_canonical("AGUA") -> "ÁGUA"
            find_canonical("FAMILIA") -> "FAMÍLIA"
        """
        import unicodedata
        try:
            trie = self.get_trie()
        except Exception:
            return None
        root = trie.get("root", trie)
        target = word.strip().upper()
        # normaliza target
        target_norm = "".join(
            c for c in unicodedata.normalize("NFD", target)
            if unicodedata.category(c) != "Mn"
        )

        def walk(node, prefix, remaining_norm, remaining_orig):
            if not remaining_norm:
                return prefix if node.get("end") else None
            children = node.get("children") or {}
            want = remaining_norm[0]
            for c in children:
                c_norm = "".join(
                    ch for ch in unicodedata.normalize("NFD", c)
                    if unicodedata.category(ch) != "Mn"
                )
                if c_norm == want:
                    got = walk(children[c], prefix + c, remaining_norm[1:], remaining_orig[1:])
                    if got is not None:
                        return got
            return None
        return walk(root, "", target_norm, target)

    def all_signs(self) -> list[str]:
        """Lista todos os sinais do dicionário."""
        try:
            trie = self.get_trie()
        except Exception as e:
            logger.warning("trie fetch failed: %s", e)
            return []
        out: list[str] = []
        def walk(node, prefix):
            if node.get("end"):
                out.append(prefix)
            for c, sub in (node.get("children") or {}).items():
                walk(sub, prefix + c)
        walk(trie.get("root", trie), "")
        return out

    def vocab_size(self) -> int:
        try:
            return len(self.all_signs())
        except Exception:
            return 0

    # --- .glb fetch ---------------------------------------------------------

    def get_glb(self, word: str) -> bytes:
        """Retorna o conteúdo .glb do sinal. Mem cache → disk cache → network.

        Primeiro resolve a grafia canônica (com acento) via trie, depois baixa.
        Valida magic bytes do GLB (descarta respostas HTML de erro).
        """
        word = word.strip()
        if not word:
            raise ValueError("empty word")

        key = word.upper()
        if key in self._mem:
            self._mem.move_to_end(key)
            return self._mem[key]

        # resolve grafia canônica (ÁGUA) a partir do input (AGUA)
        canonical = self.find_canonical(word) or word
        url_word = canonical.replace(" ", "%20")
        url = f"{self.base}/{self.version}/{self.platform}/{url_word}"

        # disk cache
        path = self._disk_path(canonical)
        if path.exists():
            data = path.read_bytes()
            if _is_glb(data):
                self._mem_put(key, data)
                return data
            path.unlink(missing_ok=True)

        # network
        logger.info("fetching glb from %s", url)
        r = self._client.get(url)
        if r.status_code == 404:
            raise KeyError(f"sign not found: {word!r} (canonical: {canonical!r})")
        r.raise_for_status()
        data = r.content
        if not _is_glb(data):
            raise KeyError(f"non-GLB response for {word!r} (size={len(data)})")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._mem_put(key, data)
        return data

    def _disk_path(self, word: str) -> Path:
        # safe filename: mantém acentos, troca caracteres problemáticos
        safe = "".join(c if c.isalnum() or c in "-_ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ" else "_" for c in word)
        return self.cache_dir / self.version / self.platform / f"{safe}.glb"

    def _mem_put(self, word: str, data: bytes) -> None:
        self._mem[word] = data
        self._mem.move_to_end(word)
        if len(self._mem) > CACHE_MAX_MEMORY:
            self._mem.popitem(last=False)

    def close(self) -> None:
        self._client.close()


# Singleton lazy
_dictionary: Dictionary | None = None


def get_dictionary() -> Dictionary:
    global _dictionary
    if _dictionary is None:
        cache_dir = Path(os.getenv("LIBRAS2_DICT_DIR", "/opt/libras2/data/dictionary"))
        _dictionary = Dictionary(
            base=os.getenv("LIBRAS2_DICT_URL", DEFAULT_BASE),
            version=os.getenv("LIBRAS2_DICT_VERSION", DEFAULT_VERSION),
            platform=os.getenv("LIBRAS2_DICT_PLATFORM", DEFAULT_PLATFORM),
            cache_dir=cache_dir,
        )
    return _dictionary


def _is_glb(data: bytes) -> bool:
    """Valida magic bytes do GLB (`glTF`)."""
    # GLB começa com magic `glTF` (0x46546c67) + versão uint32 (1 ou 2).
    if len(data) < 12:
        return False
    return data[:4] == b"glTF"
