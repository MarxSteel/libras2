// lib/skeleton-utils.js
// Helpers para converter gestos Libras (keyframes) em AnimationClip + Mixer.
// Reusa o pipeline do BVH retarget (retargetClip) para garantir animação correta.

import * as THREE from 'three';

/**
 * Captura a quaternion de rest pose de cada bone (T-pose).
 */
export function captureRestPose(skinnedMesh) {
  const map = new Map();
  for (const bone of skinnedMesh.skeleton.bones) {
    map.set(bone.name, bone.quaternion.clone());
  }
  return map;
}

/**
 * Converte um gesture (keyframes por bone) em um AnimationClip
 * com tracks QuaternionsKeyframe. Cada keyframe vira 1 sample no tempo.
 *
 * @param {Object} gesture - { duration, bones: { boneName: [{t, euler}, ...] } }
 * @param {string} [name]
 * @returns {THREE.AnimationClip}
 */
export function gestureToClip(gesture, name = 'gesture') {
  const tracks = [];
  const _q = new THREE.Quaternion();
  const _e = new THREE.Euler();
  for (const [boneName, keyframes] of Object.entries(gesture.bones)) {
    const times = [];
    const quatValues = [];
    for (const kf of keyframes) {
      const t = kf.t * gesture.duration;
      _e.set(kf.euler[0], kf.euler[1], kf.euler[2], 'XYZ');
      _q.setFromEuler(_e);
      times.push(t);
      quatValues.push(_q.x, _q.y, _q.z, _q.w);
    }
    // position track (0,0,0) — não muda
    tracks.push(new THREE.VectorKeyframeTrack(
      `${boneName}.position`,
      [0],
      [0, 0, 0]
    ));
    tracks.push(new THREE.QuaternionKeyframeTrack(
      `${boneName}.quaternion`,
      times,
      quatValues
    ));
  }
  return new THREE.AnimationClip(name, gesture.duration, tracks);
}

/**
 * Reseta o skeleton para rest pose.
 */
export function resetSkeleton(skinnedMesh, restPose) {
  for (const bone of skinnedMesh.skeleton.bones) {
    const rest = restPose.get(bone.name);
    if (rest) {
      bone.quaternion.copy(rest);
      bone.updateMatrix();
    }
  }
  if (skinnedMesh.skeleton) skinnedMesh.skeleton.update();
}
