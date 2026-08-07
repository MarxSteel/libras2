# vlibras

Bot WhatsApp que recebe mensagem em Português e responde com vídeo de Libras (Língua Brasileira de Sinais).

## Stack

- **Gateway WhatsApp**: [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Baileys, self-hosted, MIT)
- **Motor Libras**: [`sign-language-translator`](https://github.com/sign-language-translator/sign-language-translator) + dataset V-LIBRASIL
- **API**: FastAPI + uvicorn
- **Concatenação de vídeo**: ffmpeg
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
curl -X POST http://127.0.0.1:8088/translate \
  -H 'content-type: application/json' \
  -d '{"text":"bom dia"}'
```

## Estrutura

```
service/         # API FastAPI (core Libras)
hermes-skill/    # skill que pluga o service no Hermes Agent
deploy/          # systemd units
scripts/         # utilidades (download dataset, health check, cache rotation)
data/            # dataset V-LIBRASIL + cache de vídeos gerados
docs/            # PLAN.md, OPERATIONS.md
```

## Documentação

- [`docs/PLAN.md`](docs/PLAN.md) — plano de implementação completo
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — runbook de produção

## Licença

MIT.
