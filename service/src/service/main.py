"""FastAPI app — entrypoint do serviço libras2.

Rotas:
  GET  /health
  POST /translate  body: {"text": "...", "format": "mp4"|"gif"}
  GET  /signs/{word}
  GET  /videos/{filename}     # serve o MP4/GIF gerado
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from service.gloss import normalize_pt
from service.translator import Translator
from service.renderer import render

logger = logging.getLogger("libras2")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DATA_DIR = Path(os.getenv("LIBRAS2_DATA_DIR", "/opt/libras2/data/vlibrasil"))
CACHE_DIR = Path(os.getenv("LIBRAS2_CACHE_DIR", "/opt/libras2/data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="libras2", version="0.1.0", docs_url="/docs")

# Singleton — instancia uma vez, reusa por request
_translator: Translator | None = None


def get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator(data_dir=DATA_DIR)
    return _translator


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    format: str = Field("mp4", pattern="^(mp4|gif)$")


class TranslateResponse(BaseModel):
    text: str
    gloss: list[str]
    missing: list[str]            # palavras sem vídeo no dicionário
    video_url: str
    format: str
    duration_ms: int


@app.get("/health")
def health():
    """Liveness + readiness rápido."""
    t = get_translator()
    return {
        "status": "ok",
        "vocab_size": t.vocab_size,
        "data_dir": str(DATA_DIR),
        "cache_dir": str(CACHE_DIR),
    }


@app.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    tokens = normalize_pt(req.text)
    if not tokens:
        raise HTTPException(400, "empty text after normalization")

    t = get_translator()
    gloss, missing = t.to_gloss(tokens)
    if not gloss:
        raise HTTPException(
            422,
            f"none of the words are in the vocabulary (missing={missing})",
        )

    out_path = render(
        tokens=gloss,
        data_dir=DATA_DIR,
        cache_dir=CACHE_DIR,
        fmt=req.format,
    )
    return TranslateResponse(
        text=req.text,
        gloss=gloss,
        missing=missing,
        video_url=f"/videos/{out_path.name}",
        format=req.format,
        duration_ms=int(out_path.stat().st_mtime * 1000) - int(out_path.stat().st_mtime * 1000),
    )


@app.get("/signs/{word}")
def get_sign(word: str):
    """Debug: retorna o vídeo isolado de uma palavra."""
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
