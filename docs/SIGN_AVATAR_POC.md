# Avatar 3D para Libras2 — Pesquisa + POC

**Status:** POC funcional ✅ (commit `75173e2`)
**Data:** 2026-08-11

## TL;DR

Confirmamos que dá pra construir um avatar 3D humanóide e tocar animações
de sinais (Libras, LSCh, qualquer língua) inteiramente em JavaScript/WebGL:

- **Engine**: Three.js r167 (WebGL puro)
- **Formato animação**: BVH (Biovision Hierarchy) — padrão universal de mocap
- **Avatar demo**: skeleton wireframe (SkeletonHelper)
- **Avatar produção**: GLB/VRM (Mixamo-compatible) — substituir depois
- **Player standalone**: `clients/avatar-poc/index.html` (16KB, self-contained)

Live POC: `http://195.200.0.69:8088/clients/avatar-poc/`

---

## Pesquisa — bibliotecas e sistemas

### Stack 1: BVH + Three.js (mais simples, escolhido pro POC)

| Componente | URL | Custo |
|---|---|---|
| **BVH (Biovision)** | formato mocap universal | Free |
| **three.js BVHLoader** | threejs.org/docs/#examples/en/loaders/BVHLoader | Free |
| **BVHImporter** (herzig) | github.com/herzig/BVHImporter | Free |
| **SkeletonUtils.retargetClip** | three.js oficial | Free |
| **MakeHuman + MakeWalk** (Blender) | makehuman.org | Free |
| **threejs.org/examples** | pirouette.bvh, etc. | Free |

**Por que BVH:** formato texto legível, padrão da indústria, suportado por
todos os mocap tools (iPi Soft, MotionAnalysis, Qualisys, etc).

### Stack 2: Mixamo + RPM (mais fácil, FBX)

| Componente | URL | Custo |
|---|---|---|
| **Mixamo (Adobe)** | mixamo.com | Free (requer Adobe ID) |
| **Ready Player Me (RPM)** | readyplayer.me | Free tier |
| **VRM** | vrm.dev / Pixiv | Free spec |

**Por que Mixamo:** 1000+ animações mocap prontas, auto-rigging, FBX output
que qualquer engine consome. **Pronto pra produção** — mais fácil que BVH.

### Stack 3: SMPL-X + MANO (mais moderno, hand pose)

| Componente | URL | Custo |
|---|---|---|
| **SMPL-X** | smpl-x.is.tue.mpg.de | Free p/ research |
| **MANO** | mano.is.tue.mpg.de | Free p/ research |
| **SignAvatars** (ECCV 2024) | github.com/ZhengdiYu/SignAvatars | 8.34M frames |
| **three.ws** | three.ws/sign-language | ASL fingerspell, export GLB |

**Por que SMPL-X:** modelo paramétrico corpo+face+mãos (158 joints), ideal
pra Libras (sinais dependem muito de mãos). SignAvatars tem 70K sequences
com MANO hand annotations.

### Sistemas prontos

| Sistema | Lingua | Engine | Notas |
|---|---|---|---|
| **three.ws Sign Language** | ASL | Three.js próprio | Comercial, fingerspell |
| **SignAvatars** (ZhengdiYu) | multi | SMPL-X + MANO | Research, ECCV 2024 |
| **SignAvatar** (arXiv 2024) | multi | motion recon | github |
| **GenASL** (AWS) | ASL | RTMPose + PyTorch | AWS Blog |
| **SignKit** | ISL (Índia) | Three.js + MERN | Open source |

---

## POC — `clients/avatar-poc/`

### O que tem

- `index.html` (16KB) — standalone HTML
  - Three.js r167 via vendor local (não CDN)
  - BVHLoader + SkeletonHelper
  - Sequência: frase → gloss → N BVHs
  - Caption highlight por palavra ativa
  - MediaRecorder exporta webm
  - Logs em tempo real
- `setup.sh` — baixa three.js + 1 BVH sample (`pirouette.bvh`, 50KB)
- `README.md` — instruções de uso
- `vendor/three/` — three.js + loaders (gitignored, ~1.3MB)
- `bvh/` — BVH samples (gitignored)

### Como rodar

```bash
cd clients/avatar-poc
./setup.sh
# abre http://<host>:8088/clients/avatar-poc/ no browser
# frase "olá amigo bom dia" → 4 palavras → 4 BVH tocados em sequência
```

### O que o POC prova

