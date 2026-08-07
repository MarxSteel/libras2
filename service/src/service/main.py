"""FastAPI app — entrypoint do serviço libras2.

Rotas:
  GET  /health
  POST /glosa       usa a API oficial do VLibras pra PT → glosa (uppercase Libras)
  POST /translate   combina gloss + dataset local de vídeos → MP4/GIF
  GET  /signs/{word}
  GET  /vocab
  GET  /videos/{filename}     # serve o MP4/GIF gerado

Backends de tradução:
  - "local": só dataset local (V-LIBRASIL quando baixado)
  - "vlibras": chama a API oficial https://traducao2.vlibras.gov.br/translate
               pra gloss, depois tenta mapear pros vídeos locais
  - "auto": tenta local primeiro; se gloss vazio, cai pro vlibras
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from service.gloss import normalize_pt
from service.translator import Translator
from service.renderer import render
from service.vlibras_backend import VLibrasBackend, get_backend

logger = logging.getLogger("libras2")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DATA_DIR = Path(os.getenv("LIBRAS2_DATA_DIR", "/opt/libras2/data/vlibrasil"))
CACHE_DIR = Path(os.getenv("LIBRAS2_CACHE_DIR", "/opt/libras2/data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="libras2", version="0.1.0", docs_url="/docs")

# Singletons
_translator: Translator | None = None


def get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator(data_dir=DATA_DIR)
    return _translator


# ---- Schemas ----------------------------------------------------------------

class GlosaRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class GlosaResponse(BaseModel):
    text: str
    gloss: list[str]
    backend: str


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    format: str = Field("mp4", pattern="^(mp4|gif)$")
    backend: Literal["local", "vlibras", "auto"] = Field("auto")


class TranslateResponse(BaseModel):
    text: str
    gloss: list[str]
    missing: list[str]
    video_url: str
    format: str
    backend: str
    note: str | None = None


# ---- Rotas ------------------------------------------------------------------

@app.get("/health")
def health():
    """Liveness + readiness rápido."""
    t = get_translator()
    return {
        "status": "ok",
        "vocab_size": t.vocab_size,
        "data_dir": str(DATA_DIR),
        "cache_dir": str(CACHE_DIR),
        "backends": {"local": True, "vlibras": True},
    }


@app.get("/vocab")
def vocab():
    """Lista palavras do dataset local."""
    t = get_translator()
    return {"words": sorted(t.index.keys()), "size": t.vocab_size}


@app.post("/glosa", response_model=GlosaResponse)
def glosa(req: GlosaRequest):
    """Traduz PT → glosa usando a API oficial do VLibras.

    Não precisa de dataset local. Útil pra integrar Libras em outros sistemas
    sem ainda ter o dataset de vídeos.
    """
    try:
        gloss = get_backend().translate(req.text)
    except Exception as e:
        raise HTTPException(503, f"vlibras backend unavailable: {e}")

    return GlosaResponse(text=req.text, gloss=gloss, backend="vlibras")


@app.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    """Pipeline completo: gloss + (concat de vídeos) → MP4/GIF.

    Backend:
      - "local": gloss derivado dos tokens normalizados do input
      - "vlibras": gloss vem da API oficial
      - "auto": local primeiro, fallback vlibras se gloss vazio
    """
    tokens = normalize_pt(req.text)
    if not tokens:
        raise HTTPException(400, "empty text after normalization")

    t = get_translator()
    backend_used = req.backend
    note: str | None = None
    gloss: list[str]
    missing: list[str]

    if req.backend == "local":
        gloss, missing = t.to_gloss(tokens)
    elif req.backend == "vlibras":
        try:
            official = get_backend().translate(req.text)
        except Exception as e:
            raise HTTPException(503, f"vlibras backend unavailable: {e}")
        gloss = []
        missing = []
        for g in official:
            g_low = g.lower()
            if g_low in t.index:
                gloss.append(g_low)
            else:
                missing.append(g_low)
    else:  # auto
        gloss, missing = t.to_gloss(tokens)
        if not gloss:
            try:
                official = get_backend().translate(req.text)
            except Exception as e:
                logger.warning("vlibras fallback failed: %s", e)
                official = []
            if official:
                backend_used = "vlibras"
                note = "local gloss empty, used vlibras backend"
                gloss = []
                missing = []
                for g in official:
                    g_low = g.lower()
                    if g_low in t.index:
                        gloss.append(g_low)
                    else:
                        missing.append(g_low)
            else:
                backend_used = "local"
                note = "no gloss from any backend"

    if not gloss:
        raise HTTPException(
            422,
            f"none of the words are in the vocabulary (missing={missing})",
        )

    try:
        out_path = render(
            tokens=gloss,
            data_dir=DATA_DIR,
            cache_dir=CACHE_DIR,
            fmt=req.format,
        )
    except FileNotFoundError as e:
        raise HTTPException(422, f"no videos found: {e}")

    return TranslateResponse(
        text=req.text,
        gloss=gloss,
        missing=missing,
        video_url=f"/videos/{out_path.name}",
        format=req.format,
        backend=backend_used,
        note=note,
    )


@app.get("/signs/{word}")
def get_sign(word: str):
    """Debug: retorna o vídeo isolado de uma palavra (dataset local)."""
    word = word.lower()
    t = get_translator()
    path = t.lookup_video(word)
    if not path:
        raise HTTPException(404, f"sign for {word!r} not in vocabulary")
    return FileResponse(path, media_type="video/mp4")


@app.get("/videos/{filename}")
def get_video(filename: str):
    """Serve o MP4/GIF do cache. Path-traversal safe."""
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    path = CACHE_DIR / filename
    if not path.exists():
        raise HTTPException(404, "not found")
    media = "image/gif" if filename.endswith(".gif") else "video/mp4"
    return FileResponse(path, media_type=media)
