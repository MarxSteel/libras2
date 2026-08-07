#!/usr/bin/env python3
"""Baixa o dataset V-LIBRASIL pra data/vlibrasil/.

Origens conhecidas (verificar disponibilidade antes de rodar):
- Zenodo (record do paper "Less is more: concatenating videos...")
  https://zenodo.org/record/8320666
- Hugging Face (mirror mantido por terceiros)
- GitHub do paper

Uso:
  python scripts/download_vlibrasil.py [--out data/vlibrasil]
"""
from __future__ import annotations

import argparse
import logging
import sys
import urllib.request
import zipfile
from pathlib import Path

# URLs candidatas — manter em ordem de preferência
CANDIDATES = [
    # Zenodo V-LIBRASIL (4.089 vídeos, 1.364 sinais, 3 sinalizantes)
    "https://zenodo.org/records/8320666/files/v-librasil.zip?download=1",
    # Hugging Face (link hipotético, verificar antes)
    # "https://huggingface.co/datasets/<org>/v-librasil/resolve/main/videos.zip",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("download_vlibrasil")


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "videos"
    if target.exists() and any(target.iterdir()):
        log.info("dataset already present at %s — skipping", target)
        return 0

    for url in CANDIDATES:
        log.info("trying %s", url)
        try:
            archive = out_dir / "v-librasil.zip"
            urllib.request.urlretrieve(url, archive)
        except Exception as e:
            log.warning("failed %s: %s", url, e)
            continue

        log.info("extracting %s", archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(out_dir)
        archive.unlink(missing_ok=True)

        # normaliza o path esperado
        if (out_dir / "videos").exists() and not target.exists():
            (out_dir / "videos").rename(target)
        elif not target.exists():
            log.error("extracted archive has no 'videos/' dir — check layout")
            return 1

        log.info("done. videos at %s", target)
        return 0

    log.error("no candidate URL worked. baixe manualmente de "
              "https://zenodo.org e extraia em %s", out_dir)
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parents[1] / "data" / "vlibrasil")
    args = p.parse_args()
    sys.exit(main(args.out))
