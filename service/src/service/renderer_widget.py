"""Renderer headless: usa o widget OFICIAL do VLibras (avatar 3D real) + Playwright.

Pipeline:
1. Lança Chromium headless via Playwright
2. Carrega o nosso player (/signs/play?text=...) que embedda o widget oficial
   do VLibras (https://vlibras.gov.br/app/vlibras-plugin.js) — esse widget tem o
   avatar 3D (Ícaro) que faz os sinais com as mãos.
3. Espera o widget inicializar (~12s pro Unity WebGL subir)
4. Tenta clicar no botão de tradução do widget
5. Captura screenshots em loop durante a animação
6. Concatena os frames em MP4 ou GIF com ffmpeg
7. Cacheia em disco por hash

AVISO: pesado (Chromium ~500MB em disco, ~300MB RAM por execução).
Cache em disco evita re-render se a mesma frase for pedida de novo.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _cache_key(text: str, fmt: str) -> str:
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"widget_{h}.{fmt}"


async def _render_widget_async(text: str, api_base: str, cache_dir: Path, fmt: str) -> Path:
    """Renderiza o player oficial do VLibras e captura frames."""
    from playwright.async_api import async_playwright

    player_url = f"{api_base}/signs/play?text={text.replace(' ', '+')}"

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / _cache_key(text, fmt)
    if out_path.exists() and out_path.stat().st_size > 1000:
        logger.info("widget render cache hit: %s", out_path.name)
        return out_path

    # usa cache_dir como TMPDIR (sistema é read-only em /tmp)
    tmp = Path(tempfile.mkdtemp(prefix="libras2-widget-", dir=str(cache_dir)))
    os.environ["TMPDIR"] = str(tmp)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--use-gl=swiftshader",
                "--enable-webgl",
                "--ignore-gpu-blocklist",
            ])
            try:
                context = await browser.new_context(viewport={"width": 1280, "height": 800})
                page = await context.new_page()
                logger.info("loading %s", player_url)
                await page.goto(player_url, wait_until="domcontentloaded", timeout=30000)

                # espera o widget VLibras inicializar (Unity WebGL é pesado)
                logger.info("waiting 12s for Unity WebGL init...")
                await page.wait_for_timeout(12000)

                # tenta clicar no botão de tradução do widget
                clicked = False
                for sel in ["[vw-access-button]", ".vpw-btn-play", "div[vp-play]", "[vp-play]"]:
                    try:
                        btn = page.locator(sel).first
                        if await btn.count() > 0:
                            await btn.click(force=True, timeout=2000)
                            logger.info("clicked %s", sel)
                            clicked = True
                            break
                    except Exception as e:
                        logger.debug("click %s failed: %s", sel, e)
                if not clicked:
                    logger.warning("could not click widget — animation may auto-start")

                # captura frames durante a animação
                words = text.split()
                duration_s = max(5.0, min(25.0, len(words) * 2.0 + 3.0))
                fps = 5
                total_frames = int(duration_s * fps)
                interval_s = 1.0 / fps
                logger.info("capturing %d frames (%.1fs @ %dfps)", total_frames, duration_s, fps)
                for i in range(total_frames):
                    frame_path = tmp / f"frame_{i:05d}.png"
                    await page.screenshot(path=str(frame_path), full_page=False)
                    if i % fps == 0:
                        logger.info("frame %d/%d", i + 1, total_frames)
                    await page.wait_for_timeout(interval_s * 1000)

                await context.close()
            finally:
                await browser.close()

        # concatena em MP4 ou GIF
        frame_paths = sorted(tmp.glob("frame_*.png"))
        if not frame_paths:
            raise RuntimeError("nenhum frame capturado")

        list_file = tmp / "list.txt"
        list_file.write_text(
            "\n".join(f"file '{p.resolve()}'\nduration 0.2\n" for p in frame_paths) + "\n"
        )

        if fmt == "mp4":
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-vsync", "vfr",
                "-vf", "scale=1280:-2,format=yuv420p",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(out_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        else:  # gif
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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_widget(text: str, api_base: str, cache_dir: Path, fmt: str = "mp4") -> Path:
    """Wrapper síncrono do renderer com Playwright."""
    return asyncio.run(_render_widget_async(text, api_base, cache_dir, fmt))
