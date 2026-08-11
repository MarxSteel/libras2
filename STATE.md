# Libras2 — Estado da Migração (snapshot pra próxima sessão)

**Última atualização:** 2026-08-11 19:48

## ✅ TUDO FUNCIONANDO

| Componente | Máquina | Status | Evidência |
|---|---|---|---|
| Libras2 v0.3.1 (11 endpoints) | 72.62.9.238 | ✅ production | systemctl active, /health=200 |
| Avatar 3D Ícaro (widget renderer) | 72.62.9.238 | ✅ | MP4 2MB, 13.5s, com legenda animada |
| fastapi-mcp (3 tools) | 72.62.9.238 | ✅ | tools/list: glosa, translate, get_sign_info |
| Picoclaw 0.3.1 + WhatsApp-native | 72.62.9.238 | ✅ instalado | 108MB binário com whatsmeow |
| Picoclaw MCP conexão | 72.62.9.238 | ✅ | 3 tools listadas |
| MiMo (Xiaomi) LLM | 72.62.9.238 | ✅ configurado | model `mimo-v2.5` OpenAI-compat |
| **Telegram bot** | 72.62.9.238 | ✅ **ATIVO** | @IubiLibras_bot (id 8668529197) |
| Telegram channel | 72.62.9.238 | ✅ habilitado | polling user_id 143067669 |
| WhatsApp channel | 72.62.9.238 | ⏸ pausado (user pediu pra depois) | binário pronto, whatsmeow atualizado |
| **Avatar POC humanóide** | vareni-8 | ✅ gestos Libras | Soldier faz OLA, OBRIGADO, BOM DIA, etc |
| **Avatar POC BVH retarget** | vareni-8 | ✅ | pirouette.bvh → Soldier Mixamo (39 tracks) |

## Avatar POC — POC v3 (commit `a62ac8a`)

**O que tem:**
- `index.html` (28KB): cena Three.js, GLBs Mixamo (Soldier 49 bones + RobotExpressive), BVH retarget, gestos Libras
- `lib/gestures.js` (11KB): 8 gestos + 24 aliases
  - OLA, OBRIGADO, SIM, NAO, BOM DIA, TCHAU, EU, VOCE, AMIGO, POR FAVOR
  - Compostos: `BOM DIA` → 1 gesto (consome 2 palavras)
  - Normalização: lowercase + sem acento + _ no lugar de espaço
- `lib/skeleton-utils.js` (2KB): `captureRestPose`, `gestureToClip` (keyframes → AnimationClip)
- `setup.sh`: baixa Three.js + 3 BVH + 2 GLB
- 3 modos: **Sinais** (keyframe Libras, default), **Misto** (gesto + BVH fallback), **Dança** (BVH round-robin)

**Pipeline:**
```
frase PT → tokenize() → [word1, word2, ...]
  → buildSequence(): lookupGesture() → [gesto, gesto, BVH, ...]
  → nextInSequence(): applyGestureToAvatar() (clearAvatar + clone + retargetClip + mixer)
  → tick(): mixer.update(dt) + render
  → caption: palavra ativa destacada em azul
```

**Limitação crítica:** Mixamo Soldier NÃO tem dedos articulados. Sinais
que dependem de configuração de dedos (letras A-Z, "EU TE AMO") ficam
aproximados. Para Libras de verdade, trocar por modelo com rig de dedos
(Mixamo Y Bot ou Michelle).

**Para testar:**
- http://195.200.0.69:8088/clients/avatar-poc/
- Digite: "olá obrigado bom dia" → Soldier faz 3 gestos
- Modo "Dança" → BVH round-robin (mesma animação, palavra diferente)

## Credenciais configuradas (no 72.62.9.238)

`/home/libras/.picoclaw/env` (chmod 600):
- `MIMO_API_KEY=tp-s0yzieuaox1gxj732oee0kso6edrn159vusd4htill7hgkdb`
- `PICOCLAW_CHANNELS_TELEGRAM_TOKEN=8668529197:AAED6rrYHg1ucmSe5H9aFGibyCBefTPJSeA`
- `PICOCLAW_CHANNELS_TELEGRAM_ALLOWED_USERS=143067669`

## Máquinas

- **vareni-8** (195.200.0.69): produção backup, Libras2 v0.3.1 + Avatar POC.
  - Avatar POC em `http://195.200.0.69:8088/clients/avatar-poc/`
  - SSH via root (chave)
- **72.62.9.238** (srv1186168): produção principal, stack completa.
  - SSH: `sshpass -f /tmp/pw.txt ssh root@72.62.9.238` (⚠️ intermitente)
  - ufw: 22, 81, 443, 8088, 18790 abertos
  - swap: 2GB
  - user `libras` (uid 1000, gid 1001)

