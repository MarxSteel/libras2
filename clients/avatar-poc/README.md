# Libras2 — Avatar POC (Three.js + BVH + GLB)

Prova de conceito que mostra como criar um avatar 3D humanóide (GLB mixamo-compatible)
e tocar animações BVH (Biovision mocap) no navegador — base técnica para futuras
expansões multi-língua (LSCh, LSA, etc).

## O que tem

- `index.html` (~24KB) — página standalone com:
  - **Three.js r167** (render WebGL)
  - **BVHLoader** (carrega arquivos BVH mocap)
  - **GLTFLoader** (carrega GLB avatares mixamo-compatible)
  - **SkeletonUtils** (retarget BVH→GLB)
  - **OrbitControls** (câmera)
  - **MediaRecorder** (exporta webm)
  - Seletor de avatar (dropdown com GLBs detectados)
  - Caption highlighting por palavra
  - Sequência animada (N palavras → N BVHs retargeted → 1 GLB)
  - Logs em tempo real

- `setup.sh` — baixa dependências (three.js + 3 BVH + 2 GLB) e popula `vendor/`, `bvh/`, `glb/`

## Como rodar

```bash
cd clients/avatar-poc
./setup.sh
# abre http://<host>:8088/clients/avatar-poc/ no browser
```

Selecione o avatar no dropdown, cole uma frase, clique **Tokenizar**, depois **Tocar**.

## Mapeamento BVH (CMU) → Mixamo

O BVH `pirouette.bvh` usa convenção CMU (nomes curtos: `hip`, `rShldr`, `rHand`).
O GLB `Soldier.glb` usa convenção Mixamo (prefixo `mixamorig`: `mixamorigHips`, `mixamorigRightArm`).

O `index.html` tem o mapa `BVH_TO_MIXAMO` com 41 bones renomeados em runtime
antes do `SkeletonUtils.retargetClip`. Veja o mapa completo no source.

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
                          applyBVHToAvatar(bvh):
                            1. clone GLB (SkeletonUtils.clone)
                            2. renameBVHBones(bvh)  ← CMU→Mixamo
                            3. SkeletonUtils.retargetClip(skinnedMesh, bvh.skeleton, bvh.clip)
                            4. AnimationMixer.play(retargetedClip)
                                    ↓
                          renderCaption() destaca palavra ativa
```

Em produção:
- `tokenize()` seria substituído por chamada ao backend LSCh/VLibras (glosa)
- Cada palavra teria seu próprio BVH real (dataset de intérprete filmado)
- Caption viria do DOM, não gerado por Pillow (canvas.toDataURL não pega DOM)

## Limitações

- **BVH de exemplo é dança de bailarina** (`pirouette.bvh`), não sinais de Libras — poses ficam estranhas no Soldier
- **Gloss é split por espaço** (heurística), não usa VLibras/LSCh
- **3 BVHs idênticos** (round-robin), não há dataset real
- **MediaRecorder exporta webm**, não MP4
- **2 GLBs demo** (Soldier humanoide + RobotExpressive robótico)

## Próximos passos

1. **Dataset LSCh real**: contratar intérprete + filmar 200+ sinais + processar via Mixamo/Blender
2. **Backend glosa**: integrar VLibras (PT) + criar stub LSCh (ES→LSCh via dicionário)
3. **Renderer Playwright**: já temos infra (widget renderer), adaptar pra esse HTML
4. **MP4 export real**: usar ffmpeg (igual widget renderer atual) em vez de MediaRecorder

## Ver também

- `../play.html` — widget renderer do VLibras (production)
- `docs/SIGN_AVATAR_POC.md` — pesquisa de bibliotecas/avatares
- `docs/SIGN_AVATAR_POC.md` § "Caminho pra produção" — roadmap multi-língua
