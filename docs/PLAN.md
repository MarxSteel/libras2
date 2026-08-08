# libras2 — Plano de Implementação

> API REST que traduz Português para Libras e devolve MP4/GIF do sinal.
> Sem amarração a nenhum canal. Pode ser consumida por agente, n8n, CLI, frontend,
> qualquer cliente HTTP.

## Contexto

A conta `MarxSteel` no GitHub tem `ANP` e `suporte` mas **não tem `libras2`**. O workspace
local `~/Documents/projetos/libras` está vazio. `vareni-8` (195.200.0.69, Ubuntu 24.04, 8GB
RAM) está limpo. O projeto é **greenfield** — `MarxSteel/libras2` será criado do zero.

### Decisões de arquitetura

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

### Por que NÃO outras opções

| Opção | Por que não |
|---|---|
| VLibras oficial self-hosted (Node+Python+avatar 3D) | Pesado (3-4GB RAM), GPU pra render fluente, historicamente problemático de instalar |
| Avatar gerativo (LivePortrait, AVTR-1) | Não faz **tradução semântica** PT→Libras, só dirige boca a partir de áudio |
| SignAvatar (PyPI) | Usa Giphy de ASL (American), não serve pra Libras |
| `sign-language-translator` + datasets PSL/PSK | É pra Paquistão, não Libras |
| `sign-language-processing/pose-to-video` | Precisa de pose sequences gravadas, muito trabalho manual |
| sign-language-translator Libras (se houver) | Não existe ainda como dataset público Libras pronto |

## Arquitetura

```
┌─────────────────┐                                  ┌────────────────────────────┐
│  Cliente HTTP   │   POST /translate                │  libras2 service           │
│                 │   {text, format}                 │  (FastAPI + uvicorn)       │
│  • agente (LLM) │ ──────────────────────────────►  │  :8088                     │
│  • n8n          │                                  │                            │
│  • curl / CLI   │   {gloss, missing, video_url}    │  ┌──────────────────────┐  │
│  • frontend web │ ◄──────────────────────────────  │  │ Translator           │  │
│  • qualquer um  │                                  │  │  PT → gloss          │  │
└─────────────────┘   GET /videos/{hash}.mp4         │  ├──────────────────────┤  │
                       ◄─────────────────────────────  │  │ Renderer             │  │
                                                        │  │  ffmpeg concat       │  │
                                                        │  ├──────────────────────┤  │
                                                        │  │ data/vlibrasil/      │  │
                                                        │  │  1.364 sinais        │  │
                                                        │  │  4.089 vídeos        │  │
                                                        │  └──────────────────────┘  │
                                                        └────────────────────────────┘
```

### Componentes

1. **`service/`** — API FastAPI em Python.
   - `POST /glosa` body `{"text": "..."}` → `{gloss, backend}` (consulta API oficial VLibras)
   - `POST /translate` body `{"text": "...", "format": "mp4"|"gif", "backend": "local"|"vlibras"|"auto"}` → `{gloss, missing, video_url, format, backend, note}`
   - `GET /health` → `{status, vocab_size, data_dir, cache_dir, backends}`
   - `GET /vocab` → lista as palavras do dataset local
   - `GET /signs/{word}` → MP4 do sinal isolado (debug, requer dataset)
   - `GET /videos/{filename}` → serve o MP4/GIF do cache
   - `GET /docs` → Swagger UI automático
2. **`clients/`** — exemplos de consumidores (não fazem parte do core).
   - `agent.md` — guia pra LLM/agente chamar a API
   - `n8n-workflow.json` — workflow de exemplo
   - `cli.sh` — wrapper de linha de comando
3. **`deploy/systemd/`** — unit de produção.
4. **`scripts/`** — download de dataset, health check, rotação de cache.

## Fases

### Fase 0 — Bootstrap ✅

- [x] `vareni-8`: instalar `ffmpeg`, `python3-pip`, `python3-venv`, `jq`.
- [x] `vareni-8`: `mkdir /opt/libras2 && git init -b main`.
- [x] Local: scaffold de pastas em `~/Documents/projetos/libras/`.
- [x] Plano, README, runbook, esqueleto do service, esqueleto dos clientes.
- [ ] **Você**: criar o repo `MarxSteel/libras2` vazio no GitHub e me passar um PAT
      fine-grained com `Contents: Read and write` nesse repo. Alternativa: aceitar
      `--allow-unrelated-histories` e usar o repo local como está.

### Fase 1 — API funcionando (foco principal)

