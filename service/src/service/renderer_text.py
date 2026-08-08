"""Renderer de texto → MP4/GIF (representação visual da glosa).

AVISO: NÃO é o avatar 3D oficial do VLibras. É uma visualização estilizada
da glosa gerada pelo VLibras oficial (palavras em sequência, com tipografia).

Por que isso existe: o player Unity do VLibras é proprietário e não
embedável standalone. Este renderer dá ao usuário um MP4/GIF compartilhável
que representa a tradução de forma visual.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# procura fonte do sistema
def _find_font() -> Path:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    raise FileNotFoundError("nenhuma fonte TTF encontrada em /usr/share/fonts")


_FONT_PATH: Path | None = None


def _font(size: int) -> ImageFont.FreeTypeFont:
    global _FONT_PATH
    if _FONT_PATH is None:
        _FONT_PATH = _find_font()
    return ImageFont.truetype(str(_FONT_PATH), size)


# cores
BG = (10, 12, 28)
FG = (235, 235, 245)
ACCENT = (122, 170, 255)
DIM = (90, 90, 110)
GREEN = (125, 255, 184)
ORANGE = (255, 170, 125)

W, H = 800, 600


def _draw_centered(draw, y, text, font, color):
    draw.text((W // 2, y), text, fill=color, font=font, anchor="mm")


def _frame_title(text: str, gloss: list[str], msg: str = "Tradução Libras") -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _draw_centered(d, 80, "🤟 libras2", _font(56), ACCENT)
    _draw_centered(d, 200, msg, _font(34), FG)
    # caixa do texto original
    d.rectangle([60, 270, W - 60, 360], outline=DIM, width=2)
    _draw_centered(d, 315, f'"{text}"', _font(28), FG)
    # glosa
    _draw_centered(d, 450, "Glosa oficial:", _font(22), DIM)
    _draw_centered(d, 510, " ".join(gloss), _font(40), ACCENT)
    return img


def _frame_word(i: int, total: int, word: str, gloss: list[str], text: str) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _draw_centered(d, 60, f"Sinal {i} de {total}", _font(24), DIM)
    # palavra atual destacada
    _draw_centered(d, H // 2, word, _font(96), GREEN)
    # barra de progresso
    bar_w = W - 120
    progress = i / total
    d.rectangle([60, H - 130, 60 + bar_w, H - 110], outline=DIM, width=2)
    d.rectangle([62, H - 128, 62 + int(bar_w * progress), H - 112], fill=ACCENT)
    # glosa completa atualizada
    _draw_centered(d, H - 70, " ".join(gloss), _font(28), FG)
    return img


def _frame_end(text: str, gloss: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _draw_centered(d, 100, "✅ Pronto", _font(48), GREEN)
    _draw_centered(d, 200, text, _font(28), DIM)
    _draw_centered(d, H // 2 + 20, " ".join(gloss), _font(48), ACCENT)
    _draw_centered(d, H - 80, "libras2 — tradução PT → Libras", _font(20), DIM)
    return img


def _cache_key(text: str, gloss: list[str], fmt: str) -> str:
    h = hashlib.sha256((text + "|" + " ".join(gloss) + "|" + fmt).encode()).hexdigest()[:16]
    return f"{h}.{fmt}"


def render(text: str, gloss: list[str], cache_dir: Path, fmt: str = "mp4") -> Path:
    """Gera MP4 ou GIF a partir de texto + gloss. Cache por hash."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_name = _cache_key(text, gloss, fmt)
    out_path = cache_dir / out_name
    if out_path.exists() and out_path.stat().st_size > 100:
        logger.info("renderer cache hit: %s", out_path.name)
        return out_path

    # cada frame vira um PNG; copiamos N vezes pra ter duração por frame
    # usa o cache_dir (que já tem permissão) ao invés de /tmp
    tmp = Path(tempfile.mkdtemp(prefix="libras2-render-", dir=str(cache_dir)))
    try:
        frames = []
        # título: 2 cópias (~1.5s)
        title = _frame_title(text, gloss)
        title_path = tmp / "title.png"
        title.save(title_path)
        frames.append(title_path)
        frames.append(title_path)  # 2x = ~1.5s

        # uma palavra por vez: 2 cópias cada
        total = len(gloss)
        for i, w in enumerate(gloss, 1):
            p = tmp / f"word_{i:03d}.png"
            _frame_word(i, total, w, gloss, text).save(p)
            frames.append(p)
            frames.append(p)  # 2x = ~1.5s por palavra

        # final: 4 cópias (~3s)
        end = _frame_end(text, gloss)
        end_path = tmp / "end.png"
        end.save(end_path)
        for _ in range(4):
            frames.append(end_path)

        # monta filelist
        list_file = tmp / "list.txt"
        list_file.write_text("\n".join(f"file '{p.resolve()}'\nduration 0.75\n" for p in frames) + "\n")

        if fmt == "mp4":
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-vsync", "vfr",
                "-vf", "scale=800:-2,format=yuv420p",
                "-movflags", "+faststart",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(out_path),
            ]
        else:  # gif
            # 2-pass: paleta + gif
            palette = tmp / "palette.png"
            scale = "scale=800:-1:flags=lanczos"
            cmd1 = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-vf", f"{scale},palettegen=stats_mode=diff",
                str(palette),
            ]
            cmd2 = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file), "-i", str(palette),
                "-lavfi", f"{scale} [x]; [x][1:v] paletteuse=dither=sierra2_4a",
                str(out_path),
            ]
            subprocess.run(cmd1, check=True, capture_output=True)
            subprocess.run(cmd2, check=True, capture_output=True)
            return out_path

        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
