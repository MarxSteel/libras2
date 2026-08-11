#!/bin/bash
# Setup do POC: baixa three.js + BVH samples + GLB avatares
# Uso: ./setup.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENDOR="$DIR/vendor/three"
BVH="$DIR/bvh"
GLB="$DIR/glb"
THREE_VERSION="${THREE_VERSION:-0.167.0}"

echo "[setup] baixando three.js v$THREE_VERSION para $VENDOR"
mkdir -p "$VENDOR/build" "$VENDOR/examples/jsm/controls" "$VENDOR/examples/jsm/loaders" "$VENDOR/examples/jsm/utils" "$BVH" "$GLB" "$DIR/lib"

BASE="https://unpkg.com/three@$THREE_VERSION"
GH_BASE="https://raw.githubusercontent.com/mrdoob/three.js/r167/examples/jsm"

curl -sL "$BASE/build/three.module.js" -o "$VENDOR/build/three.module.js"
curl -sL "$BASE/examples/jsm/controls/OrbitControls.js" -o "$VENDOR/examples/jsm/controls/OrbitControls.js"
curl -sL "$BASE/examples/jsm/loaders/BVHLoader.js" -o "$VENDOR/examples/jsm/loaders/BVHLoader.js"
curl -sL "$BASE/examples/jsm/loaders/GLTFLoader.js" -o "$VENDOR/examples/jsm/loaders/GLTFLoader.js"
curl -sL "$BASE/examples/jsm/utils/BufferGeometryUtils.js" -o "$VENDOR/examples/jsm/utils/BufferGeometryUtils.js"
curl -sL "$GH_BASE/utils/SkeletonUtils.js" -o "$VENDOR/examples/jsm/utils/SkeletonUtils.js"

echo "[setup] baixando BVH samples para $BVH"
# pirouette.bvh (BVH de bailarina, ~50KB, domínio público) do three.js examples
curl -sL "https://threejs.org/examples/models/bvh/pirouette.bvh" -o "$BVH/pirouette.bvh"
# 2 cópias para o round-robin (em prod, cada palavra teria seu próprio BVH)
cp "$BVH/pirouette.bvh" "$BVH/dance1.bvh"
cp "$BVH/pirouette.bvh" "$BVH/dance2.bvh"

echo "[setup] baixando GLB avatares para $GLB"
# Soldier.glb (mixamo-compatible, 2.1MB) - humanóide low-poly do three.js
curl -sL "https://threejs.org/examples/models/gltf/Soldier.glb" -o "$GLB/Soldier.glb"
# RobotExpressive.glb (mixamo-compatible, 464KB) - robô estilizado
curl -sL "https://threejs.org/examples/models/gltf/RobotExpressive/RobotExpressive.glb" -o "$GLB/RobotExpressive.glb"

echo "[setup] OK"
echo "  - vendor/three/   : $(du -sh $VENDOR | cut -f1)  (three.js + loaders + SkeletonUtils)"
echo "  - bvh/            : $(du -sh $BVH | cut -f1)  (3 BVH samples)"
echo "  - glb/            : $(du -sh $GLB | cut -f1)  (2 GLB avatares mixamo-compatible)"
echo "  - lib/            : gestures.js + skeleton-utils.js (keyframes Libras)"
echo "  - abra http://localhost:8088/clients/avatar-poc/ no navegador"
echo "  - modos: Sinais (Libras keyframes) | Misto | Dança (BVH)"
echo "  - gestos disponíveis: olá, obrigado, sim, não, bom, dia, tchau, eu, você, amigo, por, favor"
