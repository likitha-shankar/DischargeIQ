/**
 * File: frontend/explainer/engine/src/animations/inflammation_highlight.js
 * Component: Anatomy Explainer — Procedural Animation
 * Description: Applies a pulsing warm emissive highlight to target meshes to draw
 *   attention to an inflamed or affected region (e.g. pancreas in diabetes, lung
 *   parenchyma in COPD). The emissive oscillates between the mesh's resting state
 *   and a warm orange-red at 0.8 Hz, creating a visible but non-alarming glow.
 *
 *   Restores all original emissive values on stop(). Safe to run alongside
 *   the highlight system — the highlight system also uses emissive, so the two
 *   should not be active on the same mesh simultaneously (the highlight wins).
 *
 * Dependencies: three
 * Consumed by: src/animations/index.js
 */

import * as THREE from 'three';

/** Oscillation frequency in Hz. 0.8 Hz = one pulse per 1.25 seconds. */
const FREQUENCY_HZ = 0.8;

/** Angular frequency. */
const OMEGA = 2 * Math.PI * FREQUENCY_HZ;

/** Peak emissive colour: warm orange-red (inflammation hue). */
const PEAK_EMISSIVE = new THREE.Color(0xc85020);

/** Peak emissive intensity multiplier. */
const PEAK_INTENSITY = 0.6;

class InflammationHighlightAnimation {
  /**
   * Construct the animation.
   *
   * @param {THREE.Scene} scene - The active THREE.js scene.
   * @param {THREE.Mesh[]} targetMeshes - Meshes to highlight. Falls back to
   *   the placeholder sphere so the animation is visible pre-model.
   */
  constructor(scene, targetMeshes) {
    this._scene = scene;
    this._targetMeshes = targetMeshes;
    this._isPlaying = false;
    this._time = 0;
    this._originalEmissives = new Map();
    this._originalIntensities = new Map();
    this._activeMeshes = [];
  }

  /**
   * Resolve active meshes, falling back to the placeholder.
   *
   * @returns {THREE.Mesh[]}
   */
  _resolveMeshes() {
    if (this._targetMeshes.length > 0) return this._targetMeshes;
    const ph = this._scene.getObjectByName('__placeholder');
    return ph ? [ph] : [];
  }

  /**
   * Save original emissive state for each mesh before first play.
   *
   * @param {THREE.Mesh[]} meshes
   * @returns {void}
   */
  _saveOriginals(meshes) {
    for (const mesh of meshes) {
      if (mesh.material?.emissive && !this._originalEmissives.has(mesh.uuid)) {
        this._originalEmissives.set(mesh.uuid, mesh.material.emissive.clone());
        this._originalIntensities.set(mesh.uuid, mesh.material.emissiveIntensity ?? 1);
      }
    }
  }

  /**
   * Start the pulsing highlight animation.
   *
   * @returns {void}
   */
  play() {
    this._activeMeshes = this._resolveMeshes();
    this._saveOriginals(this._activeMeshes);
    this._time = 0;
    this._isPlaying = true;
  }

  /**
   * Pause the animation at its current emissive level.
   *
   * @returns {void}
   */
  pause() {
    this._isPlaying = false;
  }

  /**
   * Stop and restore all meshes to their original emissive state.
   *
   * @returns {void}
   */
  stop() {
    this._isPlaying = false;
    for (const mesh of this._activeMeshes) {
      const origEmissive = this._originalEmissives.get(mesh.uuid);
      if (origEmissive && mesh.material?.emissive) {
        mesh.material.emissive.copy(origEmissive);
      }
      const origIntensity = this._originalIntensities.get(mesh.uuid);
      if (origIntensity !== undefined && mesh.material) {
        mesh.material.emissiveIntensity = origIntensity;
      }
    }
    this._time = 0;
  }

  /**
   * Advance the animation by one frame.
   *
   * Emissive fraction oscillates 0 → 1 → 0 using (sin(ωt) + 1) / 2 so the
   * mesh is at rest half the time and glowing half the time. This matches
   * the expected visual: a slow, breathing glow rather than a harsh flash.
   *
   * @param {number} delta - Elapsed seconds since last frame.
   * @returns {void}
   */
  update(delta) {
    if (!this._isPlaying) return;
    this._time += delta;
    const fraction = (Math.sin(OMEGA * this._time) + 1) / 2;
    const intensity = fraction * PEAK_INTENSITY;

    for (const mesh of this._activeMeshes) {
      if (!mesh.material?.emissive) continue;
      mesh.material.emissive.copy(PEAK_EMISSIVE).multiplyScalar(fraction);
      mesh.material.emissiveIntensity = intensity;
    }
  }

  /** @returns {boolean} */
  get isPlaying() { return this._isPlaying; }
}

export { InflammationHighlightAnimation };
