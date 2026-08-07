"""Testes do serviço vlibras.

Pré-requisito: dataset V-LIBRASIL presente em /opt/vlibras/data/vlibrasil/videos/
(rodar scripts/download_vlibrasil.py antes). Senão os testes rodam em modo smoke
(verificam que a API responde 503/422 e que o /health funciona).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# permite importar o pacote `service` em dev
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from service.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "vocab_size" in body


def test_translate_empty(client):
    r = client.post("/translate", json={"text": ""})
    assert r.status_code == 422  # pydantic validation


def test_translate_returns_shape(client):
    """Se o dataset não está presente, a API deve retornar erro estruturado,
    não crashar. Se está, deve devolver video_url + gloss + missing."""
    r = client.post("/translate", json={"text": "bom dia", "format": "mp4"})
    if r.status_code == 200:
        body = r.json()
        assert "video_url" in body
        assert "gloss" in body
        assert "missing" in body
        assert body["format"] == "mp4"
    else:
        # Sem dataset ou gloss vazio
        assert r.status_code in (422, 503)


def test_normalize_pt_strips_accents():
    from service.gloss import normalize_pt
    assert normalize_pt("Não") == ["nao"]
    assert normalize_pt("  Olá, MUNDO!  ") == ["ola", "mundo"]
    assert normalize_pt("") == []
    assert normalize_pt("ação") == ["acao"]
