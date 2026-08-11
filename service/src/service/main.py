"""FastAPI app — entrypoint do serviço libras2.

Rotas:
  GET  /health
  POST /glosa       usa a API oficial do VLibras pra PT → glosa (uppercase Libras)
  POST /translate   combina gloss + dataset local de vídeos → MP4/GIF/gloss-file
  POST /translate.json  variante que sempre devolve JSON (compat com schema antigo)
  GET  /signs/{word}/glb  serve o .glb (animação 3D) do dicionário oficial, com cache
  GET  /signs/{word}/info metadata do sinal (existe? formato? tamanho?)
  GET  /signs/play?gloss=BOM,DIA   player HTML com three.js que renderiza sequência
  GET  /signs/play?text=bom+dia   idem, mas faz /glosa primeiro
  GET  /vocab
  GET  /videos/{filename}     # serve o MP4/GIF gerado (legacy, sem dataset agora)

Query params do /translate:
  ?output=gloss  → arquivo .glosa.json (sempre funciona)
  ?output=video  → redireciona pro /signs/play com o gloss
  ?output=gif    → idem video
  ?output=auto   (default) → video se dicionário OK, senão gloss
  ?download=true → attachment
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from service.gloss import normalize_pt
from service.translator import Translator
from service.renderer import render as render_video  # legacy concat MP4 (sem dataset por enquanto)
from service.renderer_text import render as render_text_video  # MP4/GIF a partir de gloss (fallback)
from service.renderer_widget import render_widget  # MP4/GIF com avatar 3D OFICIAL do VLibras (puppeteer)
from service.vlibras_backend import VLibrasBackend, get_backend
from service.dictionary import Dictionary, get_dictionary

# MCP server: expõe rotas do Libras2 como tools pro Picoclaw (e qualquer cliente MCP-aware)
try:
    from fastapi_mcp import FastApiMCP
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

logger = logging.getLogger("libras2")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DATA_DIR = Path(os.getenv("LIBRAS2_DATA_DIR", "/opt/libras2/data/vlibrasil"))
CACHE_DIR = Path(os.getenv("LIBRAS2_CACHE_DIR", "/opt/libras2/data/cache"))
STATIC_DIR = Path(os.getenv("LIBRAS2_STATIC_DIR", "/opt/libras2/clients"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="libras2", version="0.2.0", docs_url="/docs")

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
      - rendered_gloss: subset que tem sinal no dataset OU no dicionário
      - missing: subset sem sinal
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

    # se tem dicionário online, considera ele como fonte de "tem sinal"
    dict_lookup = get_dictionary()
    def in_dataset_or_dict(w: str) -> bool:
        if w in t.index:
            return True
        return dict_lookup.has_sign(w)

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
            (rendered_gloss if in_dataset_or_dict(w) else missing).append(w)
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
                    (rendered_gloss if in_dataset_or_dict(w) else missing).append(w)
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
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    out = "".join(c if c in keep else "_" for c in s.strip())[:40]
    return out or "libras2"


def _gloss_response(payload: dict, original: str, download: bool) -> Response:
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


def _player_url(req: TranslateRequest, data: dict) -> str:
    """Monta a URL do player pra /translate?output=video."""
    gloss_q = ",".join(data["rendered_gloss"] or data["official_gloss"])
    return f"/signs/play?gloss={quote(gloss_q)}&from=text&text={quote(req.text)}"


# ---- Rotas ------------------------------------------------------------------

@app.get("/health")
def health():
    t = get_translator()
    return {
        "status": "ok",
        "vocab_size": t.vocab_size,
        "data_dir": str(DATA_DIR),
        "cache_dir": str(CACHE_DIR),
        "backends": {"local": True, "vlibras": True, "dictionary": True},
        "dictionary": {
            "version": get_dictionary().version,
            "platform": get_dictionary().platform,
        },
    }


@app.get("/vocab")
def vocab():
    t = get_translator()
    return {"words": sorted(t.index.keys()), "size": t.vocab_size}


@app.post("/glosa", response_model=GlosaResponse, operation_id="glosa")
def glosa(req: GlosaRequest):
    try:
        gloss = get_backend().translate(req.text)
    except Exception as e:
        raise HTTPException(503, f"vlibras backend unavailable: {e}")
    return GlosaResponse(text=req.text, gloss=gloss, backend="vlibras")


@app.post("/translate", operation_id="translate")
def translate(
    req: TranslateRequest,
    output: Literal["auto", "gloss", "video", "gif"] = Query("auto"),
    download: bool = Query(False),
):
    t = get_translator()
    data = _resolve_gloss(req, t)
    official = data["official_gloss"]
    rendered = data["rendered_gloss"]
    missing = data["missing"]
    backend = data["backend"]
    note = data["note"]

    if not official:
        if output == "gloss":
            return _gloss_response(_gloss_file_payload(req.text, data), req.text, download)
        raise HTTPException(422, f"no gloss from any backend (input: {req.text!r})")

    # output=video|gif → tenta primeiro o widget oficial (avatar 3D real),
    # cai pro renderer de texto se falhar
    if output in ("video", "gif"):
        if not official:
            raise HTTPException(422, "no gloss to render")
        api_base = os.getenv("LIBRAS2_PUBLIC_URL", f"http://127.0.0.1:8088")
        # 1ª tentativa: widget oficial (com PERSONAGEM 3D real do VLibras)
        try:
            out_path = render_widget(
                text=req.text,
                api_base=api_base,
                cache_dir=CACHE_DIR,
                fmt=req.format if output == "video" else "gif",
            )
            return _media_response(
                out_path, req.text, download,
                data["missing"], data["rendered_gloss"] or data["official_gloss"],
                backend, note + "; widget-player" if note else "vlibras-widget",
            )
        except Exception as e:
            logger.warning("widget render failed, falling back to text: %s", e)
        # 2ª tentativa: renderer de texto (fallback)
        try:
            out_path = render_text_video(
                text=req.text,
                gloss=official,
                cache_dir=CACHE_DIR,
                fmt=req.format if output == "video" else "gif",
            )
            return _media_response(
                out_path, req.text, download,
                data["missing"], data["rendered_gloss"] or data["official_gloss"],
                backend, note + "; text-fallback" if note else "text-fallback",
            )
        except Exception as e:
            logger.exception("text render also failed")
            raise HTTPException(500, f"renderer error: {e}")

    if output == "gloss":
        return _gloss_response(_gloss_file_payload(req.text, data), req.text, download)

    # output == "auto"
    if official:
        # se tem gloss, gera MP4 visual
        try:
            out_path = render_text_video(
                text=req.text, gloss=official, cache_dir=CACHE_DIR, fmt="mp4",
            )
            return _media_response(
                out_path, req.text, download,
                data["missing"], data["rendered_gloss"] or data["official_gloss"],
                backend, note,
            )
        except Exception as e:
            logger.warning("auto render failed, falling back to gloss file: %s", e)
    return _gloss_response(_gloss_file_payload(req.text, data), req.text, download)


@app.post("/translate.json", response_model=TranslateResponse)
def translate_json(req: TranslateRequest):
    t = get_translator()
    data = _resolve_gloss(req, t)
    if not data["official_gloss"]:
        raise HTTPException(422, "no gloss from any backend")
    return TranslateResponse(
        text=req.text,
        gloss=data["official_gloss"],
        missing=data["missing"],
        video_url=_player_url(req, data) if (data["rendered_gloss"] or data["official_gloss"]) else "",
        format=req.format,
        backend=data["backend"],
        note=data["note"],
    )


@app.post("/translate/file", operation_id="translate_file")
def translate_file(req: TranslateRequest):
    """Gera MP4 e retorna JSON com a URL pública do arquivo (não o binário).

    Pensado pra agentes/MCP tools que não conseguem decodificar MP4 binário
    de dentro de uma tool call. O cliente (ou picoclaw) baixa o MP4 via URL
    pública e envia pelo canal.
    """
    t = get_translator()
    data = _resolve_gloss(req, t)
    if not data["official_gloss"]:
        raise HTTPException(422, "no gloss from any backend")

    api_base = os.getenv("LIBRAS2_PUBLIC_URL", f"http://127.0.0.1:8088")
    try:
        out_path = render_widget(
            text=req.text,
            api_base=api_base,
            cache_dir=CACHE_DIR,
            fmt=req.format,
        )
    except Exception as e:
        logger.warning("widget render failed, falling back to text: %s", e)
        out_path = render_text_video(
            text=req.text,
            gloss=data["official_gloss"],
            cache_dir=CACHE_DIR,
            fmt=req.format,
        )

    public_url = f"{api_base}/videos/{out_path.name}"
    return {
        "text": req.text,
        "gloss": data["official_gloss"],
        "missing": data["missing"],
        "video_url": public_url,
        "video_filename": out_path.name,
        "video_size_bytes": out_path.stat().st_size,
        "format": req.format,
        "backend": data["backend"],
        "note": data["note"],
    }


@app.get("/signs/{word}/glb")
def get_sign_glb(word: str):
    """Serve o .glb (animação 3D) do sinal, do cache ou baixando do dicionário."""
    try:
        data = get_dictionary().get_glb(word)
    except KeyError:
        raise HTTPException(404, f"sign not found: {word!r}")
    except Exception as e:
        raise HTTPException(503, f"dictionary error: {e}")
    return Response(
        content=data,
        media_type="model/gltf-binary",
        headers={
            "Content-Disposition": f'inline; filename="{quote(word)}.glb"',
            "X-Libras2-Dictionary": f"{get_dictionary().version}/{get_dictionary().platform}",
        },
    )


@app.get("/signs/{word}/info", operation_id="get_sign_info")
def get_sign_info(word: str):
    """Metadata do sinal: existe? tamanho? formato?"""
    d = get_dictionary()
    exists = d.has_sign(word)
    size = None
    if exists:
        try:
            data = d.get_glb(word)
            size = len(data)
        except Exception:
            pass
    return {
        "word": word,
        "exists": exists,
        "size_bytes": size,
        "dictionary": {
            "version": d.version,
            "platform": d.platform,
            "base": d.base,
        },
    }


@app.get("/signs/play")
def play(gloss: str | None = Query(None), text: str | None = Query(None)):
    """Player HTML que embedda o widget OFICIAL do VLibras (avatar 3D).

    URL: /signs/play?text=obrigado+pela+forca
    O widget oficial do gov.br renderiza o personagem 3D (avatar Ícaro).
    """
    if not gloss and not text:
        raise HTTPException(400, "passe ?gloss=BOM,DIA ou ?text=bom+dia")
    player = STATIC_DIR / "play.html"
    if not player.exists():
        raise HTTPException(500, f"play.html not found at {player}")
    return FileResponse(player, media_type="text/html")


@app.get("/clients/{filename:path}")
def serve_client(filename: str):
    """Serve arquivos da pasta clients/ (translate.html, cli.sh, etc)."""
    if ".." in filename:
        raise HTTPException(400, "invalid filename")
    path = STATIC_DIR / filename
    # fallback: se for diretório, tenta index.html
    if path.is_dir():
        path = path / "index.html"
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "not found")
    # content-type por extensão
    fname = path.name
    if fname.endswith(".html"):
        media = "text/html"
    elif fname.endswith(".js"):
        media = "application/javascript"
    elif fname.endswith(".css"):
        media = "text/css"
    elif fname.endswith(".json"):
        media = "application/json"
    elif fname.endswith(".bvh"):
        media = "model/bvh"
    else:
        media = "application/octet-stream"
    return FileResponse(path, media_type=media)


@app.get("/videos/{filename}")
def get_video(filename: str):
    """Legacy: serve o MP4/GIF do cache local (se Fase 1 com dataset estiver ativa)."""
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    path = CACHE_DIR / filename
    if not path.exists():
        raise HTTPException(404, "not found")
    media = "image/gif" if filename.endswith(".gif") else "video/mp4"
    return FileResponse(path, media_type=media)


# ---- MCP server -------------------------------------------------------------
# Expõe rotas selecionadas como tools no endpoint /mcp (Streamable HTTP).
# Clientes compatíveis: Picoclaw, OpenAI function-calling, MCP Inspector, etc.
# Tools expostas:
#   - glosa(text)         PT → gloss (uppercase Libras, ordem SOV)
#   - translate(text, format)  PT → MP4/GIF com avatar 3D Ícaro + gloss
#   - get_sign_info(word)     metadata do sinal (existe? tamanho?)
#   - get_sign_glb(word)      modelo 3D .glb (experimental — VLibras mudou formato)
if _MCP_AVAILABLE:
    _mcp_server = FastApiMCP(
        app,
        name="libras2",
        description=(
            "Traduz Português para Libras (Língua Brasileira de Sinais). "
            "Use translate(text) para gerar MP4 com avatar 3D oficial Ícaro do VLibras "
            "(fullscreen, com legenda por palavra destacada). Use glosa(text) para só o "
            "gloss em texto. Use get_sign_info(word) para checar se uma palavra existe. "
            "O primeiro render de uma frase leva 60-200s (Chromium + Unity WebGL), "
            "frases repetidas saem em < 1s (cache em disco)."
        ),
        include_operations=[
            "glosa",            # POST /glosa
            "translate",        # POST /translate (binário MP4/GIF)
            "translate_file",   # POST /translate/file (JSON com video_url)
            "get_sign_info",    # GET /signs/{word}/info
            # "get_sign_glb",  # GET /signs/{word}/glb  — desabilitado: VLibras mudou formato
        ],
    )
    _mcp_server.mount_http()  # expõe em /mcp
    logger.info("MCP server mounted at /mcp")
else:
    logger.warning("fastapi-mcp not installed, /mcp not available")
