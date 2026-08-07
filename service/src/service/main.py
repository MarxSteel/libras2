"""FastAPI app — entrypoint do serviço libras2.

Rotas:
  GET  /health
  POST /glosa       usa a API oficial do VLibras pra PT → glosa (uppercase Libras)
  POST /translate   combina gloss + dataset local de vídeos → MP4/GIF/gloss-file
  POST /translate.json  variante que sempre devolve JSON (compat com schema antigo)
  GET  /signs/{word}
  GET  /vocab
  GET  /videos/{filename}     # serve o MP4/GIF gerado

Query params do /translate (alem do body):
  ?output=gloss  → retorna arquivo de glosa (sempre funciona, mesmo sem dataset)
  ?output=video  → retorna MP4
  ?output=gif    → retorna GIF
  ?output=auto   (default) → MP4 se tem gloss+mídia, senão arquivo de glosa
  ?download=true → força Content-Disposition: attachment
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
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


# ---- Helpers ----------------------------------------------------------------

def _resolve_gloss(req: TranslateRequest, t: Translator) -> dict:
    """Pipeline comum: pega tokens, escolhe backend, devolve dict com:
      - official_gloss: gloss da API oficial (lowercase, na ordem Libras)
      - rendered_gloss: subset que tem vídeo no dataset
      - missing: subset sem vídeo
      - backend, note
    """
    tokens = normalize_pt(req.text)
    if not tokens:
        raise HTTPException(400, "empty text after normalization")

    backend_used = req.backend
    note: str | None = None
    official_gloss: list[str] = []
    rendered_gloss: list[str] = []
    missing: list[str] = []

    if req.backend == "local":
        rendered_gloss, missing = t.to_gloss(tokens)
        official_gloss = list(rendered_gloss)
    elif req.backend == "vlibras":
        try:
            raw = get_backend().translate(req.text)
        except Exception as e:
            raise HTTPException(503, f"vlibras backend unavailable: {e}")
        official_gloss = [g.lower() for g in raw]
        rendered_gloss, missing = [], []
        for w in official_gloss:
            (rendered_gloss if w in t.index else missing).append(w)
    else:  # auto
        local_present, local_missing = t.to_gloss(tokens)
        if local_present:
            official_gloss = list(local_present)
            rendered_gloss, missing = local_present, local_missing
        else:
            try:
                raw = get_backend().translate(req.text)
            except Exception as e:
                logger.warning("vlibras fallback failed: %s", e)
                raw = []
            if raw:
                backend_used = "vlibras"
                note = "local gloss empty, used vlibras backend"
                official_gloss = [g.lower() for g in raw]
                rendered_gloss, missing = [], []
                for w in official_gloss:
                    (rendered_gloss if w in t.index else missing).append(w)
            else:
                backend_used = "local"
                note = "no gloss from any backend"

    return {
        "official_gloss": official_gloss,
        "rendered_gloss": rendered_gloss,
        "missing": missing,
        "backend": backend_used,
        "note": note,
    }


def _gloss_file_payload(text: str, data: dict) -> dict:
    """Payload do arquivo de glosa (preserva gloss oficial + info de render)."""
    return {
        "text": text,
        "gloss": data["official_gloss"],
        "rendered_gloss": data["rendered_gloss"],
        "missing": data["missing"],
        "backend": data["backend"],
        "note": data["note"],
        "format_version": "libras2-glosa-1",
    }


def _safe_name(s: str) -> str:
    """Sanitiza string pra virar filename."""
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    out = "".join(c if c in keep else "_" for c in s.strip())[:40]
    return out or "libras2"


def _gloss_response(payload: dict, original: str, download: bool) -> Response:
    """Retorna o gloss como JSON pra download (application/json)."""
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    fname = f"{_safe_name(original)}.glosa.json"
    headers = {
        "X-Libras2-Gloss": " ".join(payload["gloss"]),
        "X-Libras2-Missing": ",".join(payload["missing"]),
        "X-Libras2-Backend": payload["backend"],
    }
    if payload.get("note"):
        headers["X-Libras2-Note"] = payload["note"]
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return Response(content=body, media_type="application/json", headers=headers)


def _media_response(
    path: Path, original: str, download: bool,
    missing: list[str], rendered: list[str], backend: str, note: str | None,
) -> FileResponse:
    """Retorna MP4/GIF como arquivo (inline ou attachment)."""
    media = "image/gif" if path.suffix == ".gif" else "video/mp4"
    fname = f"{_safe_name(original)}{path.suffix}"
    headers = {
        "X-Libras2-Rendered-Gloss": " ".join(rendered),
        "X-Libras2-Missing": ",".join(missing),
        "X-Libras2-Backend": backend,
    }
    if note:
        headers["X-Libras2-Note"] = note
    disp = "attachment" if download else "inline"
    headers["Content-Disposition"] = f'{disp}; filename="{fname}"'
    return FileResponse(path, media_type=media, headers=headers, filename=fname)


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


@app.post("/translate")
def translate(
    req: TranslateRequest,
    output: Literal["auto", "gloss", "video", "gif"] = Query("auto"),
    download: bool = Query(False),
):
    """Pipeline completo: gloss + (concat de vídeos) → MP4/GIF/arquivo-de-glosa.

    Por padrão (output=auto) devolve MP4 se o gloss mapeia pra vídeos no dataset,
    senão cai pro arquivo de glosa (.json). Use output=gloss pra forçar arquivo de
    glosa mesmo se houver vídeo. Use output=video/gif pra forçar formato.
    """
    t = get_translator()
    data = _resolve_gloss(req, t)
    official = data["official_gloss"]
    rendered = data["rendered_gloss"]
    missing = data["missing"]
    backend = data["backend"]
    note = data["note"]

    if not official:
        # Sem tradução possível em nenhum backend
        if output == "gloss":
            return _gloss_response(_gloss_file_payload(req.text, data), req.text, download)
        raise HTTPException(
            422,
            f"no gloss from any backend (input: {req.text!r})",
        )

    # Tenta gerar mídia usando só rendered_gloss
    out_path = None
    if rendered:
        try:
            out_path = render(
                tokens=rendered,
                data_dir=DATA_DIR,
                cache_dir=CACHE_DIR,
                fmt=req.format,
            )
        except FileNotFoundError:
            out_path = None  # sem vídeos pra esse gloss

    # Decide o que devolver
    if output == "gloss":
        return _gloss_response(_gloss_file_payload(req.text, data), req.text, download)

    if output == "video":
        if not out_path or out_path.suffix != ".mp4":
            raise HTTPException(422, "no MP4 available (missing videos in dataset)")
        return _media_response(out_path, req.text, download, missing, rendered, backend, note)

    if output == "gif":
        if rendered:
            try:
                gif_path = render(
                    tokens=rendered, data_dir=DATA_DIR, cache_dir=CACHE_DIR, fmt="gif"
                )
            except FileNotFoundError as e:
                raise HTTPException(422, f"no GIF available: {e}")
        else:
            raise HTTPException(422, "no rendered_gloss (all words missing)")
        return _media_response(gif_path, req.text, download, missing, rendered, backend, note)

    # output == "auto"
    if out_path:
        return _media_response(out_path, req.text, download, missing, rendered, backend, note)
    # cai pro gloss-file (sem vídeo mas tem gloss)
    return _gloss_response(_gloss_file_payload(req.text, data), req.text, download)


@app.post("/translate.json", response_model=TranslateResponse)
def translate_json(req: TranslateRequest):
    """Variante que sempre devolve JSON (compat com clientes antigos)."""
    t = get_translator()
    data = _resolve_gloss(req, t)
    if not data["official_gloss"]:
        raise HTTPException(422, "no gloss from any backend")
    out_path = None
    if data["rendered_gloss"]:
        try:
            out_path = render(
                tokens=data["rendered_gloss"],
                data_dir=DATA_DIR,
                cache_dir=CACHE_DIR,
                fmt=req.format,
            )
        except FileNotFoundError as e:
            raise HTTPException(422, str(e))
    return TranslateResponse(
        text=req.text,
        gloss=data["official_gloss"],
        missing=data["missing"],
        video_url=f"/videos/{out_path.name}" if out_path else "",
        format=req.format,
        backend=data["backend"],
        note=data["note"],
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
