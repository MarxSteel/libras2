# libras2 — Plano de Implementação

> **Status atual (2026-08-10):** API rodando em produção no `vareni-8`
> (`http://195.200.0.69:8088`). Avatar 3D Ícaro do VLibras funcionando fullscreen
> com legenda por palavra. Próxima fase: migrar pra nova máquina `72.62.9.238`
> + agente Telegram via fastapi-mcp + Xiaomi MiMo.

---

## Contexto

Greenfield em 2026-08-07. Conta `MarxSteel` no GitHub sem o repo `libras2`.
Workspace local vazio. `vareni-8` (195.200.0.69, Ubuntu 24.04, 8GB RAM) limpo.
**Tudo começou do zero** — `MarxSteel/libras2` foi criado do zero e
empurrado pro GitHub nas primeiras 24h.

### Decisões de arquitetura (originais)

- **API-first**. O entregável principal é um serviço HTTP stateless. Não amarra em
  WhatsApp, Telegram, ou nenhum cliente. Clientes plugam depois.
- **Glosa via API oficial do VLibras** (`https://traducao2.vlibras.gov.br/translate`).
  É a mesma API que o widget do governo usa. Devolve gloss em uppercase com reordenação
  SOV Libras, supressão de pronomes, escolha de sinônimos. Sem custo, sem GPU, sem instalar
  nada. Cache em memória LRU 1000 entries.
- **Vídeo via dataset local** (V-LIBRASIL 1.3k sinais OU manual) — futuro. Por enquanto o
  `/glosa` já é útil sem o dataset.
- **FastAPI + uvicorn**. Maturidade, tipagem, `/docs` automático.
- **ffmpeg** com `-c copy` (sem reencode) pro concat. Cache por hash.
- **sem GPU**. Funciona em CPU puro.

### Decisões de arquitetura (atualizadas em 2026-08-10)

- **Avatar 3D real** via widget oficial do VLibras (`https://vlibras.gov.br/app/vlibras-plugin.js`).
  Player Unity WebGL (Ícaro) carregado em Playwright + chromium-headless-shell.
  Renderiza **qualquer** sinal que o widget reconhece (22.498 do dicionário).
- **Headless Chromium** com `swiftshader` (software WebGL) — sem GPU, ainda assim funciona.
- **Captura de frames** a 8 fps durante a animação, com legenda sincronizada.
- **Concat ffmpeg** → MP4 (libx264) ou GIF (palettegen).
- **Cache em disco** por SHA256(text) — vídeos repetidos saem instantâneos.

### Por que NÃO outras opções

| Opção | Por que não |
|---|---|
| VLibras oficial self-hosted (Node+Python+avatar 3D) | Pesado (3-4GB RAM), GPU pra render fluente, historicamente problemático de instalar. Mas o **widget oficial é embedável** — então usamos ele! |
| Avatar gerativo (LivePortrait, AVTR-1) | Não faz **tradução semântica** PT→Libras, só dirige boca a partir de áudio |
| SignAvatar (PyPI) | Usa Giphy de ASL (American), não serve pra Libras |
| `sign-language-translator` + datasets PSL/PSK | É pra Paquistão, não Libras |
| `sign-language-processing/pose-to-video` | Precisa de pose sequences gravadas, muito trabalho manual |
| Render manual com PIL (renderer_text.py) | Faz **só** visualização textual, não é o sinal animado real. Mantido como **fallback** se widget falhar |

---

## Arquitetura final

```
┌─────────────────┐                                  ┌────────────────────────────┐
│  Cliente HTTP   │   POST /translate                │  libras2 service           │
│                 │   {text, format}                 │  (FastAPI + uvicorn)       │
│  • agente (LLM) │ ──────────────────────────────►  │  :8088                     │
│  • n8n          │                                  │                            │
│  • curl / CLI   │   MP4/GIF (binário)              │  ┌──────────────────────┐  │
│  • frontend web │ ◄──────────────────────────────  │  │ Translator           │  │
│  • Telegram bot │                                  │  │  PT → gloss          │  │
│  • WhatsApp bot │   GET /glosa (JSON)              │  ├──────────────────────┤  │
│  • qualquer um  │ ◄──────────────────────────────  │  │ VLibras Backend      │  │
│                 │                                  │  │  (API oficial gov)   │  │
└─────────────────┘                                  │  ├──────────────────────┤  │
                                                     │  │ Dictionary           │  │
                                                     │  │  22.498 sinais .glb  │  │
                                                     │  ├──────────────────────┤  │
                                                     │  │ Widget Renderer      │  │
                                                     │  │  Playwright +        │  │
                                                     │  │  chromium-headless   │  │
                                                     │  │  + swiftshader       │  │
                                                     │  ├──────────────────────┤  │
                                                     │  │ Text Renderer        │  │
                                                     │  │  (fallback PIL+ffmpeg│  │
                                                     │  └──────────────────────┘  │
                                                     │                            │
                                                     │  data/cache/ (MP4/GIF)     │
                                                     │  data/dictionary/ (.glb)   │
                                                     └────────────────────────────┘
```