1. **Pipeline JS→BVH→3D é viável** em 16KB de código + 1.3MB de deps
2. **Sequência animada** funciona: tokeniza, mapeia palavra→BVH, toca, destaca caption
3. **Skeleton wireframe** renderiza em swiftshader (sem GPU) a 30fps
4. **MediaRecorder** captura canvas + exporta webm (alternativa leve ao ffmpeg)
5. **Caption overlay** funciona via DOM (não precisa de Pillow como no VLibras)

### O que o POC NÃO tem (próximos passos)

- Avatar humanóide realista (atualmente só wireframe)
- BVH real de sinais Libras/LSCh (atualmente é dança de bailarina)
- Gloss de verdade (atualmente split por espaço)
- Mãos articuladas (BVH padrão não tem mão detalhada)
- MP4 export via ffmpeg (MediaRecorder só dá webm)
- Sync de caption com timing real do sinal (timing atual é heurístico)

---

## Caminho pra produção (multi-língua)

### MVP técnico em 1 sprint (2-3 semanas)

1. **Avatar base** (1 dia)
   - Baixar VRM open source (Pixiv sample) ou usar RPM
   - Confirmar skeleton Mixamo-compatible
   - Renderizar com `THREE.GLTFLoader` + `VRMLoader`

2. **Renderer final** (1 dia)
   - Trocar SkeletonHelper por GLB/VRM real
   - Manter a lógica de sequência + caption
   - Adicionar ffmpeg export (já temos infra server-side)

3. **Backend gloss** (1-2 dias)
   - Manter VLibras (PT) como `vlibras` backend
   - Criar stub `lsch` backend (dicionário ES→LSCh)
   - Adicionar campo `language` no request

4. **Dataset LSCh** (longo prazo)
   - Gravar 100-200 sinais LSCh com intérprete (glove sensor ou câmera)
   - Processar via Mixamo ou Blender (retarget pra skeleton padrão)
   - Exportar BVH/FBX por sinal
   - Hospedar no Libras2 (`/data/lsch/bvh/<word>.bvh`)

5. **Testes E2E** (2 dias)
   - Frases reais (glosa LSCh) → sequência BVHs → MP4
   - Validar timing + caption sync

### Pré-requisitos que ainda faltam

- ❌ Dataset LSCh em BVH/FBX (precisa de intérprete filmado — 1-2 meses de gravação)
- ❌ Glosa ES→LSCh automática (precisa modelo NLP ou dicionário expandido)
- ❌ Avatar 3D Mixamo-compatible pronto (RPM resolve em 1 dia)
- ✅ Engine Three.js + BVHLoader (já temos)
- ✅ Pipeline de captura Playwright (já temos)
- ✅ Infra de servidor + cache (já temos)

---

## Arquitetura proposta (multi-língua)

```
libras2/                      ← renomear futuramente pra sign2/
├── backends/
│   ├── vlibras.py            ← 🇧🇷 BR (já funciona)
│   ├── lsch.py               ← 🇨🇱 CL (stub → dataset real)
│   ├── lsa.py                ← 🇦🇷 AR (futuro)
│   └── lsperu.py             ← 🇵🇪 PE (futuro)
├── renderer/
│   ├── widget_vlibras.py     ← VLibras widget + Playwright (já funciona)
│   ├── avatar_poc.py         ← Three.js BVH (POC)
│   └── avatar_glb.py         ← Avatar GLB/VRM (futuro)
├── data/
│   ├── vlibrasil/            ← dataset BR
│   ├── lsch/bvh/             ← dataset CL
│   └── ...
└── api/
    ├── main.py               ← FastAPI
    └── translate.py          ← POST /translate (seleciona backend)
```

**API contract (proposta):**
```http
POST /translate
{
  "text": "olá amigo",
  "language": "pt-BR" | "es-CL" | "es-AR",
  "output": "video" | "gloss" | "skeleton"
}
```

---

## Ver também

- `clients/play.html` — VLibras widget renderer (production)
- `clients/avatar-poc/index.html` — POC avatar BVH (NEW)
- `docs/API.md` — REST API reference
- `docs/PLAN.md` — roadmap completo
- [BVH format spec](https://research.cs.wisc.edu/graphics/Courses/cs-838-1999/Jeff/BVH.html)
- [three.js BVHLoader docs](https://threejs.org/docs/#examples/en/loaders/BVHLoader)
- [SignAvatars paper (ECCV 2024)](https://signavatars.github.io/)
