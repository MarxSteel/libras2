# vlibras — Plano de Implementação

> Bot WhatsApp que recebe mensagem em Português, gera Libras e responde com GIF/vídeo.

## Contexto

A conta `MarxSteel` no GitHub tem `ANP` e `suporte` mas **não tem `vlibras`**. O workspace local
`~/Documents/projetos/libras` está vazio. `vareni-8` (195.200.0.69, Ubuntu 24.04, 8GB RAM)
não tem `gh` nem token do GitHub salvo. Então o projeto é **greenfield** — vamos criar
`MarxSteel/vlibras` do zero, versionar, e empurrar pra origin quando o PAT estiver disponível.

### Por que essas escolhas

- **Greenfield**: nenhuma base utilizável; VLibras oficial é monolito pesado e difícil de instalar.
- **Hermes Agent** (e não OpenClaw) como gateway WhatsApp: stack Python (mesma do nosso serviço),
  skill system nativo pra plugar nossa API, memória persistente, MIT, 140k⭐.
- **`sign-language-translator` + V-LIBRASIL** como motor Libras: open-source MIT, leve, cabe no
  `vareni-8`, dataset brasileiro (1.364 sinais, UFPE). Trade-off: vocabulário menor que o VLibras
  oficial; palavras fora do dicionário recebem fallback de datilização soletrada.

## Arquitetura

```
┌──────────────┐    Baileys      ┌────────────────────┐    HTTP     ┌────────────────────┐
│  Celular do  │  ───────────►   │  Hermes Agent      │ ──────────► │  vlibras service   │
│  usuário     │   WhatsApp Web  │  (vareni-8)        │  /translate │  (FastAPI)         │
│              │  ◄───────────   │  + skill Libras    │ ◄────────── │  + SLT + V-LIBRASIL│
└──────────────┘                 └────────────────────┘   MP4/GIF   └────────────────────┘
                                          │                          │
                                          ▼                          ▼
                                ~/.hermes/memory/           data/vlibrasil/videos/
                                (histórico contatos)        (4.089 vídeos, 1.364 sinais)
```

### Componentes

1. **`service/`** — API FastAPI em Python.
   - `POST /translate` body `{"text": "bom dia"}` → `{"video_url": "...", "gloss": "...", "missing": [...], "format": "mp4"}`
   - `GET /health` → `{"status": "ok", "vocab_size": 1364, "ffmpeg": "6.x"}`
   - `GET /signs/{word}` → MP4 do sinal isolado (debug)
   - Pipeline: `normalizar PT → tokenizar → mapear gloss → buscar vídeos → ffmpeg concat`.
2. **`hermes-skill/`** — Skill Python que o Hermes carrega.
   - Recebe mensagem WhatsApp; se for comando `!libras <texto>`, chama `service` e responde com o vídeo anexado.
   - Whitelist de números no `.env` do Hermes.
3. **`deploy/systemd/`** — Serviços persistentes no `vareni-8`.
   - `vlibras.service` (FastAPI em `uvicorn`, porta 8088).
   - `hermes.service` (já provido pelo instalador do Hermes).

## Fases

### Fase 0 — Bootstrap (já em andamento)

- [x] `vareni-8`: instalar `ffmpeg`, `python3-pip`, `python3-venv`, `jq`.
- [x] `vareni-8`: `mkdir /opt/vlibras && git init -b main`.
- [x] Local: scaffold de pastas em `~/Documents/projetos/libras/`.
- [ ] **Você**: criar o repo `MarxSteel/vlibras` vazio no GitHub (sem README/license/.gitignore, pra dar `git push` limpo) e me passar um PAT de fine-grained com `Contents: Read and write` no `MarxSteel/vlibras`. Alternativa: aceitar a `--allow-unrelated-histories` e usar o repo local.
- [ ] `vareni-8`: `git remote add origin https://x-access-token:<PAT>@github.com/MarxSteel/vlibras.git` e `git push -u origin main`.

### Fase 1 — Serviço Core de Libras

- [ ] Criar `service/pyproject.toml` (deps: `fastapi`, `uvicorn[standard]`, `sign-language-translator[all]`, `pydantic`, `Pillow`).
- [ ] `service/Dockerfile` baseado em `python:3.12-slim` (com `ffmpeg` instalado via apt).
- [ ] `service/src/main.py` — FastAPI app, rotas `/health`, `/translate`, `/signs/{word}`.
- [ ] `service/src/gloss.py` — normalização PT-BR (lowercase, remove acentos pra lookup, trata números/datas).
- [ ] `service/src/translator.py` — wrapper do `ConcatenativeSynthesis` do `sign-language-translator`.
- [ ] `service/src/renderer.py` — `ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4` + fallback pra GIF com `palettegen`.
- [ ] Baixar V-LIBRASIL pra `data/vlibrasil/`. Origem: Zenodo ou GitHub do paper "Less is more" (V-LIBRASIL, 1.364 sinais × 3 sinalizantes).
- [ ] Cache LRU em disco (`data/cache/`) por hash do texto.
- [ ] `service/tests/` — `pytest` com 5 frases-fix: "bom dia", "eu gosto de você", "obrigado", "água por favor", "não entendi".
- [ ] **Critério de aceite**: `curl localhost:8088/translate -d '{"text":"bom dia"}'` retorna MP4 com pelo menos 2 sinais encadeados e `< 5s` de latência.