### Componentes

1. **`service/src/service/main.py`** — FastAPI app, todas as rotas.
2. **`service/src/service/translator.py`** — tokenização PT + to_gloss local.
3. **`service/src/service/gloss.py`** — pipeline de gloss (normalização PT).
4. **`service/src/service/vlibras_backend.py`** — cliente da API oficial VLibras (com cache LRU).
5. **`service/src/service/dictionary.py`** — cache do dicionário VLibras (22.498 sinais .glb).
6. **`service/src/service/renderer_widget.py`** — **★ avatar 3D Ícaro via Playwright + Chromium headless.**
7. **`service/src/service/renderer_text.py`** — fallback visual (PIL + ffmpeg).
8. **`service/src/service/renderer.py`** — legacy concat MP4 (place dataset).
9. **`clients/play.html`** — player HTML que embedda o widget oficial VLibras.
10. **`deploy/systemd/libras2.service`** — unit de produção.
11. **`scripts/`** — health, rotate-cache, watchdog.

---

## Fases

### Fase 0 — Bootstrap ✅

- [x] `vareni-8`: instalar `ffmpeg`, `python3-pip`, `python3-venv`, `jq`, `ufw`.
- [x] `vareni-8`: `mkdir /opt/libras2 && git init -b main`.
- [x] Local: scaffold de pastas em `~/Documents/projetos/libras/`.
- [x] Plano, README, runbook, esqueleto do service, esqueleto dos clientes.
- [x] Repo `MarxSteel/libras2` criado no GitHub + push inicial.

### Fase 1 — API funcionando (foco principal) ✅

- [x] Criar venv em `/opt/libras2/venv` (`python3 -m venv`).
- [x] `pip install -e ./service[all]`.
- [x] Subir `uvicorn service.main:app --port 8088` em background via systemd.
- [x] `/glosa` integrado com a API oficial VLibras (tradução semântica real).
- [x] `/translate?output=gloss` retorna arquivo `.glosa.json` (sempre funciona).
- [x] `/translate?output=video` retorna MP4 (~64KB) gerado por `renderer_text.py`
      (visualização da glosa, NÃO é o avatar 3D oficial do VLibras).
- [x] `/translate?output=gif` retorna GIF (~45KB), mesmo renderer.
- [x] `/signs/{word}/glb` serve o arquivo UnityFS do dicionário VLibras (22.498 sinais,
      cached em disco).
- [x] 9/9 testes passando.

### Fase 2 — Produção no `vareni-8` ✅

- [x] `deploy/systemd/libras2.service` instalado e habilitado (`systemctl enable --now`).
- [x] 2 workers uvicorn, `MemoryMax=2G`, hardening básico (NoNewPrivileges, ProtectSystem).
- [x] `journalctl -u libras2 -f` como log padrão.
- [x] Cron `0 3 * * * /opt/libras2/scripts/rotate-cache.sh 7` em `/etc/cron.d/libras2-cache-rotate`.
- [x] `scripts/health.sh` retorna OK (active + /health=200).
- [x] `deploy/systemd/install.sh` reproduz o install (idempotente).
- [x] **Critério de aceite**: serviço ativo, 2 workers, ~98MB RAM, restart OK, sobrevive a reboot.
- [x] ufw allow 8088/tcp — IP público `195.200.0.69:8088` responde.
- [x] Tailscale Funnel: `https://srv1521298.tail00b260.ts.net` → 8088.

### Fase 3 — Robustez da tradução ✅ (parcial)

