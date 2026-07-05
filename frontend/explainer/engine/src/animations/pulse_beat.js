/**
 * File: frontend/explainer/engine/src/animations/pulse_beat.js
 * Component: Anatomy Explainer - Procedural Animation
 * Description: Applies a gentle, rhythmic scale pulse to target meshes simulating
 *   a heartbeat. Scale oscillates between (1 - amplitude) and (1 + amplitude) at
 *   a BPM-derived frequency using a sine wave driven by accumulated time.
 *
 *   Saves and restores original mesh scales so the animation leaves no permanent
 *   state changes when stopped. Works on the placeholder sphere so the lighting
 *   pipeline can be verified with motion before real models are sourced.
 *
 * Dependencies: three
 * Consumed by: src/animations/index.js
 */

import * as THREE from 'three';

/** Scale deviation from 1.0 at peak (±5%). */
const AMPLITUDE = 0.05;

/** Beats per minute. 72 BPM = 1.2 Hz. */
const BPM = 72;

/** Angular frequency derived from BPM: ω = 2π × (BPM/60) rad/s. */
const OMEGA = (2 * Math.PI * BPM) / 60;

class PulseBeatAnimation {
  /**
   * Construct the animation. Records the original scale of each target mesh so
   * stop() can restore them accurately.
   *
   * @param {THREE.Scene} scene - The active THREE.js scene (unused directly, but
   *   kept for interface consistency with other animations).
   * @param {THREE.Mesh[]} targetMeshes - Meshes to pulse. Falls back to searching
   *   the scene for the placeholder sphere when the array is empty.
   */
  constructor(scene, targetMeshes) {
    this._scene = scene;
    this._targetMeshes = targetMeshes;
    this._isPlaying = false;
    this._time = 0;
    this._originalScales = new Map();
  }

  /**
   * Resolve the mesh list, falling back to the placeholder when targets are empty.
   *
   * Stores original scales before first play so stop() can restore them.
   *
   * @returns {THREE.Mesh[]}
   */
  _resolveMeshes() {
    if (this._targetMeshes.length > 0) return this._targetMeshes;
    const placeholder = this._scene.getObjectByName('__placeholder');
    return placeholder ? [placeholder] : [];
  }

  /**
   * Start the pulse animation. Resets time so pulse always starts from rest.
   *
   * @returns {void}
   */
  play() {
    const meshes = this._resolveMeshes();
    for (const mesh of meshes) {
      if (!this._originalScales.has(mesh.uuid)) {
        this._originalScales.set(mesh.uuid, mesh.scale.clone());
      }
    }
    this._activeMeshes = meshes;
    this._time = 0;
    this._isPlaying = true;
  }

  /**
   * Pause the animation. Mesh scales are left at their current pulsed value.
   *
   * @returns {void}
   */
  pause() {
    this._isPlaying = false;
  }

  /**
   * Stop the animation and restore every mesh to its original scale.
   *
   * @returns {void}
   */
  stop() {
    this._isPlaying = false;
    if (!this._activeMeshes) return;
    for (const mesh of this._activeMeshes) {
      const orig = this._originalScales.get(mesh.uuid);
      if (orig) mesh.scale.copy(orig);
    }
    this._time = 0;
  }

  /**
   * Advance the animation by one frame.
   *
   * Uniform scale is applied (X = Y = Z) so the mesh pulsates spherically,
   * matching how cardiac contraction appears in simplified anatomy views.
   *
   * @param {number} delta - Elapsed seconds since last frame.
   * @returns {void}
   */
  update(delta) {
    if (!this._isPlaying || !this._activeMeshes) return;
    this._time += delta;
    const scaleFactor = 1 + AMPLITUDE * Math.sin(OMEGA * this._time);
    for (const mesh of this._activeMeshes) {
      const orig = this._originalScales.get(mesh.uuid);
      if (!orig) continue;
      mesh.scale.set(
        orig.x * scaleFactor,
        orig.y * scaleFactor,
        orig.z * scaleFactor,
      );
    }
  }

  /** @returns {boolean} */
  get isPlaying() { return this._isPlaying; }
}

export { PulseBeatAnimation };
