"""Renderer headless: usa o widget OFICIAL do VLibras (avatar 3D real) + Playwright.

Pipeline:
1. Lança Chromium headless via Playwright
2. Carrega o nosso player (/signs/play?text=...) que embedda o widget oficial
   do VLibras (https://vlibras.gov.br/app/vlibras-plugin.js)
3. Espera o widget criar o access button (não pode estar display:none senão
   o Unity WebGL iframe não é criado)
4. Clica no access button (isso expande o player e cria o iframe do Unity)
5. Espera o `vw-plugin-wrapper.active` e o canvas do Unity WebGL aparecer
6. Via page.evaluate, força fullscreen no canvas/wrapper
7. Espera o Unity estabilizar (~5s) — durante esse tempo o widget JÁ
   começa a tocar a animação da frase
8. Detecta o FIM da animação (frames estáveis por 1.5s) e para de capturar
9. Concatena os frames em MP4 ou GIF com ffmpeg
10. Cacheia em disco por hash

AVISO: pesado (Chromium ~500MB em disco, ~300MB RAM por execução).
Cache em disco evita re-render se a mesma frase for pedida de novo.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
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
# IMPORTANTE: NÃO esconde o access button até o widget criar o iframe (senão
# o click não funciona e o Unity WebGL nunca inicializa).
_FULLSCREEN_JS = r"""
async () => {
  const w = window.innerWidth;
  const h = window.innerHeight;

  // clica no access button (avatar pequeno) pra abrir o player
  // IMPORTANTE: o botão NÃO pode estar display:none senão o widget ignora o click
  const btn = document.querySelector('[vw-access-button]');
  if (btn) {
    // remove qualquer style que esconda o botão
    btn.style.cssText = '';
    btn.classList.add('active');
    btn.click();
  }

  // espera o canvas do Unity WebGL aparecer (até 30s)
  let canvas = null;
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 500));
    canvas = document.querySelector('canvas');
    if (canvas && canvas.clientWidth > 100) break;
    if (i === 5 || i === 15 || i === 25) {
      const b = document.querySelector('[vw-access-button]');
      if (b) { b.style.cssText = ''; b.click(); }
    }
  }
  if (!canvas) {
    return {error: 'canvas não apareceu em 30s', has_canvas: false};
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
  // IMPORTANTE: NÃO esconder [vw-access-button] depois do click (já foi usado)
  const hideSelectors = [
    'div[vp-header]', 'div[vp-controls]', 'div[vp-info-screen]',
    'div[vp-settings]', 'div[vp-settings-btn]', 'div[vp-message-box]',
    'div[vp-dictionary]', 'div[vp-suggestion-screen]', 'div[vp-translator-screen]',
    'div[vp-more-options-screen]', 'div[vp-emotions-tooltip]',
    'div[vp-main-guide-screen]', 'div[vp-suggestion-button]', 'div[vp-rate-box]',
    'div[vp-change-avatar]', 'div[vp-aux-controls]', 'span[vp-click-blocker]',
    '[vw-access-button]',  // agora sim pode esconder
  ];
  for (const sel of hideSelectors) {
    document.querySelectorAll(sel).forEach((el) => {
      el.style.cssText = 'display:none!important;visibility:hidden!important;'
        + 'opacity:0!important;height:0!important;width:0!important;'
        + 'position:absolute!important;left:-9999px!important;';
    });
  }

  // injeta barra de legenda (caption) no rodapé — vai ser "queimada" nos screenshots
  // aceita updates de palavra via window.__libras2Caption(idx)
  const WORDS = (window.__LIBRAS2_WORDS__ || []).slice();
  const cap = document.createElement('div');
  cap.id = '__libras2-caption';
  cap.style.cssText = [
    'position:fixed!important',
    'left:0!important',
    'right:0!important',
    'bottom:0!important',
    'padding:32px 60px!important',
    'min-height:120px!important',
    'background:linear-gradient(to top,rgba(0,0,0,0.85) 0%,rgba(0,0,0,0.65) 70%,rgba(0,0,0,0) 100%)!important',
    'color:#fff!important',
    'font:600 56px/1.2 -apple-system,system-ui,"Segoe UI",sans-serif!important',
    'text-align:center!important',
    'letter-spacing:1px!important',
    'text-shadow:0 2px 8px rgba(0,0,0,0.6)!important',
    'z-index:2147483647!important',
    'pointer-events:none!important',
    'box-sizing:border-box!important',
    'display:flex!important',
    'align-items:center!important',
    'justify-content:center!important',
    'flex-wrap:wrap!important',
    'gap:18px!important',
  ].join(';');
  if (WORDS.length) {
    WORDS.forEach((w, i) => {
      const span = document.createElement('span');
      span.textContent = w.toUpperCase();
      span.dataset.idx = String(i);
      span.style.cssText = [
        'padding:4px 14px!important',
        'border-radius:8px!important',
        'background:rgba(255,255,255,0.08)!important',
        'transition:all 0.3s ease!important',
        'opacity:0.55!important',
      ].join(';');
      cap.appendChild(span);
    });
  } else {
    cap.textContent = '...';
  }
  document.body.appendChild(cap);

  // helper global: destaca a palavra N
  window.__libras2Caption = (idx) => {
    const spans = cap.querySelectorAll('span');
    spans.forEach((s, i) => {
      if (i === idx) {
        s.style.cssText = 'padding:6px 18px!important;border-radius:8px!important;'
          + 'background:#1f6feb!important;color:#fff!important;'
          + 'opacity:1!important;transform:scale(1.05);font-weight:700!important;'
          + 'box-shadow:0 0 20px rgba(31,111,235,0.6)!important;';
      } else {
        s.style.cssText = 'padding:4px 14px!important;border-radius:8px!important;'
          + 'background:rgba(255,255,255,0.08)!important;opacity:0.55!important;';
      }
    });
  };
  if (WORDS.length) window.__libras2Caption(0);

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


def _frame_diff_score(png1: bytes, png2: bytes) -> float:
    """Retorna 0.0-1.0 indicando quanto os dois PNGs diferem (1.0 = totalmente diferentes).
    Usa Pillow pra calcular diferença de pixels. Rápido o suficiente pra ~10 fps.
    """
    from PIL import Image, ImageChops
    try:
        im1 = Image.open(io.BytesIO(png1)).convert("RGB")
        im2 = Image.open(io.BytesIO(png2)).convert("RGB")
        if im1.size != im2.size:
            return 1.0  # tamanho diferente = mudou
        diff = ImageChops.difference(im1, im2)
        # diff.getbbox() retorna o bounding box da área diferente
        bbox = diff.getbbox()
        if bbox is None:
            return 0.0
        # calcula a "energia" da diferença (média dos pixels que mudaram)
        hist = diff.crop(bbox).histogram()
        # 3 canais RGB, 256 bins cada
        total = 0
        nonzero = 0
        for ch in range(3):
            for v in range(256):
                count = hist[ch * 256 + v]
                if v > 5:  # ignora mudanças mínimas (compressão)
                    nonzero += count
                    total += count * v
        if nonzero == 0:
            return 0.0
        avg = total / nonzero
        return min(1.0, avg / 128.0)
    except Exception as e:
        logger.warning("frame diff error: %s", e)
        return 1.0  # em caso de erro, assume que mudou


async def _render_widget_async(text: str, api_base: str, cache_dir: Path, fmt: str) -> Path:
    """Renderiza o player oficial do VLibras e captura frames."""
    from playwright.async_api import async_playwright

    # viewport: 1280x720 (HD) é o sweet spot — fullscreen pra usuário mas rápido em swiftshader
    # 1920x1080 demora ~2s por frame (10x mais lento), inviável pra 30s de animação
    VW, VH = 1280, 720
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
        _success = False
        async with async_playwright() as p:
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
                words = text.split()
                await context.add_init_script(
                    f"window.__LIBRAS2_WORDS__ = {json.dumps(words)};"
                )
                page = await context.new_page()
                logger.info("loading %s", player_url)
                await page.goto(player_url, wait_until="domcontentloaded", timeout=30000)

                # espera o widget VLibras inicializar (criar access button)
                logger.info("waiting 12s for widget to create access button...")
                await page.wait_for_timeout(12000)

                # força fullscreen via page.evaluate (clica access button + redimensiona)
                logger.info("forcing widget fullscreen (clica access + espera iframe + resize)...")
                info = await page.evaluate(_FULLSCREEN_JS)
                logger.info("widget info: %s", info)
                if not info or not info.get("has_plugin"):
                    logger.warning("widget plugin não inicializou — sem Unity, vai ficar em standby")

                # espera mais 3s pro widget começar a animação (e Unity estabilizar)
                logger.info("waiting 3s for animation to start...")
                await page.wait_for_timeout(3000)

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

                # === CAPTURA via canvas.toDataURL (rápido para WebGL) ===
                # page.screenshot() é lento com swiftshader porque faz round-trip CDP
                # e re-rasteriza via swiftshader. Em vez disso, pegamos o frame DIRETO
                # do canvas via canvas.toDataURL — já está renderizado no GPU, só precisa
                # codificar em PNG. ~5-10x mais rápido.
                fps = 8
                interval_s = 1.0 / fps
                n_words = max(1, len(words))
                # VLibras toca cada sinal em ~1.5-2s. Distribui o tempo total
                # entre as palavras proporcionalmente, com 1s de intro e 2s de respiro.
                intro_s = 1.0
                tail_s = 2.0
                total_target_s = 1.5 * n_words + intro_s + tail_s
                per_word_s = max(1.0, 1.5)  # 1.5s por palavra (tempo real de sinal)
                max_total_s = min(30.0, total_target_s)
                standby_threshold = int(2.0 * fps)  # 2s parado = acabou
                capture_duration = int(max_total_s * fps)

                logger.info("capturing %d frames @ %dfps (max %.1fs, per_word=%.1fs)",
                            capture_duration, fps, max_total_s, per_word_s)

                last_word = -2
                frames_captured = 0
                stable_count = 0
                last_hash = None
                last_size = None
                animation_done = False
                standby_trail_s = 1.5

                for i in range(capture_duration + int(standby_trail_s * fps) + 10):
                    t_s = i * interval_s
                    widx = word_at_safe(t_s, intro_s, per_word_s, n_words)
                    if widx != last_word:
                        try:
                            await page.evaluate(f"window.__libras2Caption && window.__libras2Caption({widx})")
                        except Exception:
                            pass
                        last_word = widx

                    # captura via canvas.toDataURL (rápido!)
                    # IMPORTANTE: WebGL por padrão tem preserveDrawingBuffer:false,
                    # então precisamos forçar re-render via requestAnimationFrame antes
                    # de copiar. O Unity renderiza o frame em RAF, então esperamos 2 RAFs.
                    try:
                        data_url = await page.evaluate("""async () => {
                            const c = document.querySelector('canvas');
                            if (!c) return null;
                            // força o Unity a re-renderizar (2 RAFs)
                            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                            try {
                                return c.toDataURL('image/jpeg', 0.85);
                            } catch(e) {
                                return c.toDataURL('image/png');
                            }
                        }""")
                    except Exception as e:
                        logger.warning("toDataURL failed: %s", e)
                        data_url = None

                    if data_url and data_url.startswith("data:image/jpeg;base64,"):
                        import base64
                        b64 = data_url.split(",", 1)[1]
                        png_bytes = base64.b64decode(b64)
                        frame_path = tmp / f"frame_{frames_captured:05d}.jpg"
                        frame_path.write_bytes(png_bytes)
                        frames_captured += 1

                        # detecta fim da animação via hash rápido
                        import hashlib
                        sample = png_bytes[:4096]
                        cur_hash = hashlib.md5(sample).hexdigest()
                        cur_size = len(png_bytes)
                        if last_hash is not None:
                            same = (cur_hash == last_hash) and abs(cur_size - last_size) < 500
                            if same:
                                stable_count += 1
                                if stable_count >= standby_threshold and not animation_done:
                                    logger.info("animation ended at t=%.1fs (frame %d, stable for %.1fs)",
                                                t_s, i, stable_count * interval_s)
                                    animation_done = True
                            else:
                                stable_count = 0
                        last_hash = cur_hash
                        last_size = cur_size

                    if i % fps == 0:
                        logger.info("frame %d t=%.1fs word=%d captured=%d", i, t_s, widx, frames_captured)

                    if animation_done and stable_count >= int(standby_trail_s * fps):
                        logger.info("stopping capture after animation end (total %.1fs, %d frames)",
                                    t_s, frames_captured)
                        break

                    if t_s >= max_total_s and not animation_done:
                        logger.info("max_total_s reached without detecting end (%d frames)", frames_captured)
                        break

                    await page.wait_for_timeout(int(interval_s * 1000))

                await context.close()
            finally:
                await browser.close()

        # concatena em MP4 ou GIF
        frame_paths = sorted(tmp.glob("frame_*.jpg"))
        if not frame_paths:
            raise RuntimeError("nenhum frame capturado")

        # === ADICIONA LEGENDA (caption) em cada frame via Pillow ===
        # Como usamos canvas.toDataURL, a legenda HTML não vem nos frames.
        # Desenhamos ela por cima com Pillow antes do ffmpeg.
        logger.info("adicionando legenda em %d frames...", len(frame_paths))
        from PIL import Image, ImageDraw, ImageFont
        try:
            # tenta achar uma fonte bold
            font = None
            for fp in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            ]:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, 64)
                    break
            if font is None:
                font = ImageFont.load_default()
        except Exception as e:
            logger.warning("não carregou fonte: %s, usando default", e)
            font = ImageFont.load_default()

        # descobre dimensões do primeiro frame
        first = Image.open(frame_paths[0])
        fw, fh = first.size

        caption_h = 140  # altura da barra de legenda
        caption_y0 = fh - caption_h

        def add_caption_to_frame(frame_path: Path, widx: int):
            img = Image.open(frame_path).convert("RGB")
            draw = ImageDraw.Draw(img)
            # gradiente preto no rodapé (overlay)
            overlay = Image.new("RGBA", (fw, caption_h), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            for y in range(caption_h):
                alpha = int(220 * (1 - y / caption_h) * 0.85)
                od.line([(0, y), (fw, y)], fill=(0, 0, 0, alpha))
            img.paste(overlay, (0, caption_y0), overlay)

            # desenha cada palavra
            x = 30
            y_text = caption_y0 + (caption_h - 70) // 2
            for i, w in enumerate(words):
                active = (i == widx)
                txt = w.upper()
                # bbox do texto
                try:
                    tb = draw.textbbox((0, 0), txt, font=font)
                    tw = tb[2] - tb[0]
                    th = tb[3] - tb[1]
                except Exception:
                    tw, th = draw.textsize(txt, font=font)
                pad_x, pad_y = 18, 8
                box_w = tw + pad_x * 2
                box_h = th + pad_y * 2
                if x + box_w > fw - 30:
                    # quebra linha (não cabe)
                    x = 30
                    y_text += box_h + 12
                if active:
                    # fundo azul forte
                    draw.rounded_rectangle(
                        [x, y_text, x + box_w, y_text + box_h],
                        radius=10, fill=(31, 111, 235, 255)
                    )
                    draw.text((x + pad_x, y_text + pad_y - 4), txt, font=font, fill=(255, 255, 255, 255))
                else:
                    # fundo cinza escuro translúcido
                    draw.rounded_rectangle(
                        [x, y_text, x + box_w, y_text + box_h],
                        radius=10, fill=(40, 40, 40, 180)
                    )
                    draw.text((x + pad_x, y_text + pad_y - 4), txt, font=font, fill=(200, 200, 200, 255))
                x += box_w + 18
            img.save(frame_path, quality=85)

        # aplica legenda (palavras destacadas pelo tempo)
        for i, fp in enumerate(frame_paths):
            t_s = i / fps
            widx = word_at_safe(t_s, intro_s, per_word_s, n_words)
            try:
                add_caption_to_frame(fp, widx)
            except Exception as e:
                logger.warning("caption failed for frame %d: %s", i, e)

        sizes = [p.stat().st_size for p in frame_paths]
        unique_sizes = set(sizes)
        if len(unique_sizes) < 3:
            logger.warning("frames muito similares (sizes únicos: %d) — widget pode não ter animado", len(unique_sizes))

        list_file = tmp / "list.txt"
        list_file.write_text(
            "\n".join(f"file '{p.resolve()}'\nduration {1.0/fps}\n" for p in frame_paths) + "\n"
        )

        if fmt == "mp4":
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-fps_mode", "vfr",  # novo nome (era -vsync)
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast",
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

        _success = True
        return out_path
    except Exception:
        # NÃO deleta o tmp em caso de erro — deixa pra debug
        logger.exception("render failed, tmp preserved at: %s", tmp)
        raise
    finally:
        # só deleta se sucesso
        if _success:
            try:
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass


def word_at_safe(t_s: float, intro_s: float, per_word_s: float, n_words: int) -> int:
    """Retorna o índice da palavra destacada no tempo t_s."""
    if t_s < intro_s:
        return -1
    idx = int((t_s - intro_s) / per_word_s)
    return min(idx, n_words - 1)


def render_widget(text: str, api_base: str, cache_dir: Path, fmt: str = "mp4") -> Path:
    """Wrapper síncrono do renderer com Playwright."""
    from urllib.parse import quote_plus
    return asyncio.run(_render_widget_async(text, api_base, cache_dir, fmt))
