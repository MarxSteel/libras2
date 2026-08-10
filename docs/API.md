# libras2 — Referência da API

> Documentação executável: [`http://195.200.0.69:8088/docs`](http://195.200.0.69:8088/docs) (Swagger UI)
>
> Base URL produção: `http://195.200.0.69:8088` (vareni-8)
> Base URL dev: `http://127.0.0.1:8088`

---

## Sumário

- [`GET /health`](#get-health) — healthcheck
- [`GET /vocab`](#get-vocab) — vocabulário local
- [`POST /glosa`](#post-glosa) — PT → gloss puro
- [`POST /translate`](#post-translate) — PT → gloss + vídeo (MP4/GIF)
- [`POST /translate.json`](#post-translatejson) — variante só-JSON
- [`GET /signs/play`](#get-signsplay) — player HTML interativo
- [`GET /signs/{word}/glb`](#get-signswordglb) — modelo 3D do sinal
- [`GET /signs/{word}/info`](#get-signswordinfo) — metadata do sinal
- [`GET /videos/{filename}`](#get-videosfilename) — MP4/GIF do cache (legacy)
- [`GET /clients/{filename}`](#get-clientsfilename) — serve arquivos estáticos
- [Códigos de erro](#códigos-de-erro)
- [Cache e performance](#cache-e-performance)
- [Headers de resposta](#headers-de-resposta)

---

## `GET /health`

Healthcheck + info do ambiente.

**Request:**
```http
GET /health HTTP/1.1
Host: 195.200.0.69:8088
```

**Response 200:**
```json
{
  "status": "ok",
  "vocab_size": 0,
  "data_dir": "/opt/libras2/data/vlibrasil",
  "cache_dir": "/opt/libras2/data/cache",
  "backends": {
    "local": true,
    "vlibras": true,
    "dictionary": true
  },
  "dictionary": {
    "version": "2018.3.1",
    "platform": "WEBGL"
  }
}
```

**Quando usar:** load balancer healthcheck, monitoring (Uptime Kuma, Betterstack).

---

## `GET /vocab`

Lista de palavras com dataset local. Útil pra debug e pra ver se uma palavra específica
tem vídeo próprio.

**Request:**
```http
GET /vocab HTTP/1.1
```

**Response 200:**
```json
{
  "words": ["abacate", "abacaxi", "abelha", "..."],
  "size": 1364
}
```

**Status atual:** `size: 0` — dataset V-LIBRASIL ainda não foi baixado (não impede
o widget de funcionar, porque o widget busca do dicionário VLibras oficial).

---

## `POST /glosa`

Tradução **PT → gloss** (uppercase, ordem Libras, supressão de pronomes).
É o endpoint mais rápido e leve. Não renderiza vídeo.

**Request:**
```http
POST /glosa HTTP/1.1
Host: 195.200.0.69:8088
Content-Type: application/json

{
  "text": "bom dia meu nome é Marx"
}
```

**Validação:**
- `text`: obrigatório, 1-500 chars
- aceita acentos, números, pontuação

**Response 200:**
```json
{
  "text": "bom dia meu nome é Marx",
  "gloss": [
    "bom&bom-dia",
    "meu&meu-nome",
    "Marx"
  ],
  "backend": "vlibras"
}
```

**Notas:**
- `gloss` é uma lista de **gloss tokens** — cada item pode ser uma palavra ou uma
  expressão multi-palavra (separada por `&`).
- Backend atual sempre é `vlibras` (chama a API oficial).
- A API oficial faz: tokenização, lematização, escolha de sinônimos, reordenação SOV.

**Exemplo curl:**
```bash
curl -X POST http://195.200.0.69:8088/glosa \
  -H 'content-type: application/json' \
  -d '{"text":"obrigado meu amigo"}'
```

---

## `POST /translate`

O endpoint principal. Combina gloss + vídeo.

**Request:**
```http
POST /translate?output=video&download=false HTTP/1.1
Host: 195.200.0.69:8088
Content-Type: application/json

{
  "text": "bom dia meu nome é Marx",
  "format": "mp4",
  "backend": "auto"
}
```

**Body schema:**
| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `text` | string | (required) | Texto em PT, 1-500 chars |
| `format` | string | `"mp4"` | `"mp4"` ou `"gif"` (output pretendido) |
| `backend` | string | `"auto"` | `"local"`, `"vlibras"` ou `"auto"` (estratégia de gloss) |

**Query params:**
| Param | Tipo | Default | Descrição |
|---|---|---|---|
| `output` | string | `"auto"` | `"gloss"`, `"video"`, `"gif"` ou `"auto"` |
| `download` | bool | `false` | Se `true`, `Content-Disposition: attachment` |

**Comportamento por `output`:**

### `output=video` ou `output=gif`

Gera o **MP4/GIF com avatar 3D Ícaro oficial** renderizado em headless Chromium.

**Pipeline:**
1. Chama VLibras API → gloss
2. Carrega `/signs/play?text=...` em Chromium headless
3. Força fullscreen (1920×1080) via JS
4. Esconde UI do widget (header, controles, settings, etc)
5. Captura 8 fps × (1.5s intro + 2.5s × n_palavras)
6. Atualiza legenda em tempo real (`__libras2Caption(idx)`)
7. Concatena com ffmpeg → MP4 (libx264) ou GIF (palettegen)
8. Cache em disco: `data/cache/widget_<sha256(text)[:16]>.{mp4,gif}`

**Response 200 (sucesso):**
- Body: binário do MP4/GIF
- `Content-Type: video/mp4` ou `image/gif`
- `Content-Disposition: inline; filename="bom_dia_meu_nome_e_Marx.mp4"`
- Headers úteis (ver [Headers de resposta](#headers-de-resposta))

**Timing:**
- Cold: 60-200s (depende do tamanho do gloss)
- Warm (cache hit): < 1s
- Vídeos típicos: 100-700 KB para 1-4 sinais

**Exemplo:**
```bash
curl -X POST "http://195.200.0.69:8088/translate?output=video" \
  -H 'content-type: application/json' \
  -d '{"text":"obrigado meu amigo"}' -OJ

# explicitamente MP4
curl -X POST "http://195.200.0.69:8088/translate?output=video&download=true" \
  -H 'content-type: application/json' \
  -d '{"text":"bom dia"}' -OJ --output bom_dia.mp4

# GIF animado
curl -X POST "http://195.200.0.69:8088/translate?output=gif" \
  -H 'content-type: application/json' \
  -d '{"text":"eu te amo"}' -OJ
```

### `output=gloss`

Retorna **só o gloss** como arquivo `.glosa.json`. Não renderiza nada. Sempre rápido.

**Response 200:**
- Body: JSON (ver schema de [glosa acima](#post-glosa))
- `Content-Type: application/json`
- `Content-Disposition: inline; filename="<text>.glosa.json"`

**Exemplo:**
```bash
curl -X POST "http://195.200.0.69:8088/translate?output=gloss" \
  -H 'content-type: application/json' \
  -d '{"text":"obrigado meu amigo"}' -OJ

# retorna arquivo: obrigado_meu_amigo.glosa.json
```

### `output=auto` (default)

Se todos os sinais do gloss têm vídeo no dataset/dicionário → MP4.
Senão → arquivo de gloss.

---

## `POST /translate.json`

Variante de `/translate` que **sempre** devolve JSON, nunca binário. Útil pra clientes
que querem metadata do vídeo em vez do vídeo em si.

**Request:** idêntico a `/translate`.

**Response 200:**
```json
{
  "text": "obrigado meu amigo",
  "gloss": ["obrigado&agradecimento", "meu", "amigo"],
  "missing": [],
  "video_url": "/signs/play?gloss=obrigado%26agradecimento%2Cmeu%2Camigo&from=text&text=obrigado%20meu%20amigo",
  "format": "mp4",
  "backend": "vlibras",
  "note": "local gloss empty, used vlibras backend"
}
```

**Diferença pro `/translate`:** aqui `video_url` aponta pro **player HTML interativo**
(`/signs/play`), não pro MP4 cacheado. Cliente que quiser o MP4 deve chamar `/translate?output=video`.

---

## `GET /signs/play`

Player HTML standalone que embedda o widget oficial do VLibras. Serve pra preview
no browser e pra casos onde você quer o widget real interativo (não o vídeo renderizado).

**Request:**
```http
GET /signs/play?text=obrigado HTTP/1.1
```

**Query params:**
| Param | Tipo | Default | Descrição |
|---|---|---|---|
| `text` | string | — | Texto PT a traduzir (faz `/glosa` no client) |
| `gloss` | string | — | Gloss já computado (formato: `BOM,DIA,MEU,NOME,MARX`) |

**Response 200:**
- `Content-Type: text/html`
- HTML que carrega `https://vlibras.gov.br/app/vlibras-plugin.js`
- Avatar 3D Ícaro interativo, com todos os controles do widget oficial

**Exemplo:**
```
http://195.200.0.69:8088/signs/play?text=obrigado
http://195.200.0.69:8088/signs/play?text=bom%20dia
```

---

## `GET /signs/{word}/glb`

Baixa o **modelo 3D .glb** (Unity3D exportado) do sinal da palavra `word`.
Útil pra integrar o sinal em outro player Three.js ou pra inspeção.

**Request:**
```http
GET /signs/obrigado/glb HTTP/1.1
```

**Response 200:**
- `Content-Type: model/gltf-binary`
- Body: binário do .glb (1-5 MB típico)
- `X-Libras2-Dictionary: 2018.3.1/WEBGL`

**Cache:** primeira vez baixa de `dicionario2.vlibras.gov.br/2018.3.1/WEBGL/<word>` e cacheia
em `data/dictionary/`. Próximas chamadas saem do disco.

**Exemplo:**
```bash
# baixa o modelo 3D do sinal "obrigado"
curl -o obrigado.glb http://195.200.0.69:8088/signs/obrigado/glb
# abre em https://gltf-viewer.donmccurdy.com/
```

---

## `GET /signs/{word}/info`

Metadata do sinal sem baixar o .glb inteiro. Bom pra checar se existe antes de renderizar.

**Request:**
```http
GET /signs/obrigado/info HTTP/1.1
```

**Response 200 (existe):**
```json
{
  "word": "obrigado",
  "exists": true,
  "size_bytes": 184320,
  "dictionary": {
    "version": "2018.3.1",
    "platform": "WEBGL",
    "base": "https://dicionario2.vlibras.gov.br"
  }
}
```

**Response 200 (não existe):**
```json
{
  "word": "palavra-que-nao-existe",
  "exists": false,
  "size_bytes": null,
  "dictionary": {
    "version": "2018.3.1",
    "platform": "WEBGL",
    "base": "https://dicionario2.vlibras.gov.br"
  }
}
```

**Uso:** validar input antes de gastar 60-200s renderizando um sinal que não existe.

---

## `GET /videos/{filename}`

Serve MP4/GIF do cache local (`data/cache/`). Legacy — o endpoint principal é
`/translate?output=video`, que já devolve o arquivo como resposta.

**Request:**
```http
GET /videos/widget_a1b2c3d4e5f6.mp4 HTTP/1.1
```

**Response 200:**
- `Content-Type: video/mp4` ou `image/gif`
- Body: binário

**Response 404:** arquivo não existe no cache.

**Filename format:** `widget_<sha256(text)[:16]>.<ext>` — mesmo padrão usado pelo renderer.

**Exemplo:**
```bash
# descobre o hash de um texto
echo -n "obrigado" | sha256sum | cut -c1-16
# → a1b2c3d4e5f6...

# baixa do cache
curl -o obrigado.mp4 http://195.200.0.69:8088/videos/widget_a1b2c3d4e5f6.mp4
```

---

## `GET /clients/{filename}`

Serve arquivos da pasta `clients/` (HTML, JS, CSS, JSON, etc). Útil pra embedar
o player em outra página.

**Request:**
```http
GET /clients/agent.md HTTP/1.1
```

**Content-Type por extensão:**
- `.html` → `text/html`
- `.js` → `application/javascript`
- `.css` → `text/css`
- `.json` → `application/json`
- outros → `application/octet-stream`

**Validação:** bloqueia `..` no path (defesa contra path traversal).

---

## Códigos de erro

| Código | Quando | Body típico |
|---|---|---|
| 400 | Input inválido (parâmetro obrigatório faltando, formato errado) | `{"detail": "empty text after normalization"}` |
| 404 | Sinal não existe no dicionário / arquivo não encontrado | `{"detail": "sign not found: 'palavra'"}` |
| 422 | Sem gloss de nenhum backend (texto inválido ou backend falhou) | `{"detail": "no gloss from any backend (input: '...')"}` |
| 500 | Renderer falhou (Chromium crashou, ffmpeg erro) | `{"detail": "renderer error: ..."}` |
| 503 | VLibras backend ou dicionário indisponível | `{"detail": "vlibras backend unavailable: ..."}` |

---

## Headers de resposta

Toda resposta de `/glosa`, `/translate`, `/translate.json` inclui:

| Header | Quando | Valor |
|---|---|---|
| `X-Libras2-Gloss` | sucesso | gloss como string único (`"BOM DIA MEU"`) |
| `X-Libras2-Missing` | sucesso | palavras sem sinal (separadas por `,`) |
| `X-Libras2-Backend` | sucesso | `"local"`, `"vlibras"` ou `"auto"` |
| `X-Libras2-Note` | sucesso | aviso contextual (ex: `"local gloss empty, used vlibras backend"`) |
| `X-Libras2-Rendered-Gloss` | vídeo | subset do gloss que foi renderizado |
| `X-Libras2-Dictionary` | `/glb` | `"<version>/<platform>"` |
| `Content-Disposition` | download | `inline; filename="..."` ou `attachment; filename="..."` |

Úteis pra logging, métricas e debug.

---

## Cache e performance

**Dois níveis de cache:**

1. **Em memória (LRU)** — só gloss
   - VLibras backend tem LRU interno
   - `get_dictionary()` carrega índice no startup (1 requisição)
   - Hit: < 5ms

2. **Em disco (SHA256)** — vídeos e dicionário
   - `data/cache/widget_<hash>.<ext>` — MP4/GIF renderizados
   - `data/dictionary/<hash>.glb` — modelos 3D baixados
   - Hit: < 1s (só I/O)
   - Limpeza: cron `0 3 * * *` remove arquivos > 7 dias

**Forçar re-render:** apague o arquivo do cache.
```bash
# recriar vídeo de "obrigado"
rm -f /opt/libras2/data/cache/widget_$(echo -n "obrigado" | sha256sum | cut -c1-16).mp4
curl -X POST "http://195.200.0.69:8088/translate?output=video" \
  -H 'content-type: application/json' -d '{"text":"obrigado"}' -OJ
```

---

## Limites e quotas

| Recurso | Limite | Configurável |
|---|---|---|
| Tamanho do input | 500 chars | sim (`Field(max_length=...)` em `main.py`) |
| Render time | 30s de vídeo | sim (`duration_s` em `renderer_widget.py`) |
| Concorrência | 2 workers uvicorn | sim (`--workers` no systemd) |
| RAM por worker | 2.5 GB | sim (`MemoryMax=2.5G` no systemd) |
| Disco por vídeo | 1-2 MB | n/a |
| Disco total cache | ilimitado (até encher) | rodar `rotate-cache.sh` |

**Comportamento sob pressão:**
- `MemoryMax` do systemd mata o worker se passar (restart automático em 5s)
- Watchdog script mata chromium zumbi se RSS > 1.5 GB
- Disco cheio → renderer falha, log mostra `OSError: No space left on device`

---

## SDKs / clientes

**Não tem SDK oficial ainda.** Use HTTP direto (curl, fetch, requests, axios).

**Python exemplo:**
```python
import requests

# glosa
r = requests.post("http://195.200.0.69:8088/glosa",
                  json={"text": "bom dia"})
print(r.json()["gloss"])
# → ['bom&bom-dia', ...]

# vídeo
r = requests.post("http://195.200.0.69:8088/translate?output=video",
                  json={"text": "obrigado meu amigo"})
with open("saida.mp4", "wb") as f:
    f.write(r.content)
print(f"salvo: {len(r.content)} bytes, {r.headers['X-Libras2-Backend']}")
```

**Node exemplo:**
```js
const fs = require('fs');
const res = await fetch('http://195.200.0.69:8088/translate?output=video', {
  method: 'POST',
  headers: {'content-type': 'application/json'},
  body: JSON.stringify({text: 'obrigado meu amigo'}),
});
const buf = Buffer.from(await res.arrayBuffer());
fs.writeFileSync('saida.mp4', buf);
console.log('salvo:', buf.length, 'bytes');
```

---

## Changelog

| Versão | Data | Mudança |
|---|---|---|
| 0.1.0 | 2026-08-08 | API inicial: `/glosa` + `/translate` com renderer de texto (PIL) |
| 0.2.0 | 2026-08-09 | Integração VLibras backend + dictionary + restructure `/translate` |
| 0.3.0 | 2026-08-10 | **Widget renderer**: avatar 3D Ícaro fullscreen via Playwright |
| 0.3.1 | 2026-08-10 | **Legenda por palavra** com highlight animado |

Próxima: 0.4.0 — fastapi-mcp + agente Telegram (Fase 6 do roadmap)
