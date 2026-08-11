#!/bin/bash
# Setup do POC: baixa three.js + BVH samples
# Uso: ./setup.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENDOR="$DIR/vendor/three"
BVH="$DIR/bvh"
THREE_VERSION="${THREE_VERSION:-0.167.0}"

echo "[setup] baixando three.js v$THREE_VERSION para $VENDOR"
mkdir -p "$VENDOR/build" "$VENDOR/examples/jsm/controls" "$VENDOR/examples/jsm/loaders" "$VENDOR/examples/jsm/utils" "$BVH"

BASE="https://unpkg.com/three@$THREE_VERSION"

curl -sL "$BASE/build/three.module.js" -o "$VENDOR/build/three.module.js"
curl -sL "$BASE/examples/jsm/controls/OrbitControls.js" -o "$VENDOR/examples/jsm/controls/OrbitControls.js"
curl -sL "$BASE/examples/jsm/loaders/BVHLoader.js" -o "$VENDOR/examples/jsm/loaders/BVHLoader.js"
curl -sL "$BASE/examples/jsm/loaders/GLTFLoader.js" -o "$VENDOR/examples/jsm/loaders/GLTFLoader.js"
curl -sL "$BASE/examples/jsm/utils/BufferGeometryUtils.js" -o "$VENDOR/examples/jsm/utils/BufferGeometryUtils.js"

echo "[setup] baixando BVH samples para $BVH"
# pirouette.bvh do three.js examples (BVH de bailarina, ~50KB, domínio público)
curl -sL "https://threejs.org/examples/models/bvh/pirouette.bvh" -o "$BVH/pirouette.bvh"
# 2 cópias para o round-robin (em prod, cada palavra teria seu próprio BVH)
cp "$BVH/pirouette.bvh" "$BVH/dance1.bvh"
cp "$BVH/pirouette.bvh" "$BVH/dance2.bvh"

echo "[setup] OK"
echo "  - abra http://localhost:8088/clients/avatar-poc/ no navegador"
echo "  - cole uma frase, clique Tokenizar, depois Tocar"
