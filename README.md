# libras2

API REST que traduz Português para **Libras** (Língua Brasileira de Sinais) e devolve
**MP4/GIF com o avatar 3D oficial Ícaro do VLibras**, fullscreen, com legenda por palavra.

API-first. Sem amarração a nenhum canal. Pode ser consumida por agente, n8n, CLI,
frontend, qualquer cliente HTTP. Integra direto com Telegram, WhatsApp, webhooks, etc.

## Quickstart

**Base URL pública (produção)**: `http://195.200.0.69:8088` (IP público da `vareni-8`, porta 8088 liberada no ufw).
**Tailscale Funnel**: `https://srv1521298.tail00b260.ts.net` (mesmo serviço via HTTPS).

```bash
# health check
curl http://195.200.0.69:8088/health

# glosa pura (sempre funciona, ~200ms)
curl -X POST http://195.200.0.69:8088/glosa \
  -H 'content-type: application/json' \
  -d '{"text":"obrigado meu amigo"}'

# MP4 com avatar 3D Ícaro (fullscreen + legenda por palavra)
# cold: ~3min (primeira vez) | warm: < 1s (cache hit)
curl -X POST "http://195.200.0.69:8088/translate?output=video" \
  -H 'content-type: application/json' \
  -d '{"text":"bom dia meu nome é Marx"}' -OJ
```

## O que é o vídeo

O `/translate?output=video` gera um **MP4 real com o personagem 3D Ícaro oficial do VLibras**
executando os sinais. Não é uma representação visual, não é texto animado, é o avatar do
gov.br renderizado em headless Chromium e capturado frame a frame.

**Pipeline de render:**
1. Chromium headless carrega `/signs/play?text=...` que embedda o widget oficial do VLibras
2. Player forçado a 1920×1080 (fullscreen) via `page.evaluate`
3. Captura screenshots em loop a 8 fps durante a animação
4. Atualiza legenda em tempo real (`__libras2Caption(idx)` JS) sincronizada com timing de cada palavra
5. Concatena com ffmpeg → MP4 (libx264) ou GIF (palettegen)
6. Cacheia em disco por SHA256(text) — vídeos repetidos saem instantâneos

**Timing da legenda:** 1.5s de intro + 2.5s por palavra. Palavra atual destacada em azul com
glow, outras em cinza. Queimada nos frames → assista em qualquer player.

**Trade-off honesto:** primeira render é lenta (Chromium + Unity WebGL = 60-200s). Cache em
disco resolve. Pra 1-10 frases comuns, isso é aceitável. Pra chamada em tempo real (chatbot),
veja [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) sobre fila de warmup.

## Stack

| Camada | Tech | Por quê |
|---|---|---|
| API | FastAPI + uvicorn | Tipagem, /docs, async, padrão de mercado |
| Glosa | VLibras oficial (`traducao2.vlibras.gov.br/translate`) | Mesma API que o widget do gov.br usa, sem custo, sem GPU |
| Dicionário | VLibras (`dicionario2.vlibras.gov.br`) | 22.498 sinais com .glb do Unity3D |
| Avatar 3D | VLibras widget (Unity WebGL) | Avatar Ícaro real, executa qualquer sinal |
| Render headless | Playwright + chromium-headless-shell | Único jeito de automatizar o widget oficial |
| Browser GPU | swiftshader (software WebGL) | Sem GPU no host, ainda assim roda |
| Vídeo final | ffmpeg (libx264 / palettegen) | Padrão, rápido, cache-friendly |

## Endpoints

| Método | Path | O que faz |
|---|---|---|
| GET  | `/health` | Status + tamanho vocab + versão dicionário |
| GET  | `/vocab` | Lista de palavras com dataset local |
| POST | `/glosa` | PT → gloss (libras, uppercase, ordem Libras) |
| POST | `/translate` | Combina gloss + vídeo, saída MP4/GIF/gloss-file |
| POST | `/translate.json` | Variante que sempre devolve JSON (schema antigo) |
| GET  | `/signs/play` | Player HTML com widget VLibras (preview interativo) |
| GET  | `/signs/{word}/glb` | .glb 3D do sinal (do dicionário oficial) |
| GET  | `/signs/{word}/info` | Metadata: existe? tamanho? origem? |
| GET  | `/videos/{filename}` | Serve MP4/GIF do cache (legacy) |
| GET  | `/clients/{filename}` | Serve arquivos da pasta `clients/` |
| GET  | `/docs` | Swagger UI automático |

**Query params do `/translate`:**
- `output=gloss` → arquivo `.glosa.json` (sempre funciona, < 1s)
- `output=video` → MP4 com avatar 3D (3min cold, < 1s warm)
- `output=gif` → GIF animado (mesmo tempo do MP4)
- `output=auto` → video se dicionário tem todos os sinais, senão gloss
- `download=true` → serve como attachment

