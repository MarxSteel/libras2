# vlibras Hermes Skill

Skill que conecta o [Hermes Agent](https://github.com/NousResearch/hermes-agent) ao serviço `vlibras` (FastAPI).

## Instalação

```bash
# no vareni-8
mkdir -p ~/.hermes/skills/libras
cp -r hermes-skill/* ~/.hermes/skills/libras/

# garante que a dep httpx está disponível pro Hermes
pip install httpx

# reinicia o gateway
hermes gateway restart
```

## Uso

No WhatsApp:

- `!libras bom dia` → vídeo do sinal
- `!libras eu gosto de café por favor` → vídeo encadeado
- `me fala em libras "obrigado"` → auto-trigger, mesmo efeito

## Configuração

`~/.hermes/.env`:

```
VLIBRAS_API_URL=http://127.0.0.1:8088
VLIBRAS_MEDIA_CACHE=/tmp/vlibras-media
WHATSAPP_ALLOWED_USERS=5511999999999
```

## Como funciona

1. Mensagem chega no Hermes via Baileys (WhatsApp Web).
2. Hermes consulta a skill `libras` registrada.
3. `handler.handle()` detecta o trigger (`!libras` ou frase com "em libras").
4. Faz `POST http://127.0.0.1:8088/translate` com o texto limpo.
5. Recebe `{gloss, missing, video_url, format}`.
6. Baixa o vídeo pro disco local e devolve `{text, media}` pro Hermes enviar.

## Teste sem o Hermes

```bash
cd hermes-skill
VLIBRAS_API_URL=http://127.0.0.1:8088 python -c "
from handler import handle
import json
print(json.dumps(handle('!libras bom dia', {}), indent=2, default=str))
"
```