## Como testar agora (Telegram)

1. Abre Telegram → procura **@IubiLibras_bot**
2. Manda `/start` → bot responde
3. Manda qualquer frase em PT (ex: "bom dia meu nome é Marx")
4. Bot chama LLM MiMo → tool `translate` do Libras2 → recebe MP4 → envia de volta

## Como ativar WhatsApp (depois)

```bash
sshpass -f /tmp/pw.txt ssh root@72.62.9.238 'bash -s' <<'EOF'
cd /opt/picoclaw-src
export PATH=/usr/local/go/bin:$PATH
go build -tags goolm,stdjson,whatsapp_native -o /usr/local/bin/picoclaw ./cmd/picoclaw
python3 -c "
import json
c = json.load(open('/home/libras/.picoclaw/config.json'))
c['channel_list']['whatsapp']['enabled'] = True
c['channel_list']['whatsapp']['type'] = 'whatsapp_native'
c['channel_list']['whatsapp']['settings']['use_native'] = True
c['channel_list']['whatsapp']['settings']['session_store_path'] = '/home/libras/.picoclaw/workspace/whatsapp'
json.dump(c, open('/home/libras/.picoclaw/config.json', 'w'), indent=2, ensure_ascii=False)
"
systemctl restart picoclaw.service
# QR vai aparecer em journalctl -u picoclaw.service -f
EOF
```

## Decisões técnicas

- **fastapi-mcp 0.4.0** + **mcp 1.12.4** (mcp 2.0 quebra Server.__init__)
- **operation_id explícito** em cada rota que vira tool
- **chromium-headless-shell** + swiftshader (sem GPU)
- **mp4 via libx264**, gif via palettegen
- **whatsmeow v0.0.0-20260810** (atualizado, build OK)
- **whatsapp type="whatsapp_native"** (não "whatsapp" — esse usa bridge)
- **MiMo via custom_headers.api-key** (além de api_keys[0])
- **Telegram via env var** PICOCLAW_CHANNELS_TELEGRAM_TOKEN (SecureString)
- **Avatar gesture → clip → retargetClip** (não direto via keyframe manual;
  retargetClip faz o setup de hierarquia + skeleton que o mixer espera)
- **Mixamo Hips tem rotação 180°Y built-in** (capturado no rest pose)

## Arquivos críticos

- **service/src/service/main.py**: rotas + MCP mount (operation_id explícito)
- **service/src/service/renderer_widget.py**: Playwright + caption
- **clients/play.html**: player HTML do widget oficial
- **clients/avatar-poc/index.html**: cena + gestos + BVH + caption
- **clients/avatar-poc/lib/gestures.js**: 8 gestos Libras
- **clients/avatar-poc/lib/skeleton-utils.js**: captureRestPose + gestureToClip
- **/etc/systemd/system/libras2.service**: MemoryMax=2.5G
- **/etc/systemd/system/picoclaw.service**: MemoryMax=256M, env file com creds
- **/home/libras/.picoclaw/config.json**: model MiMo + channel telegram habilitado
- **/opt/picoclaw-src/**: source code Picoclaw v0.3.1 + whatsmeow atualizado

## GitHub

- **Repo**: https://github.com/MarxSteel/libras2
- **Commits recentes**:
  - `a62ac8a` feat(avatar-poc): gestos Libras reais via keyframes + retargetClip
  - `28c9c46` feat(avatar-poc): Soldier + RobotExpressive GLBs com Mixamo retarget
  - `26bf26a` fix(clients): serve index.html quando path é diretório
  - `ec980eb` docs(SIGN_AVATAR_POC): pesquisa + POC de avatar BVH/Three.js
  - `75173e2` feat(avatar-poc): standalone Three.js + BVH player
  - `7a4a915` fix(widget): detecta fim de animacao e gera legenda via Pillow
  - `81e5922` feat(libras2): add fastapi-mcp server with 3 tools

## Pendente

- [ ] Testar bot Telegram end-to-end com frase real
- [ ] Implementar allow_from restrito (security warning atual)
- [ ] Ativar WhatsApp (quando user quiser)
- [ ] Avatar POC: modelo com dedos articulados (Y Bot/Michelle)
- [ ] Avatar POC: mais gestos (alfabeto A-Z, números 0-9)
- [ ] Avatar POC: MP4 export via Playwright + ffmpeg
- [ ] LSCh (Lengua de Señas Chilena): dataset + retarget (multi-língua)
