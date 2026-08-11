# Libras2 — Avatar POC (Three.js + BVH + GLB + Gestos Libras)

Prova de conceito que mostra como criar um avatar 3D humanóide (GLB mixamo-compatible)
e animá-lo de duas formas no navegador:

1. **Gestos de Libras em keyframes** (`lib/gestures.js`) — OLA, OBRIGADO, SIM,
   NAO, BOM DIA, TCHAU, EU, VOCE, AMIGO, POR FAVOR. Aplica diretamente no
   skeleton Mixamo via `lib/skeleton-utils.js`. Suporta compostos (BOM DIA
   → 1 gesto único).
2. **BVH retarget** (`SkeletonUtils.retargetClip`) — fallback para palavras
   sem gesto ou modo "Dança". Usa mapa BVH→Mixamo (41 bones).

Base técnica para futuras expansões multi-língua (LSCh, LSA, etc).

## O que tem

- `index.html` (~28KB) — página standalone com:
  - **Three.js r167** (render WebGL)
  - **BVHLoader** (carrega arquivos BVH mocap)
  - **GLTFLoader** (carrega GLB avatares mixamo-compatible)
  - **SkeletonUtils** (retarget BVH→GLB)
  - **OrbitControls** (câmera)
  - **MediaRecorder** (exporta webm)
  - 3 modos: **Sinais** (keyframe Libras), **Misto**, **Dança** (BVH)
  - 8 gestos de Libras pré-mapeados
  - Caption highlighting por palavra
  - Sequência animada (N palavras → N gestos/BVHs → 1 GLB)
  - Logs em tempo real

- `lib/gestures.js` (11KB) — biblioteca de gestos Libras (keyframes por bone)
- `lib/skeleton-utils.js` (3KB) — `captureRestPose`, `applyGestureFrame`
- `setup.sh` — baixa dependências (three.js + 3 BVH + 2 GLB) e popula `vendor/`, `bvh/`, `glb/`

## Como rodar

```bash
cd clients/avatar-poc
./setup.sh
# abre http://<host>:8088/clients/avatar-poc/ no browser
```

Selecione o avatar no dropdown, escolha o modo (Sinais é o default), cole uma
frase, clique **Tocar**.

## Gestos disponíveis (v3)

| Palavra | Movimento |
|---------|-----------|
| OLA / OI | palma aberta, balança lateral na altura do ombro |
| OBRIGADO / OBRIGADA | mão no queixo, vai pra frente em arco |
| SIM | cabeça acenando |
| NAO | mão fechada balança lateral no peito |
| BOM DIA / BOM / DIA | mão na testa, vai pra frente |
| TCHAU | mão aberta acena, palma pra frente |
| EU | indicador aponta pro próprio peito |
| VOCE / TU | indicador aponta pra frente |
| AMIGO / AMIGA | braços se cruzam na frente |
| POR FAVOR / FAVOR | mão no peito, movimento circular |

Suporta compostos: `BOM DIA` → 1 gesto (consome 2 palavras).

## Mapeamento BVH (CMU) → Mixamo

O BVH `pirouette.bvh` usa convenção CMU (nomes curtos: `hip`, `rShldr`, `rHand`).
O GLB `Soldier.glb` usa convenção Mixamo (prefixo `mixamorig`: `mixamorigHips`, `mixamorigRightArm`).

O `index.html` tem o mapa `BVH_TO_MIXAMO` com 41 bones renomeados em runtime
antes do `SkeletonUtils.retargetClip`. Veja o mapa completo no source.

## Arquitetura

```
frase em PT  →  tokenize()  →  [word1, word2, word3]
                                    ↓
                          buildSequence():
                            - lookupGesture()  ← lib/gestures.js
                            - se tem gesto: usa keyframes
                            - senão: fallback BVH
                                    ↓
                          nextInSequence() toca um por vez
                                    ↓
                          applyGestureToAvatar(gesture):
                            1. clone GLB (SkeletonUtils.clone)
                            2. restPose = captureRestPose(skinnedMesh)
                            3. currentGesture = { gesture, t0 }
                                    ↓
                          tick():
                            - applyGestureFrame(skinnedMesh, restPose, gesture, t01)
                            - bone.quaternion = rest * gesture
                                    ↓
                          renderCaption() destaca palavra ativa
```

## Limitações

- **Sem dedos articulados**: Soldier.glb tem mãos genéricas. Sinais que
  dependem de configuração de dedos (letras A-Z, "EU TE AMO") ficam
  aproximados. Pra Libras de verdade, trocar por modelo Mixamo com rig de
  dedos (Y Bot, Michelle).
- **8 gestos hardcoded**: cobrem cumprimentos + pronomes + gentilezas.
  Frases completas exigem muito mais gestos (alfabeto, números, verbos).
- **BVH de exemplo é dança**, não Libras — modo "Dança" é só demo.
- **MediaRecorder exporta webm**, não MP4.

## Próximos passos

1. **Modelo com dedos**: Mixamo Y Bot ou Michelle (skeleton com dedos)
2. **Dataset LSCh real**: contratar intérprete + filmar 200+ sinais + Mixamo retarget
3. **Mais gestos**: alfabeto manual (A-Z), números (0-9), verbos essenciais
4. **MP4 export real**: Playwright + ffmpeg (igual widget renderer)
5. **Glosa real**: integrar VLibras (PT) + stub LSCh (ES→LSCh via dicionário)

## Ver também

- `../play.html` — widget renderer do VLibras (production)
- `docs/SIGN_AVATAR_POC.md` — pesquisa de bibliotecas/avatares
