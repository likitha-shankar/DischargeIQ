/**
 * File: frontend/explainer/engine/src/animations/airflow_obstruction.js
 * Component: Anatomy Explainer — Procedural Animation
 * Description: Simulates narrowed airways in COPD by cyclically squeezing the
 *   X and Z axes of target airway meshes. The squeeze alternates between full
 *   width (no obstruction) and 45% reduction (significant obstruction) with a
 *   slow, laboured rhythm (~0.25 Hz, representing one laboured breath every 4s).
 *
 *   A secondary emissive pulse on bronchi meshes represents airway inflammation.
 *   Both effects are removed cleanly on stop().
 *
 * Dependencies: three
 * Consumed by: src/animations/index.js
 */

import * as THREE from 'three';

/** Cycles per second for the obstruction rhythm (0.25 Hz = 4s per cycle). */
const FREQUENCY_HZ = 0.25;

/** Angular frequency: ω = 2π × freq. */
const OMEGA = 2 * Math.PI * FREQUENCY_HZ;

/** Maximum fractional reduction of X/Z scale at peak obstruction. */
const MAX_SQUEEZE = 0.45;

/** Emissive colour representing airway inflammation (dull red). */
const INFLAMMATION_COLOR = new THREE.Color(0x9a2020);

class AirflowObstructionAnimation {
  /**
   * Construct the animation. Does not modify the scene until play() is called.
   *
   * @param {THREE.Scene} scene - The active THREE.js scene.
   * @param {THREE.Mesh[]} targetMeshes - Airway meshes to squeeze (trachea,
   *   bronchi, bronchioles). Falls back to the placeholder sphere.
   */
  constructor(scene, targetMeshes) {
    this._scene = scene;
    this._targetMeshes = targetMeshes;
    this._isPlaying = false;
    this._time = 0;
    this._originalScales = new Map();
    this._originalEmissives = new Map();
    this._activeMeshes = [];
  }

  /**
   * Resolve active meshes, falling back to the placeholder when targets are empty.
   *
   * @returns {THREE.Mesh[]}
   */
  _resolveMeshes() {
    if (this._targetMeshes.length > 0) return this._targetMeshes;
    const ph = this._scene.getObjectByName('__placeholder');
    return ph ? [ph] : [];
  }

  /**
   * Save the original scale and emissive of each mesh before first play.
   *
   * @param {THREE.Mesh[]} meshes
   * @returns {void}
   */
  _saveOriginals(meshes) {
    for (const mesh of meshes) {
      if (!this._originalScales.has(mesh.uuid)) {
        this._originalScales.set(mesh.uuid, mesh.scale.clone());
      }
      if (!this._originalEmissives.has(mesh.uuid) && mesh.material?.emissive) {
        this._originalEmissives.set(mesh.uuid, mesh.material.emissive.clone());
      }
    }
  }

  /**
   * Start the airflow obstruction animation.
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
   * Pause the animation at its current squeeze state.
   *
   * @returns {void}
   */
  pause() {
    this._isPlaying = false;
  }

  /**
   * Stop and restore all meshes to original scale and emissive.
   *
   * @returns {void}
   */
  stop() {
    this._isPlaying = false;
    for (const mesh of this._activeMeshes) {
      const origScale = this._originalScales.get(mesh.uuid);
      if (origScale) mesh.scale.copy(origScale);
      const origEmissive = this._originalEmissives.get(mesh.uuid);
      if (origEmissive && mesh.material?.emissive) {
        mesh.material.emissive.copy(origEmissive);
      }
    }
    this._time = 0;
  }

  /**
   * Advance the animation by one frame.
   *
   * Squeeze fraction oscillates 0 → MAX_SQUEEZE → 0 using |sin(ωt)|, giving a
   * one-directional narrowing pattern (airways only squeeze, never expand beyond
   * their rest diameter) that reads as obstruction rather than pulsing.
   *
   * @param {number} delta - Elapsed seconds since last frame.
   * @returns {void}
   */
  update(delta) {
    if (!this._isPlaying) return;
    this._time += delta;
    const squeeze = MAX_SQUEEZE * Math.abs(Math.sin(OMEGA * this._time));
    const lateralScale = 1 - squeeze;
    const inflammationIntensity = squeeze * 0.4;

    for (const mesh of this._activeMeshes) {
      const orig = this._originalScales.get(mesh.uuid);
      if (orig) {
        mesh.scale.set(orig.x * lateralScale, orig.y, orig.z * lateralScale);
      }
      if (mesh.material?.emissive) {
        mesh.material.emissive.copy(INFLAMMATION_COLOR).multiplyScalar(inflammationIntensity);
        mesh.material.emissiveIntensity = 1;
      }
    }
  }

  /** @returns {boolean} */
  get isPlaying() { return this._isPlaying; }
}

export { AirflowObstructionAnimation };