- [x] Fallback automático `local → vlibras` quando gloss local vazio.
- [x] Dicionário VLibras (22.498 sinais) como índice de "tem vídeo".
- [x] Headers `X-Libras2-*` com gloss, missing, backend, note.
- [ ] Reordenação SOV manual (Libras usa SOV, português SVO).
- [ ] Lematização (correndo→correr).
- [ ] Fallback de datilologia: palavra sem vídeo → soletrar com alfabeto manual.
- [ ] Endpoint `POST /admin/words` (autenticado) pra subir vídeos novos de palavra custom.
- [x] Cache LRU em memória pra glosses frequentes.
- [ ] Rate limiting (`slowapi`).

**Nota:** a API oficial VLibras já faz a reordenação SOV, lematização e sinônimos
automaticamente. O gloss retornado já está pronto pra ser renderizado.

### Fase 4 — ★ Avatar 3D Ícaro via widget oficial ✅

- [x] `renderer_widget.py` carrega widget oficial do VLibras em Playwright headless.
- [x] chromium-headless-shell (vs chromium full) pra reduzir RAM.
- [x] swiftshader pra WebGL em CPU puro.
- [x] Viewport 1920×1080 + força fullscreen via `page.evaluate`.
- [x] Descobre estrutura: `[vw] > [vw-plugin-wrapper] > div > #gameContainer.emscripten > canvas#canvas`.
- [x] Esconde UI do widget (header, controles, settings, etc) com `display:none!important`.
- [x] Captura bbox do `gameContainer` (que agora é fullscreen).
- [x] Captura 8 fps × duração.
- [x] Concatena com ffmpeg (libx264 pra MP4, palettegen pra GIF).
- [x] Cache por SHA256(text).
- [x] TMPDIR=/opt/libras2/data/cache (system /tmp é read-only).
- [x] **Critério de aceite**: vídeo com avatar 3D real, corpo inteiro visível, cache hit funcional.

**Honestidade técnica:** primeira render é lenta (60-200s) porque Chromium precisa
inicializar o Unity WebGL. Mas com cache em disco, vídeos repetidos saem em < 1s.
Trade-off aceito: o usuário final não vai esperar isso se a frase for cacheada.

### Fase 5 — ★ Legenda por palavra com highlight animado ✅

- [x] Palavras passadas pro widget via `context.add_init_script("window.__LIBRAS2_WORDS__ = ...")`.
- [x] Caption bar injetada no DOM com `position:fixed; bottom:0; ...`.
- [x] Cada palavra em `<span data-idx>` com opacity 0.55 (não destacada).
- [x] Palavra atual destacada via `__libras2Caption(idx)` — azul + glow + scale 1.05.
- [x] Timing: 1.5s intro + 2.5s por palavra.
- [x] Atualizado por frame no Python via `await page.evaluate(f"window.__libras2Caption({widx})")`.
- [x] **Critério de aceite**: legenda sincronizada com a animação, queimada nos frames.

### Fase 6 — Agente Telegram via fastapi-mcp + Xiaomi MiMo (próximo) ⏳

**Objetivo:** expor a API do Libras2 como MCP tools, conectar num agente de chat
(Picoclaw), configurar LLM Xiaomi MiMo V2.5 Pro, ativar canal Telegram.

**Máquina destino:** `72.62.9.238` (Ubuntu 24.04, 7.8GB RAM, hostname `srv1186168`).

**Stack:**
- `fastapi-mcp` (3 linhas no `main.py`, MIT) — expõe rotas como MCP tools em `/mcp`
- `Picoclaw` (Sipeed, Go, <10MB RAM) — agente de chat leve, channels: Telegram/Discord/etc
- `Xiaomi MiMo V2.5 Pro` (OpenAI-compatible, `https://api.xiaomimimo.com/v1`) — LLM
- Telegram (canal 1, via @BotFather)

**Plano completo:** [`/tmp/migration-plan-72.62.9.238/PLANO_MIGRACAO.md`](/tmp/migration-plan-72.62.9.238/PLANO_MIGRACAO.md) (8 fases, 725 linhas, PT-BR).

**Critério de aceite:** mandar mensagem real no Telegram, bot responde com MP4 Libras.

### Fase 7 — WhatsApp nativo (quando demandar) ⏸

- [ ] Rebuild Picoclaw com `-tags whatsapp_native` (whatsmeow).
- [ ] Escanear QR, salvar sessão.
- [ ] Teste fim-a-fim.

**Risco:** whatsmeow é não-oficial, pode dar ban se uso comercial. Manter Telegram
como primário até resolver.

### Fase 8 — Hardening + monitoring + backup (Fase 8 do plano de migração) ⏳