**Backends de tradução:**
- `local` — gloss derivado dos tokens normalizados (precisa dataset local)
- `vlibras` — gloss vem da API oficial do gov.br
- `auto` (default) — tenta local primeiro, cai pra vlibras

## Instalar do zero

```bash
# no host (Ubuntu 24.04, 8GB RAM, sem GPU necessária)
git clone https://github.com/MarxSteel/libras2.git /opt/libras2
cd /opt/libras2
python3 -m venv venv && source venv/bin/activate
pip install -e ./service[all]
playwright install --with-deps chromium  # ~200MB

# deploy
sudo cp deploy/systemd/libras2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now libras2.service
sudo ufw allow 8088/tcp

curl http://127.0.0.1:8088/health
```

## Estrutura

```
libras2/
├── README.md
├── docs/
│   ├── PLAN.md            ← plano de implementação (histórico + roadmap)
│   ├── API.md             ← referência completa de endpoints
│   ├── ARCHITECTURE.md    ← decisões de arquitetura (widget, render, cache)
│   └── OPERATIONS.md      ← runbook de produção
├── service/
│   ├── pyproject.toml
│   ├── src/service/
│   │   ├── main.py              ← FastAPI app
│   │   ├── translator.py        ← normalização PT + to_gloss
│   │   ├── gloss.py             ← pipeline de gloss
│   │   ├── vlibras_backend.py   ← cliente da API oficial VLibras
│   │   ├── dictionary.py        ← cache do dicionário VLibras (22k sinais)
│   │   ├── renderer_text.py     ← fallback visual (PIL+ffmpeg)
│   │   ├── renderer_widget.py   ← ★ avatar 3D Ícaro via Playwright
│   │   └── renderer.py          ← legacy concat MP4
│   └── tests/
├── clients/
│   ├── play.html                ← player do widget VLibras
│   ├── translate.html
│   ├── agent.md                 ← guia pra LLM consumir a API
│   ├── cli.sh
│   └── n8n-workflow.json
├── deploy/
│   └── systemd/
│       ├── libras2.service
│       └── install.sh
├── scripts/
│   ├── health.sh
│   ├── rotate-cache.sh
│   └── watchdog.sh
└── data/
    ├── cache/                   ← MP4/GIF gerados (gitignored, ~1GB)
    ├── dictionary/              ← .glb dos 22k sinais (gitignored)
    └── samples/                 ← exemplos pra teste
```

## Casos de uso

- **Chatbot Telegram/WhatsApp** — recebe PT, responde com vídeo Libras + texto da glosa
- **Frontend acessível** — embed direto do player `/signs/play?text=...`
- **Pipeline de legendagem** — `/glosa` pra extrair a glosa estruturada, `?output=gloss` pra JSON
- **Pesquisa de vocabulário** — `/signs/{word}/info` pra ver se o sinal existe antes de renderizar
- **Avatares 3D standalone** — `/signs/{word}/glb` baixa o .glb pra usar em outro player Three.js

## Performance

| Operação | Cold | Warm (cache) |
|---|---|---|
| `/glosa` | ~200ms (API gov.br) | < 5ms (LRU) |
| `/translate?output=gloss` | ~200ms | < 5ms |
| `/translate?output=video` | 60-200s (Chromium + Unity) | < 1s |
| `/translate?output=gif` | 60-200s | < 1s |
| `/signs/{word}/glb` | ~1s (download dicionário) | < 10ms |
| `/signs/{word}/info` | < 50ms (check local) | < 50ms |

**Limite de RAM em produção:** 2GB (systemd MemoryMax). Chromium consome ~500MB
em pico, 2 workers uvicorn ~200MB, sobra ~1.3GB pra cache de páginas do Unity.

## Clientes inclusos

- `clients/cli.sh` — wrapper bash (`libras2 "bom dia"`)
- `clients/n8n-workflow.json` — workflow n8n (Webhook → /translate → vídeo)
- `clients/agent.md` — guia pra LLM/tool use consumir a API
- `clients/play.html` — player HTML standalone do widget VLibras

## Roadmap

- [x] Fase 0 — bootstrap + repo
- [x] Fase 1 — API funcionando (glosa + gloss file)
- [x] Fase 2 — produção no vareni-8 (systemd + ufw)
- [x] Fase 3 — robustez tradução (auto fallback vlibras)
- [x] Fase 4 — ★ avatar 3D Ícaro via widget oficial (Playwright)
- [x] Fase 5 — ★ legenda por palavra com highlight animado
- [ ] Fase 6 — fastapi-mcp + agente Telegram (próximo: máquina 72.62.9.238)
- [ ] Fase 7 — WhatsApp nativo (quando demandar)
- [ ] Fase 8 — warmup pool + fila de render (chatbot real-time)

## Licença

MIT.
