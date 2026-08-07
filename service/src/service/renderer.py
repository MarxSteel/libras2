"""Render de uma sequência de glosses em MP4 (ou GIF) usando ffmpeg concat.

Pipeline:
1. Para cada gloss, resolve o vídeo do dicionário.
2. Escreve um filelist no formato `file '...'` aceito por `ffmpeg -f concat`.
3. Concatena com `-c copy` (sem reencode) pra velocidade.
4. Se format=gif, gera paleta + gif em duas passadas.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

FFMPEG = "ffmpeg"


def _cache_key(tokens: list[str], fmt: str) -> str:
    h = hashlib.sha256(("|".join(tokens) + f"|{fmt}").encode()).hexdigest()[:16]
    return f"{h}.{fmt}"


def render(
    tokens: list[str],
    data_dir: Path,
    cache_dir: Path,
    fmt: str = "mp4",
) -> Path:
    """Concatena os vídeos de cada gloss e devolve o path do arquivo final."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_name = _cache_key(tokens, fmt)
    out_path = cache_dir / out_name

    if out_path.exists():
        logger.info("cache hit: %s", out_path.name)
        return out_path

    videos_dir = data_dir / "videos"
    paths: list[Path] = []
    for tok in tokens:
        word_dir = videos_dir / tok
        if not word_dir.exists():
            logger.warning("no video for gloss %r — skipping", tok)
            continue
        # pega a primeira variante disponível (determinístico pro cache)
        candidates = sorted(word_dir.glob("*.mp4"))
        if candidates:
            paths.append(candidates[0])

    if not paths:
        raise FileNotFoundError(f"no videos found for tokens={tokens}")

    # filelist temporário
    list_file = cache_dir / f"{out_path.stem}.list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in paths) + "\n"
    )

    if fmt == "mp4":
        cmd = [
            FFMPEG, "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy",
            "-movflags", "+faststart",
            str(out_path),
        ]
    elif fmt == "gif":
        # Duas passadas: paleta + gif
        palette = cache_dir / f"{out_path.stem}.palette.png"
        scale = "scale=480:-1:flags=lanczos"
        cmd1 = [
            FFMPEG, "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-vf", f"{scale},palettegen=stats_mode=diff",
            str(palette),
        ]
        cmd2 = [
            FFMPEG, "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-i", str(palette),
            "-lavfi", f"{scale} [x]; [x][1:v] paletteuse=dither=sierra2_4a",
            str(out_path),
        ]
        subprocess.run(cmd1, check=True, capture_output=True)
        subprocess.run(cmd2, check=True, capture_output=True)
        list_file.unlink(missing_ok=True)
        palette.unlink(missing_ok=True)
        return out_path
    else:
        raise ValueError(f"unsupported format: {fmt}")

    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return out_path
