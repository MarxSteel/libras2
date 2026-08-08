# libras2

API REST que traduz Português para **Libras** (Língua Brasileira de Sinais) e devolve
glosa + (opcionalmente) MP4/GIF do sinal.

API-first. Sem amarração a nenhum canal. Pode ser consumida por agente, n8n, CLI,
frontend, qualquer cliente HTTP.

## Stack

- **API**: FastAPI + uvicorn
- **Glosa**: API oficial do VLibras (`traducao2.vlibras.gov.br/translate`) — já integrada
- **Vídeo (opcional)**: dataset local (V-LIBRASIL) + ffmpeg concat
- **Hospedagem**: bare-metal no `vareni-8` (Ubuntu 24.04, 8GB RAM)

## Quickstart

```bash
# no vareni-8
cd /opt/libras2
python3 -m venv venv && source venv/bin/activate
pip install -e ./service[all]

# baixar V-LIBRASIL pra data/vlibrasil/
python scripts/download_vlibrasil.py

# subir a API
uvicorn service.main:app --host 127.0.0.1 --port 8088

# em outro terminal
curl http://127.0.0.1:8088/health
curl -X POST http://127.0.0.1:8088/translate \
  -H 'content-type: application/json' \
  -d '{"text":"bom dia","format":"mp4"}'
```

## Endpoints

| Método | Path | Descrição |
|---|---|---|
| GET  | `/health` | Status + tamanho do vocabulário local |
| GET  | `/vocab` | Lista de palavras do dataset local |
| POST | `/glosa` | `{"text"}` → `{gloss, backend}` (chama API oficial VLibras) |
| POST | `/translate` | `{"text","format","backend"}` → `{gloss, missing, video_url, ...}` |
| GET  | `/signs/{word}` | MP4 do sinal isolado (debug, requer dataset) |
| GET  | `/videos/{filename}` | Serve MP4/GIF do cache |
| GET  | `/docs` | Swagger UI automático |

**Backends de tradução** (no `/translate`):
- `local` — gloss derivado dos tokens normalizados do input (precisa de dataset)
- `vlibras` — gloss vem da API oficial `traducao2.vlibras.gov.br`
- `auto` (default) — tenta local primeiro, cai pra vlibras se gloss vazio

**`/glosa` funciona agora** sem nenhum dataset — usa a API oficial do VLibras e devolve a glosa real com reordenação SOV Libras.

**`/translate` precisa de dataset local** pra gerar vídeo. Sem o dataset, retorna gloss + lista `missing` (você pode usar a glosa direto via `/glosa`).

## O que o vídeo é (e o que NÃO é)

`/translate?output=video` e `?output=gif` geram um **MP4/GIF visual** da glosa usando PIL + ffmpeg.
**Não é o avatar 3D oficial do VLibras** (que é proprietário e embedado no widget do gov.br).

O que sai:
- Frame 1: título com a frase original em PT
- Frames seguintes: cada palavra da glosa, uma por uma, destacada em verde
- Frame final: glosa completa consolidada

Honestamente: é uma **representação visual da tradução**, não o sinal animado real. Serve
pra visualizar, compartilhar, embedar. Para o avatar animado do VLibras, abra o widget
oficial em `https://www.vlibras.gov.br`.

Sample: `curl -X POST http://vareni-8:8088/translate?output=video -H 'content-type: application/json' -d '{"text":"obrigado meu amigo"}' -OJ`

## Estrutura

```
service/         # API FastAPI (core)
clients/         # exemplos de consumidores (agente, n8n, CLI)
deploy/          # systemd unit
scripts/         # download dataset, health check, cache rotation
data/            # dataset V-LIBRASIL + cache de vídeos gerados
docs/            # PLAN.md, OPERATIONS.md
```

## Documentação

- [`docs/PLAN.md`](docs/PLAN.md) — plano de implementação
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — runbook de produção
- [`clients/agent.md`](clients/agent.md) — guia pra LLM/agente usar a API
- [`clients/README.md`](clients/README.md) — como adicionar novos clientes

## Clientes inclusos

- `clients/cli.sh` — wrapper bash (`libras2 "bom dia"`)
- `clients/n8n-workflow.json` — workflow n8n (Webhook → /translate → vídeo)
- `clients/agent.md` — guia pra LLM chamar via curl/Python

## Licença

MIT.