- [ ] Criar venv em `/opt/libras2/venv` (`python3 -m venv`).
- [ ] `pip install -e ./service[all]`.
- [ ] Baixar V-LIBRASIL pra `data/vlibrasil/` (rodar `scripts/download_vlibrasil.py`).
- [ ] Subir `uvicorn service.main:app --port 8088` em background.
- [ ] Smoke test: `curl localhost:8088/health` retorna 200.
- [ ] Smoke test: `curl -X POST localhost:8088/translate -d '{"text":"bom dia"}'` retorna MP4 válido.
- [ ] `pytest` passa (5 frases-fix).
- [ ] **Critério de aceite**: latência `/translate` < 5s para frase de 3 palavras;
      pelo menos 80% das palavras comuns do português (top 1k) cobertas pelo dataset.

### Fase 2 — Produção no `vareni-8` ✅

- [x] `deploy/systemd/libras2.service` instalado e habilitado (`systemctl enable --now`).
- [x] 2 workers uvicorn, `MemoryMax=2G`, hardening básico (NoNewPrivileges, ProtectSystem).
- [x] `journalctl -u libras2 -f` como log padrão.
- [x] Cron `0 3 * * * /opt/libras2/scripts/rotate-cache.sh 7` em `/etc/cron.d/libras2-cache-rotate`.
- [x] `scripts/health.sh` retorna OK (active + /health=200).
- [x] `deploy/systemd/install.sh` reproduz o install (idempotente).
- [x] **Critério de aceite**: serviço ativo, 2 workers, ~98MB RAM, restart OK, sobrevive a reboot.

### Fase 3 — Robustez da tradução

- [ ] Reordenação SOV (Libras usa SOV, português SVO).
- [ ] Lematização (correndo→correr).
- [ ] Fallback de datilologia: palavra sem vídeo → soletrar com alfabeto manual.
- [ ] Endpoint `POST /admin/words` (autenticado) pra subir vídeos novos de palavra custom.
- [ ] Cache LRU em memória pra glosses frequentes.
- [ ] Rate limiting (`slowapi`).
- [ ] **Critério de aceite**: cobertura de frase natural sobe de ~60% pra ~85%.

### Fase 4 — Clientes (paralelo, sob demanda)

- [ ] `clients/n8n-workflow.json` — workflow exemplo: Webhook → translate → responde.
- [ ] `clients/cli.sh` — `libras2 "bom dia" → /tmp/libras.mp4`.
- [ ] `clients/agent.md` — guia pra LLM saber chamar a API via tool/function.
- [ ] (Opcional) `clients/web/` — frontend estático com form + preview do vídeo.
- [ ] **Critério de aceite**: agente consegue traduzir usando só a API sem olhar código.

## Estrutura de Pastas

```
libras2/
├── README.md
├── docs/
│   ├── PLAN.md            ← este arquivo
│   └── OPERATIONS.md
├── service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/
│   │   └── service/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── translator.py
│   │       ├── gloss.py
│   │       └── renderer.py
│   └── tests/
│       └── test_translate.py
├── clients/
│   ├── README.md
│   ├── agent.md            ← como agente/LLM consome
│   ├── n8n-workflow.json   ← workflow exemplo
│   └── cli.sh              ← wrapper bash
├── deploy/
│   └── systemd/
│       └── libras2.service
├── scripts/
│   ├── download_vlibrasil.py
│   ├── health.sh
│   └── rotate-cache.sh
└── data/
    ├── vlibrasil/          ← vídeos do dataset (gitignored, ~3GB)
    └── cache/              ← MP4/GIF gerados (gitignored)
```

## Riscos & Mitigações

| Risco | Mitigação |
|---|---|
| V-LIBRASIL indisponível no Zenodo | Plano B: dataset próprio (gravar 1.3k sinais = 3-6 meses). Plano C: VLibras dictionary-video do `spbgovbr-libras2` |
| Vocabulário V-LIBRASIL incompleto | Fallback de datilologia (Fase 3). Usuário pode subir vídeos próprios (`/admin/words`) |
| RAM do `vareni-8` estourar (8GB) | `MemoryMax=2G` no libras2. Cache LRU com TTL. Cache em disco, não memória |
| ffmpeg concat quebrar com vídeos de tamanhos diferentes | Padronizar resolução 480x360 no V-LIBRASIL; `-c copy` sem reencode (rápido) |
| Concorrência alta (100+ req/s) | `--workers 4` no uvicorn; fila de processamento com timeout |

## Quando pedir ajuda

- **PAT do GitHub** — pra criar o repo e dar push.
- **Aprovação** antes de instalar pacotes (`apt`, `pip`) e baixar dataset grande.
- **Esclarecimento** sobre escopo se aparecer ambiguidade.

## Status atual

- ✅ Repo local inicializado em `/opt/libras2` no `vareni-8` (2 commits).
- ✅ Scaffold sincronizado local + remoto via rsync.
- ✅ Esqueleto de código escrito.
- 🔄 **Próximo passo (Fase 1)**: criar venv, instalar deps, baixar V-LIBRASIL, subir API.
