"""Wrapper do sign-language-translator.

Responsabilidades:
- Carregar o dicionário de vídeos (1 sinal por palavra, escolhe variante aleatória).
- Mapear tokens PT-BR -> gloss (reordenação de gramática pra Libras).
- Reportar palavras ausentes (vão pra fallback de datilologia).

TODO Fase 1: trocar implementação stub pelo `ConcatenativeSynthesis` real.
Ver: https://github.com/sign-language-translator/sign-language-translator
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.videos_dir = data_dir / "videos"
        self.index: dict[str, list[Path]] = {}
        self._load_index()

    @property
    def vocab_size(self) -> int:
        return len(self.index)

    def _load_index(self) -> None:
        """Indexa data/vlibrasil/videos/{palavra}/{signer_id}.mp4."""
        if not self.videos_dir.exists():
            logger.warning(
                "vlibrasil dataset not found at %s — run scripts/download_vlibrasil.py",
                self.videos_dir,
            )
            return
        for word_dir in self.videos_dir.iterdir():
            if not word_dir.is_dir():
                continue
            word = word_dir.name
            videos = sorted(word_dir.glob("*.mp4"))
            if videos:
                self.index[word] = videos

    def lookup_video(self, word: str) -> Path | None:
        """Retorna um vídeo aleatório da palavra (3 sinalizantes no V-LIBRASIL)."""
        options = self.index.get(word)
        if not options:
            return None
        return random.choice(options)

    def to_gloss(self, tokens: list[str]) -> tuple[list[str], list[str]]:
        """Tokens PT -> gloss + lista de palavras ausentes.

        Stub: identidade (cada token vira gloss). Vai crescer com:
        - reordenação SOV (Libras usa SOV, português usa SVO)
        - lematização (correndo->correr)
        - expansão de gírias
        """
        present: list[str] = []
        missing: list[str] = []
        for tok in tokens:
            if tok in self.index:
                present.append(tok)
            else:
                missing.append(tok)
        return present, missing
