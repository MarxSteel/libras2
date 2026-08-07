"""Testes do serviço libras2.

Pré-requisito: dataset V-LIBRASIL presente em /opt/libras2/data/vlibrasil/videos/
(rodar scripts/download_vlibrasil.py antes). Senão os testes rodam em modo smoke
(verificam que a API responde 503/422 e que o /health funciona).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

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
    assert body["backends"]["vlibras"] is True


def test_vocab(client):
    r = client.get("/vocab")
    assert r.status_code == 200
    body = r.json()
    assert "words" in body
    assert "size" in body


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
        assert "backend" in body
    else:
        # Sem dataset ou gloss vazio
        assert r.status_code in (422, 503)


def test_glosa_mocked(client):
    """Com a API do VLibras mockada, /glosa devolve a glosa direto."""
    with patch("service.vlibras_backend.get_backend") as mock:
        backend = mock.return_value
        backend.translate.return_value = ["BOM", "DIA"]
        r = client.post("/glosa", json={"text": "bom dia"})
        assert r.status_code == 200
        body = r.json()
        assert body["gloss"] == ["BOM", "DIA"]
        assert body["backend"] == "vlibras"


def test_normalize_pt_strips_accents():
    from service.gloss import normalize_pt
    assert normalize_pt("Não") == ["nao"]
    assert normalize_pt("  Olá, MUNDO!  ") == ["ola", "mundo"]
    assert normalize_pt("") == []
    assert normalize_pt("ação") == ["acao"]


def test_translate_with_vlibras_backend_mocked(client):
    """Com a API do VLibras mockada, /translate com backend=vlibras devolve gloss
    e missing (vai estar missing pq vocab=0)."""
    with patch("service.vlibras_backend.get_backend") as mock:
        backend = mock.return_value
        backend.translate.return_value = ["BOM", "DIA"]
        r = client.post("/translate", json={
            "text": "bom dia", "format": "mp4", "backend": "vlibras",
        })
        # Sem dataset, gloss existe mas missing tudo → 422
        if r.status_code == 200:
            body = r.json()
            assert body["backend"] == "vlibras"
        else:
            assert r.status_code == 422