### Fase 2 — Gateway WhatsApp (Hermes)

- [ ] `pip install hermes-agent` no `vareni-8`.
- [ ] `hermes setup` em modo não-interativo: provider=OpenRouter (free tier), model=`nvidia/nemotron-3-super-120b-a12b`, terminal=local.
- [ ] `hermes whatsapp` — escanear QR do WhatsApp Business (recomenda-se número dedicado pra não banir o pessoal).
- [ ] Configurar `~/.hermes/.env`:
  ```
  WHATSAPP_ENABLED=true
  WHATSAPP_MODE=bot
  WHATSAPP_ALLOWED_USERS=<seu número com DDI, sem +>
  VLIBRAS_API_URL=http://127.0.0.1:8088
  ```
- [ ] `hermes gateway install` + `hermes gateway start` (systemd user service).
- [ ] Teste manual: mandar `oi` pro número e ver o bot responder.

### Fase 3 — Skill Libras

- [ ] `hermes-skill/handler.py` — recebe a mensagem, detecta prefixo `!libras` ou intent automático (quando o user pedir "me ensina em libras" / "manda em sinais" / etc.).
- [ ] Faz `requests.post(VLIBRAS_API_URL + "/translate", json={"text": msg})`.
- [ ] Baixa o MP4 retornado e envia via Baileys como `document` (vídeo) ou `image` (gif).
- [ ] Se a API retornar `missing: [...]`, responde em texto: "Não achei os sinais de: X, Y. Soletrei em datilologia."
- [ ] Logging: cada chamada vai pra `~/.hermes/memory/libras-log.jsonl` (texto, gloss, missing, latência, status).
- [ ] **Critério de aceite**: mandar `!libras bom dia` pelo WhatsApp retorna vídeo de ~2-3s em < 8s.

### Fase 4 — Produção

- [ ] `deploy/systemd/vlibras.service` — `ExecStart=/opt/vlibras/venv/bin/uvicorn service.main:app --host 127.0.0.1 --port 8088 --workers 2`. `Restart=always`. `MemoryMax=2G`.
- [ ] `deploy/systemd/hermes.service` (overlay do user service se necessário) + `Wants=vlibras.service` no Hermes.
- [ ] `journalctl -u vlibras -f` + `journalctl -u hermes -f` configurados como padrão de operação.
- [ ] Script `scripts/health.sh` que pinga os dois e posta num webhook se cair (opcional).
- [ ] Cron diário: `scripts/rotate-cache.sh` — apaga MP4 com > 7 dias de `data/cache/`.
- [ ] Documentação: `README.md` com quickstart, `docs/OPERATIONS.md` com runbook de incidente.

## Estrutura de Pastas

```
vlibras/
├── README.md
├── docs/
│   ├── PLAN.md            ← este arquivo
│   └── OPERATIONS.md
├── service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py
│   │   ├── translator.py
│   │   ├── gloss.py
│   │   └── renderer.py
│   └── tests/
│       └── test_translate.py
├── hermes-skill/
│   ├── handler.py
│   ├── skill.yml
│   └── README.md
├── deploy/
│   └── systemd/
│       └── vlibras.service
├── scripts/
│   ├── health.sh
│   └── rotate-cache.sh
└── data/
    ├── vlibrasil/         ← vídeos do dataset (gitignored)
    └── cache/             ← MP4 gerados (gitignored)
```

## Riscos & Mitigações

| Risco | Mitigação |
|---|---|
| Ban do número WhatsApp (Meta flagging) | Usar número dedicado (chip separado) só pro bot, não misturar com WhatsApp pessoal. |
| RAM do `vareni-8` estourar (8GB) | `MemoryMax=2G` no vlibras; cache LRU com TTL; parar Hermes se >6GB. |
| Palavra fora do vocabulário | Fallback de datilologia (alfabeto manual) + aviso textual. |
| V-LIBRASIL indisponível no Zenodo | Plano B: usar `sign-language-translator` com dataset próprio gravado manualmente (mais longo). |
| Latência alta no concat de vídeos | Pré-computar combinações comuns; cache por hash de frase. |

## Quando pedir ajuda

- Autorização pra instalar pacotes no `vareni-8` (`apt`, `pip`): necessário.
- PAT do GitHub: necessário antes do `git push`.
- Número de WhatsApp dedicado (chip/second-line): necessário pra parear.
- Confirmação antes de cada deploy/produção.

## Status atual

- Repo local inicializado em `/opt/vlibras` no `vareni-8`.
- Scaffold local em `~/Documents/projetos/libras`.
- Próximo passo: **você cria o repo `MarxSteel/vlibras` no GitHub e me passa um PAT**.
