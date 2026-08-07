# vlibras

API REST que traduz Português para **Libras** (Língua Brasileira de Sinais) e devolve
MP4/GIF do sinal.

API-first. Sem amarração a nenhum canal. Pode ser consumida por agente, n8n, CLI,
frontend, qualquer cliente HTTP.

## Stack

- **API**: FastAPI + uvicorn
- **Motor Libras**: [`sign-language-translator`](https://github.com/sign-language-translator/sign-language-translator) + dataset V-LIBRASIL
- **Concat de vídeo**: ffmpeg
- **Hospedagem**: bare-metal no `vareni-8` (Ubuntu 24.04, 8GB RAM)

## Quickstart

```bash
# no vareni-8
cd /opt/vlibras
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
| GET  | `/health` | Status + tamanho do vocabulário |
| GET  | `/vocab` | Lista de palavras conhecidas |
| GET  | `/signs/{word}` | MP4 do sinal isolado (debug) |
| POST | `/translate` | `{"text","format"}` → `{gloss, missing, video_url, format}` |
| GET  | `/videos/{filename}` | Serve MP4/GIF do cache |
| GET  | `/docs` | Swagger UI automático |

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

- `clients/cli.sh` — wrapper bash (`vlibras "bom dia"`)
- `clients/n8n-workflow.json` — workflow n8n (Webhook → /translate → vídeo)
- `clients/agent.md` — guia pra LLM chamar via curl/Python

## Licença

MIT.