- [ ] Caddy HTTPS reverse proxy.
- [ ] Watchdog que mata chromium zumbi.
- [ ] Backup automático do `data/` (cache + dicionário).
- [ ] Healthcheck endpoint pra Uptime Kuma / Betterstack.
- [ ] Métricas Prometheus (opcional).

### Fase 9 — Warmup pool + fila de render (chatbot real-time) 💭

**Problema:** chatbot Telegram espera resposta em < 5s, mas render leva 60-200s.

**Soluções possíveis:**
- Pool de N Chromium pré-aquecidos com widget já carregado
- Worker assíncrono que retorna task_id, usuário recebe vídeo via notificação depois
- Fila com priorização (frases comuns pré-renderizadas em batch noturno)

**Decidir** quando chatbot estiver em produção e tivermos dados de uso real.

---

## Estrutura de Pastas (atual)

```
libras2/
├── README.md
├── docs/
│   ├── PLAN.md            ← este arquivo
│   ├── API.md             ← referência completa da API
│   ├── ARCHITECTURE.md    ← decisões (widget, render, cache)
│   └── OPERATIONS.md      ← runbook de produção
├── service/
│   ├── pyproject.toml
│   ├── src/
│   │   └── service/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── translator.py
│   │       ├── gloss.py
│   │       ├── vlibras_backend.py
│   │       ├── dictionary.py
│   │       ├── renderer.py              (legacy)
│   │       ├── renderer_text.py         (fallback)
│   │       └── renderer_widget.py       ★ avatar 3D
│   └── tests/
├── clients/
│   ├── play.html           ★ player do widget VLibras
│   ├── translate.html
│   ├── agent.md            ← como LLM/agente consome
│   ├── n8n-workflow.json
│   └── cli.sh
├── deploy/
│   └── systemd/
│       ├── libras2.service
│       └── install.sh
├── scripts/
│   ├── health.sh
│   ├── rotate-cache.sh
│   └── watchdog.sh
└── data/
    ├── cache/              ← MP4/GIF gerados (gitignored, ~1GB)
    ├── dictionary/         ← .glb dos 22k sinais (gitignored, ~50GB se completo)
    └── samples/            ← exemplos pra teste
```

---

## Riscos & Mitigações

| Risco | Mitigação |
|---|---|
| VLibras oficial mudar widget (versão nova quebra fullscreen JS) | Versões pinadas; hide selectors revalidados a cada release do VLibras |
| VLibras API mudar contrato | Bate em `https://traducao2.vlibras.gov.br/translate`; smoke test diário detecta |
| Chromium memory leak em render longo | Watchdog script mata renderer se RSS > 1.5 GB |
| Cache encher disco | `rotate-cache.sh` remove arquivos > 7 dias; backup opcional em Fase 8 |
| Picoclaw pré-v1.0 quebrar | Pin versão (não `latest`) no plano de migração |
| WhatsApp ban por whatsmeow não-oficial | Telegram como primário; WhatsApp só com opt-in |
| Xiaomi MiMo mudar API | OpenAI-compatible, contrato estável. Fallback = OpenRouter (mesma base) |
| Concorrência alta (100+ req/s) | `--workers 4` no uvicorn (se RAM permitir); fila de processamento com timeout |

---

## Quando pedir ajuda

- **Telegram BotFather** — pra criar bot e pegar token (Fase 6).
- **Xiaomi MiMo API key** — `https://platform.xiaomimimo.com` (Fase 6).
- **Aprovação** antes de instalar pacotes (`apt`, `pip`) em 72.62.9.238.
- **Esclarecimento** sobre escopo se aparecer ambiguidade.

---

## Histórico de commits (vareni-8)

```
1725715 feat(widget): legenda por palavra com highlight animado
f6af96e fix(widget): força fullscreen do avatar Ícaro via JS
cef8124 feat: widget renderer (avatar 3D real do VLibras via Playwright)
11786eb feat: expor API no IP público + ufw allow 8088
ad7b809 feat: video/gif renderer (visualização da glosa)
1f6ab47 fix: install.sh garante +x nos scripts e clients
8aa041b feat: Fase 2 done — systemd + cron + install script
bf23c44 feat: /translate now returns file (gloss/auto/video/gif) instead of JSON
0e339c7 Merge branch 'main' of https://github.com/MarxSteel/libras2
947d69a feat: integrate VLibras official backend (glosa) + restructure translate
e0aa3d3 refactor: rename project vlibras -> libras2
98b9f4d refactor: drop WhatsApp/Hermes, focus on API
c55805c Initial commit
```
