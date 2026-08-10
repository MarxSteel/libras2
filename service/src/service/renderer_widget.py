"""Renderer headless: usa o widget OFICIAL do VLibras (avatar 3D real) + Playwright.

Pipeline:
1. Lança Chromium headless via Playwright
2. Carrega o nosso player (/signs/play?text=...) que embedda o widget oficial
   do VLibras (https://vlibras.gov.br/app/vlibras-plugin.js) — esse widget tem o
   avatar 3D (Ícaro) que faz os sinais com as mãos.
3. Espera o widget inicializar (~12s pro Unity WebGL subir)
4. Via page.evaluate, força o widget a ocupar 100vw x 100vh:
   - encontra o iframe interno (Unity WebGL)
   - redimensiona wrapper + iframe + tudo
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
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


def _cache_key(text: str, fmt: str) -> str:
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"widget_{h}.{fmt}"


# JS que roda DEPOIS do widget inicializar pra forçar fullscreen.
# O widget VLibras renderiza o Unity WebGL dentro de:
#   div[vw] → div[vw-plugin-wrapper] → div → #gameContainer.emscripten → canvas#canvas
# Por padrão tudo é 300x450px. A gente força 100vw x 100vh em todos.
_FULLSCREEN_JS = r"""
async () => {
  const w = window.innerWidth;
  const h = window.innerHeight;

  // clica no access button (avatar pequeno) pra abrir o player
  const btn = document.querySelector('[vw-access-button]');
  if (btn) btn.click();

  // espera o canvas do Unity WebGL aparecer (até 25s)
  let canvas = null;
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 500));
    canvas = document.querySelector('canvas');
    if (canvas && canvas.clientWidth > 100) break;
    if (i === 5 || i === 15) {
      const b = document.querySelector('[vw-access-button]');
      if (b) b.click();
    }
  }
  if (!canvas) {
    return {error: 'canvas não apareceu em 25s', has_canvas: false};
  }

  // função de redimensionamento — pode ser chamada várias vezes
  const apply = () => {
    const vw = document.querySelector('div[vw]');
    const wrapper = document.querySelector('div[vw-plugin-wrapper]');
    // pega o gameContainer via plugin (mais confiável que querySelector)
    const gc = (window.plugin && window.plugin.player && window.plugin.player.gameContainer) ||
               document.getElementById('gameContainer');
    const canvas = document.querySelector('canvas');

    if (vw) {
      vw.style.cssText = `position:fixed!important;left:0!important;top:0!important;`
        + `right:0!important;bottom:0!important;width:${w}px!important;`
        + `height:${h}px!important;max-width:100vw!important;max-height:100vh!important;`
        + `min-width:0!important;min-height:0!important;margin:0!important;`
        + `z-index:2147483647!important;transform:none!important;`;
    }
    if (wrapper) {
      wrapper.classList.add('active');
      wrapper.style.cssText = `display:flex!important;flex-direction:column!important;`
        + `position:fixed!important;left:0!important;top:0!important;`
        + `right:0!important;bottom:0!important;width:${w}px!important;`
        + `height:${h}px!important;max-width:100vw!important;max-height:100vh!important;`
        + `min-width:0!important;min-height:0!important;margin:0!important;`
        + `background:#fff!important;box-shadow:none!important;border-radius:0!important;`
        + `z-index:2147483647!important;transform:none!important;`;
    }
    // gameContainer é o DIV pai do canvas (criado pelo Unity Emscripten)
    if (gc) {
      gc.style.cssText = `position:relative!important;width:${w}px!important;`
        + `height:${h}px!important;max-width:100vw!important;max-height:100vh!important;`
        + `margin:0!important;padding:0!important;`;
    }
    // canvas do Unity WebGL — redimensiona atributos + estilo
    if (canvas) {
      canvas.style.cssText = `display:block!important;width:${w}px!important;`
        + `height:${h}px!important;position:absolute!important;left:0!important;`
        + `top:0!important;margin:0!important;padding:0!important;`;
      canvas.width = w;
      canvas.height = h;
    }
    // avisa o Unity Emscripten sobre o novo tamanho (se disponível)
    if (window.Module && typeof window.Module.setCanvasSize === 'function') {
      try { window.Module.setCanvasSize(w, h); } catch(e) {}
    }
  };

  // aplica 3x (CSS do widget pode reinjetar)
  apply();
  await new Promise((r) => setTimeout(r, 1000));
  apply();
  await new Promise((r) => setTimeout(r, 2000));
  apply();

  // espera 3s pro Unity se re-renderizar no novo tamanho
  await new Promise((r) => setTimeout(r, 3000));
  apply();

  // esconde header/footer/controles do widget (deixa só o canvas do Unity visível)
  // o widget tem div[vp-header] (com nome do avatar), div[vp-controls] (Pular, etc),
  // div[vp-info-screen] (mensagem "Clique em um texto...")
  // IMPORTANTE: NÃO esconder div[vp] (pai do canvas) nem div[vp-box] (container do canvas)
  const hideSelectors = [
    'div[vp-header]', 'div[vp-controls]', 'div[vp-info-screen]',
    'div[vp-settings]', 'div[vp-settings-btn]', 'div[vp-message-box]',
    'div[vp-dictionary]', 'div[vp-suggestion-screen]', 'div[vp-translator-screen]',
    'div[vp-more-options-screen]', 'div[vp-emotions-tooltip]',
    'div[vp-main-guide-screen]', 'div[vp-suggestion-button]', 'div[vp-rate-box]',
    'div[vp-change-avatar]', 'div[vp-aux-controls]', 'span[vp-click-blocker]',
  ];
  for (const sel of hideSelectors) {
    document.querySelectorAll(sel).forEach((el) => {
      el.style.cssText = 'display:none!important;visibility:hidden!important;'
        + 'opacity:0!important;height:0!important;width:0!important;'
        + 'position:absolute!important;left:-9999px!important;';
    });
  }

  // captura bbox do gameContainer (que agora deve ser fullscreen)
  const gc = (window.plugin && window.plugin.player && window.plugin.player.gameContainer) ||
             document.getElementById('gameContainer');
  const target = gc || document.querySelector('div[vw-plugin-wrapper]') || document.querySelector('div[vw]');
  let bbox = null;
  if (target) {
    const rect = target.getBoundingClientRect();
    bbox = {x: Math.max(0, rect.x), y: Math.max(0, rect.y),
            width: Math.min(w, rect.width), height: Math.min(h, rect.height)};
  }
  const finalCanvas = document.querySelector('canvas');
  return {
    bbox,
    canvas_size: finalCanvas ? {w: finalCanvas.width, h: finalCanvas.height,
                                cw: finalCanvas.clientWidth, ch: finalCanvas.clientHeight} : null,
    gc_rect: gc ? gc.getBoundingClientRect() : null,
    has_plugin: !!window.plugin,
    viewport: {w, h},
  };
}
"""


async def _render_widget_async(text: str, api_base: str, cache_dir: Path, fmt: str) -> Path:
    """Renderiza o player oficial do VLibras e captura frames."""
    from playwright.async_api import async_playwright

    # viewport maior pra acomodar o player fullscreen
    VW, VH = 1920, 1080
    player_url = f"{api_base}/signs/play?text={quote_plus(text)}"

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
            # chromium-headless-shell (mais leve) com flags de baixo uso de RAM
            browser = await p.chromium.launch(
                headless=True,
                channel="chromium-headless-shell",
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--use-gl=swiftshader",
                    "--enable-webgl",
                    "--ignore-gpu-blocklist",
                    "--disable-gpu-vsync",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-extensions",
                    "--disable-sync",
                    "--disable-translate",
                    "--no-first-run",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            try:
                context = await browser.new_context(
                    viewport={"width": VW, "height": VH},
                    device_scale_factor=1,
                )
                page = await context.new_page()
                logger.info("loading %s", player_url)
                await page.goto(player_url, wait_until="domcontentloaded", timeout=30000)

                # espera o widget VLibras inicializar (Unity WebGL é pesado)
                logger.info("waiting 25s for Unity WebGL init...")
                await page.wait_for_timeout(25000)

                # força fullscreen via page.evaluate (clica access button, espera iframe, redimensiona)
                logger.info("forcing widget fullscreen (clica access + espera iframe + resize)...")
                info = await page.evaluate(_FULLSCREEN_JS)
                logger.info("widget info: %s", info)

                # espera mais 8s pro Unity estabilizar depois do resize
                logger.info("waiting 8s for Unity to settle after resize...")
                await page.wait_for_timeout(8000)

                # decide o que capturar
                bbox = info.get("bbox") if info else None
                if bbox and bbox.get("width", 0) > 100 and bbox.get("height", 0) > 100:
                    clip = {
                        "x": max(0, bbox["x"]),
                        "y": max(0, bbox["y"]),
                        "width": min(VW, bbox["width"]),
                        "height": min(VH, bbox["height"]),
                    }
                    logger.info("capturing wrapper bbox: %s", clip)
                else:
                    clip = None
                    logger.warning("wrapper bbox inválido, capturando viewport inteiro")

                # captura frames do player durante a animação
                words = text.split()
                duration_s = max(5.0, min(25.0, len(words) * 2.0 + 3.0))
                fps = 8  # 8fps é suficiente pra movimento do avatar
                total_frames = int(duration_s * fps)
                interval_s = 1.0 / fps
                logger.info("capturing %d frames (%.1fs @ %dfps) clip=%s",
                            total_frames, duration_s, fps, clip)
                for i in range(total_frames):
                    frame_path = tmp / f"frame_{i:05d}.png"
                    if clip:
                        await page.screenshot(path=str(frame_path), clip=clip)
                    else:
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

        # checa se os frames não são todos iguais (widget não inicializou?)
        sizes = [p.stat().st_size for p in frame_paths]
        unique_sizes = set(sizes)
        if len(unique_sizes) < 3:
            logger.warning("frames muito similares (sizes únicos: %d) — widget pode não ter animado", len(unique_sizes))

        list_file = tmp / "list.txt"
        list_file.write_text(
            "\n".join(f"file '{p.resolve()}'\nduration 0.125\n" for p in frame_paths) + "\n"
        )

        if fmt == "mp4":
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-vsync", "vfr",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
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
    from urllib.parse import quote_plus
    return asyncio.run(_render_widget_async(text, api_base, cache_dir, fmt))
