# Libras2 — Avatar POC (Three.js + BVH)

Prova de conceito que mostra como criar um avatar 3D humanóide e tocar
animações BVH (Biovision Hierarchy) no navegador — base técnica para
futuras expansões multi-língua (LSCh, LSA, etc).

## O que tem aqui

- `index.html` (~16KB) — página standalone com:
  - **Three.js r167** (render WebGL)
  - **BVHLoader** (carrega arquivos BVH mocap)
  - **OrbitControls** (câmera)
  - **MediaRecorder** (exporta MP4/webm)
  - Skeleton com `SkeletonHelper` (avatar wireframe)
  - Caption highlighting por palavra
  - Sequência animada (N palavras → N BVHs tocadas em ordem)
  - Logs em tempo real

- `setup.sh` — baixa dependências (three.js + BVH samples) e popula `vendor/` e `bvh/`

## Como rodar

```bash
cd clients/avatar-poc
./setup.sh                                    # baixa 1.3MB
# abra http://<host>:8088/clients/avatar-poc/ no browser
```

Cole uma frase, clique **Tokenizar**, depois **Tocar**.

## Arquitetura

```
frase em PT  →  tokenize()  →  [word1, word2, word3]
                                    ↓
                          buildSequence() mapeia cada palavra → BVH
                                    ↓
                          ensureSequence() carrega BVHs (cache)
                                    ↓
                          nextInSequence() toca um por vez
                                    ↓
                          applyBVH() + AnimationMixer.play()
                                    ↓
                          renderCaption() destaca palavra ativa
```

Em produção:
- `tokenize()` seria substituído por chamada ao backend LSCh/VLibras (glosa)
- Cada palavra teria seu próprio BVH (dataset de intérprete filmado)
- Skeleton wireframe seria substituído por avatar GLB/VRM
- Caption viria do DOM, não gerado por Pillow (canvas.toDataURL não pega DOM)

## Limitações

- **Avatar é wireframe** (esqueleto com linhas), não humanóide realista
- **BVH de exemplo é dança de bailarina** (`pirouette.bvh`), não sinais de Libras
- **Gloss é split por espaço** (heurística), não usa VLibras/LSCh
- **3 BVHs idênticos** (round-robin), não há dataset real
- **MediaRecorder exporta webm**, não MP4 (codec vp9)

## Próximos passos

1. **Avatar GLB/VRM**: usar RPM ou VRM sample (esqueleto humanóide completo com mãos)
2. **Dataset LSCh real**: contratar intérprete + filmar 200+ sinais + processar via Mixamo/Blender
3. **Backend glosa**: integrar VLibras (PT) + criar stub LSCh (ES→LSCh via dicionário)
4. **Renderer Playwright**: já temos infra (widget renderer), adaptar pra esse HTML
5. **MP4 export real**: usar ffmpeg (igual widget renderer atual) em vez de MediaRecorder

## Ver também

- `../play.html` — widget renderer do VLibras (production)
- `docs/SIGN_AVATAR_RESEARCH.md` — pesquisa de bibliotecas/avatares
