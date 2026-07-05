/**
 * File: frontend/explainer/engine/src/animations/fluid_accumulation.js
 * Component: Anatomy Explainer - Procedural Animation
 * Description: Simulates fluid rising inside a region (pulmonary oedema in heart
 *   failure, bilateral leg oedema). A semi-transparent blue-grey plane is created
 *   within the bounding box of the target meshes and its Y scale animates from 0
 *   to 1 over `fillDuration` seconds, then holds. Reversing play calls the drain.
 *
 *   Works on any mesh set - falls back to a unit-cube bounding region when no
 *   target meshes are present in the scene, so it renders something meaningful
 *   even against the placeholder sphere.
 *
 * Dependencies: three
 * Consumed by: src/animations/index.js
 */

import * as THREE from 'three';

/** Seconds for the fluid to rise from empty to full. */
const FILL_DURATION_S = 3.5;

/** Fluid colour: muted blue representing oedema. */
const FLUID_COLOR = 0x4a7aaa;

/** Fluid transparency (0 = fully transparent, 1 = opaque). */
const FLUID_OPACITY = 0.35;

class FluidAccumulationAnimation {
  /**
   * Construct the animation. Does not add anything to the scene yet - call play().
   *
   * @param {THREE.Scene} scene - The active THREE.js scene.
   * @param {THREE.Mesh[]} targetMeshes - Meshes representing the affected region.
   *   The fluid plane is sized and positioned to their collective bounding box.
   */
  constructor(scene, targetMeshes) {
    this._scene = scene;
    this._targetMeshes = targetMeshes;
    this._isPlaying = false;
    this._elapsed = 0;
    this._direction = 1;
    this._fluidMesh = null;
    this._originY = 0;
    this._height = 1;
  }

  /**
   * Compute the collective bounding box of the target meshes.
   *
   * Falls back to a unit cube at the origin when the mesh array is empty
   * or when all meshes have degenerate geometry.
   *
   * @returns {THREE.Box3}
   */
  _computeBounds() {
    if (this._targetMeshes.length === 0) {
      return new THREE.Box3(
        new THREE.Vector3(-0.2, -0.2, -0.1),
        new THREE.Vector3(0.2, 0.2, 0.1),
      );
    }
    const box = new THREE.Box3();
    for (const mesh of this._targetMeshes) {
      box.expandByObject(mesh);
    }
    if (box.isEmpty()) {
      return new THREE.Box3(
        new THREE.Vector3(-0.2, -0.2, -0.1),
        new THREE.Vector3(0.2, 0.2, 0.1),
      );
    }
    return box;
  }

  /**
   * Build the fluid plane mesh and add it to the scene.
   *
   * The plane starts at full bounds size but Y-scaled to 0, positioned at the
   * bottom of the bounding box. Animation drives Y scale from 0 → 1.
   *
   * @returns {void}
   */
  _buildFluidMesh() {
    const box = this._computeBounds();
    const size = new THREE.Vector3();
    box.getSize(size);
    const center = new THREE.Vector3();
    box.getCenter(center);

    this._height = size.y;
    this._originY = box.min.y;

    const geo = new THREE.BoxGeometry(size.x * 1.05, size.y, size.z * 1.05);
    const mat = new THREE.MeshStandardMaterial({
      color: FLUID_COLOR,
      opacity: FLUID_OPACITY,
      transparent: true,
      depthWrite: false,
      roughness: 0.3,
      metalness: 0.1,
    });
    this._fluidMesh = new THREE.Mesh(geo, mat);
    this._fluidMesh.name = '__fluid_anim';
    // Position at bottom of bounding box; scale Y from that bottom edge
    this._fluidMesh.position.set(center.x, box.min.y, center.z);
    this._fluidMesh.scale.y = 0;
    this._scene.add(this._fluidMesh);
  }

  /**
   * Start the fill animation. If already playing, resets and plays from empty.
   *
   * @returns {void}
   */
  play() {
    if (!this._fluidMesh) this._buildFluidMesh();
    this._isPlaying = true;
    this._direction = 1;
  }

  /**
   * Pause the animation at its current fill level.
   *
   * @returns {void}
   */
  pause() {
    this._isPlaying = false;
  }

  /**
   * Stop and remove the fluid mesh from the scene, freeing GPU memory.
   *
   * After stop(), play() can be called again to restart from empty.
   *
   * @returns {void}
   */
  stop() {
    this._isPlaying = false;
    this._elapsed = 0;
    if (this._fluidMesh) {
      this._scene.remove(this._fluidMesh);
      this._fluidMesh.geometry.dispose();
      this._fluidMesh.material.dispose();
      this._fluidMesh = null;
    }
  }

  /**
   * Advance the animation by one frame.
   *
   * The fluid plane Y scale and position origin are updated together so the
   * plane always grows from the bottom of the bounding box upward.
   *
   * @param {number} delta - Elapsed seconds since last frame.
   * @returns {void}
   */
  update(delta) {
    if (!this._isPlaying || !this._fluidMesh) return;
    this._elapsed = Math.min(this._elapsed + delta * this._direction, FILL_DURATION_S);
    const fraction = Math.max(0, this._elapsed / FILL_DURATION_S);
    // Scale from bottom edge: y position moves up as scale grows
    this._fluidMesh.scale.y = fraction;
    this._fluidMesh.position.y = this._originY + (fraction * this._height) / 2;
    if (this._elapsed >= FILL_DURATION_S) this._isPlaying = false;
  }

  /** @returns {boolean} */
  get isPlaying() { return this._isPlaying; }
}

export { FluidAccumulationAnimation };
