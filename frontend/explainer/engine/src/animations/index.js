/**
 * File: frontend/explainer/engine/src/animations/index.js
 * Component: Anatomy Explainer - Animation Registry
 * Description: Central registry for all procedural animations. Maps animation id
 *   strings (from the registry entry's `available_animations` list and the config
 *   panel's `animation` field) to their implementing classes.
 *
 *   Adding a new animation requires only:
 *     1. A new module in this directory implementing the animation interface.
 *     2. One entry added to ANIMATION_CLASSES below.
 *   No other file needs to change.
 *
 * Animation interface (all animations must implement):
 *   play()                     → void    Start from current state.
 *   pause()                    → void    Freeze at current state.
 *   stop()                     → void    Stop and restore original mesh state.
 *   update(delta: number)      → void    Advance one frame (delta = seconds).
 *   isPlaying                  → boolean Read-only state.
 *
 * Dependencies: individual animation modules in this directory
 * Consumed by: src/main.js
 */

import { FluidAccumulationAnimation } from './fluid_accumulation.js';
import { PulseBeatAnimation } from './pulse_beat.js';
import { AirflowObstructionAnimation } from './airflow_obstruction.js';
import { InflammationHighlightAnimation } from './inflammation_highlight.js';

/**
 * Map of animation id → animation class.
 *
 * Keys must match the `available_animations` strings in anatomy_registry.json
 * and the `animation` field in explainer config panels. Unknown ids are ignored
 * rather than crashing - the engine logs a warning and shows the panel without
 * animation.
 *
 * @type {Object<string, Function>}
 */
const ANIMATION_CLASSES = {
  fluid_accumulation: FluidAccumulationAnimation,
  pulse_beat: PulseBeatAnimation,
  airflow_obstruction: AirflowObstructionAnimation,
  inflammation_highlight: InflammationHighlightAnimation,
};

class AnimationSystem {
  /**
   * Initialise the animation system with access to the scene and mesh resolver.
   *
   * @param {THREE.Scene} scene - The active THREE.js scene.
   * @param {function(string): THREE.Mesh|null} getMeshByName - Viewer method to
   *   resolve a GLB node name to a THREE.Mesh. Used to build target mesh arrays.
   * @param {Object<string, string>} meshNamesMap - Registry mesh_names map
   *   (friendly label → node name) used to resolve panel highlight_meshes lists.
   */
  constructor(scene, getMeshByName, meshNamesMap) {
    this._scene = scene;
    this._getMeshByName = getMeshByName;
    this._meshNamesMap = meshNamesMap;
    this._active = null;
    this._bakeMixer = null;
  }

  /**
   * Set a THREE.AnimationMixer for GLB baked animations.
   *
   * When a loaded GLB contains embedded animations, main.js passes the mixer
   * here so update() can advance it each frame alongside procedural animations.
   *
   * @param {THREE.AnimationMixer} mixer
   * @returns {void}
   */
  setBakeMixer(mixer) {
    this._bakeMixer = mixer;
  }

  /**
   * Resolve a list of friendly mesh names to actual THREE.Mesh objects.
   *
   * Unknown names produce a console warning and are skipped. Empty result is
   * valid - animations fall back to operating on the placeholder sphere.
   *
   * @param {string[]} friendlyNames - Friendly label strings from the config panel.
   * @returns {THREE.Mesh[]}
   */
  _resolveMeshes(friendlyNames) {
    const meshes = [];
    for (const label of friendlyNames) {
      const nodeName = this._meshNamesMap[label];
      if (!nodeName) {
        console.warn(`[DischargeIQ] Animation: no node name for label '${label}'`);
        continue;
      }
      const mesh = this._getMeshByName(nodeName);
      if (!mesh) {
        console.warn(`[DischargeIQ] Animation: mesh '${nodeName}' not found in scene`);
        continue;
      }
      meshes.push(mesh);
    }
    return meshes;
  }

  /**
   * Start a named procedural animation on the given mesh targets.
   *
   * Stops any currently running animation before starting the new one - only
   * one procedural animation runs at a time (baked animations run in parallel).
   * Unknown animation ids log a warning and return without crashing.
   *
   * @param {string} animationId - Key from ANIMATION_CLASSES, e.g. 'pulse_beat'.
   * @param {string[]} [friendlyNames=[]] - Friendly mesh names to animate.
   * @returns {void}
   */
  play(animationId, friendlyNames = []) {
    this.stopCurrent();
    const AnimClass = ANIMATION_CLASSES[animationId];
    if (!AnimClass) {
      console.warn(`[DischargeIQ] Unknown animation id: '${animationId}'`);
      return;
    }
    const meshes = this._resolveMeshes(friendlyNames);
    this._active = new AnimClass(this._scene, meshes);
    this._active.play();
  }

  /**
   * Pause the currently running procedural animation, if any.
   *
   * @returns {void}
   */
  pauseCurrent() {
    this._active?.pause();
    this._bakeMixer?.timeScale && (this._bakeMixer.timeScale = 0);
  }

  /**
   * Stop and dispose the currently running procedural animation, if any.
   *
   * @returns {void}
   */
  stopCurrent() {
    this._active?.stop();
    this._active = null;
  }

  /**
   * Advance all active animations by one frame. Called from the Viewer's
   * update callback every frame.
   *
   * @param {number} delta - Elapsed seconds since last frame.
   * @returns {void}
   */
  update(delta) {
    this._active?.update(delta);
    this._bakeMixer?.update(delta);
  }
}

export { AnimationSystem, ANIMATION_CLASSES };
