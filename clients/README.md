# Clientes da libras2 API

A API é o produto. Esses arquivos são **exemplos** de como consumir — não fazem parte
do core. Adicione o seu (frontend, Slack bot, Telegram, Discord, WhatsApp via Baileys,
ou qualquer outro) na mesma pasta.

## Clientes inclusos

| Arquivo | Pra quê |
|---|---|
| `agent.md` | Guia pra um agente/LLM (como eu) chamar a API via `curl` ou `requests` |
| `n8n-workflow.json` | Workflow n8n pronto: Webhook → `/translate` → responde com vídeo |
| `cli.sh` | Wrapper bash pra traduzir direto do terminal: `libras2 "bom dia"` |

## Contrato da API (pra implementar cliente novo)

### `POST /glosa` — só texto, funciona sem dataset

```http
POST /glosa
Content-Type: application/json
{ "text": "bom dia" }

→ 200 OK
{ "text": "bom dia", "gloss": ["BOM", "DIA"], "backend": "vlibras" }
```

A glosa vem da API oficial do VLibras (`traducao2.vlibras.gov.br`), já com
reordenação SOV Libras. Útil pra integrar com n8n, agentes, chatbot etc. mesmo
sem dataset de vídeos.

### `POST /translate` — gloss + vídeo (precisa de dataset)

```http
POST /translate
Content-Type: application/json
{
  "text": "bom dia",
  "format": "mp4",          // ou "gif"
  "backend": "auto"          // "local" | "vlibras" | "auto"
}

→ 200 OK (com dataset)
{
  "text": "bom dia",
  "gloss": ["bom", "dia"],
  "missing": [],
  "video_url": "/videos/abc123.mp4",
  "format": "mp4",
  "backend": "local",
  "note": null
}

→ 422 (sem dataset)
{ "detail": "none of the words are in the vocabulary (missing=['bom','dia'])" }
```

### `GET /health`

```http
GET /health
→ 200 OK
{
  "status": "ok",
  "vocab_size": 0,
  "data_dir": "/opt/libras2/data/vlibrasil",
  "cache_dir": "/opt/libras2/data/cache",
  "backends": { "local": true, "vlibras": true }
}
```

### `GET /vocab`

```http
GET /vocab
→ 200 OK
{ "words": ["bom", "dia", "agua", ...], "size": 1364 }
```

### `GET /signs/{word}` e `GET /videos/{filename}`

Servem o MP4 do dataset local e do cache. Requerem dataset.

## Como adicionar um cliente novo

1. Crie um arquivo `clients/meu-cliente.{py,sh,js,json}` documentando o caso de uso.
2. Se precisar de lib extra (ex: `python-telegram-bot`), adicione em
   `service/pyproject.toml [project.optional-dependencies]` num grupo `clients-telegram`
   ou similar — não infla o core.
3. Mantenha o cliente **stateless**: a API é a fonte de verdade, o cliente só formata.

## TL;DR pra plugar em qualquer lugar

```bash
# descobrir se está no ar
curl -s http://vareni-8:8088/health | jq

# traduzir uma frase
curl -s -X POST http://vareni-8:8088/translate \
    -H 'content-type: application/json' \
    -d '{"text":"bom dia","format":"mp4"}' | jq

# baixar o vídeo
curl -sOJ http://vareni-8:8088/videos/<filename>
```
