/**
 * File: frontend/explainer/engine/src/main.js
 * Component: Anatomy Explainer - Bootstrap and Wiring
 * Description: Entry point for the Vite build. Reads the explainer config,
 *   initialises the Viewer, HighlightSystem, AnimationSystem, and UIController,
 *   then orchestrates the per-panel render loop. Owns no rendering state directly
 *   - delegates everything to the four subsystems.
 *
 * Config loading priority:
 *   1. window.__DISCHARGEIQ_CONFIG__ (parent-injected before load - fastest)
 *   2. ?config= URL query param (base64url JSON - for iframe src= usage)
 *   3. postMessage from parent (Flutter JS channel or Streamlit postMessage)
 *
 * The engine never crashes on a bad or missing model: it falls back to a
 * text-only panel via UIController.showTextFallback(). The fallback path is
 * exercised when model_id is null (resolver returned no match) or when the
 * model file is missing or fails to load.
 *
 * Phase 4 note (resolver logging):
 *   When the config arrives with model_id === null, the backend already logged
 *   one of two distinct cases:
 *     - "BLOCKED_NOT_SERVABLE": entry found, is_servable = False
 *     - "NO_MATCH": no registry entry matched the diagnosis at all
 *   The frontend does not need to distinguish these - both result in the
 *   text-only fallback. The distinction lives entirely in the backend logs.
 *
 * Dependencies: config.js, viewer.js, highlight.js, ui.js, animations/index.js
 */

import * as THREE from 'three';
import { loadConfigSync, listenForPostMessageConfig } from './config.js';
import { Viewer } from './viewer.js';
import { HighlightSystem } from './highlight.js';
import { UIController } from './ui.js';
import { AnimationSystem } from './animations/index.js';

/**
 * Apply a single panel: update highlight emphasis and start the panel's animation.
 *
 * Called by UIController's onPanelChange callback whenever the active panel
 * changes. Reads the panel object from the config to get highlight_meshes and
 * the animation id.
 *
 * @param {object} panel - Config panel object.
 * @param {HighlightSystem} highlight - Active highlight system.
 * @param {AnimationSystem} animations - Active animation system.
 * @returns {void}
 */
function applyPanel(panel, highlight, animations) {
  if (!panel) return;

  if (panel.highlight_meshes?.length) {
    highlight.emphasiseMeshes(panel.highlight_meshes);
  }
  if (panel.camera) {
    // Camera override per panel is handled in UIController's onPanelChange
    // when viewer is available; stored here for forward compatibility.
  }
  if (panel.animation) {
    animations.play(panel.animation, panel.highlight_meshes ?? []);
  } else {
    animations.stopCurrent();
  }
}

/**
 * Build the per-frame update callback registered with the Viewer.
 *
 * The Viewer calls this every frame with delta time. Order of operations:
 *   1. UI tick (panel auto-advance and progress bar).
 *   2. Animation system update (procedural + baked mixer).
 *   3. Highlight callout position tracking.
 *
 * @param {UIController} ui
 * @param {AnimationSystem} animations
 * @param {HighlightSystem} highlight
 * @returns {function(number): void}
 */
function buildUpdateCallback(ui, animations, highlight) {
  return function onFrame(delta) {
    ui.tick(delta);
    animations.update(delta);
    highlight.updateLabelPosition();
  };
}

/**
 * Handle a loaded GLTF object: wire up baked animations if present.
 *
 * Baked animations are stored in gltf.animations. If the array is non-empty,
 * a THREE.AnimationMixer is created and the first clip is played. The mixer
 * is passed to the AnimationSystem so update() advances it each frame.
 *
 * @param {object} gltf - The GLTF object returned by Viewer.loadModel().
 * @param {THREE.Object3D} modelRoot - The loaded model's scene root.
 * @param {AnimationSystem} animations - The active animation system.
 * @returns {void}
 */
function wireBakedAnimations(gltf, modelRoot, animations) {
  if (!gltf.animations || gltf.animations.length === 0) return;
  try {
    const mixer = new THREE.AnimationMixer(modelRoot);
    const clip = gltf.animations[0];
    mixer.clipAction(clip).play();
    animations.setBakeMixer(mixer);
  } catch (err) {
    console.warn('[DischargeIQ] Failed to wire baked animations:', err);
  }
}

/**
 * Load the 3D model specified in the config and transition from placeholder.
 *
 * If model_id is null or load fails, shows the text-only fallback.
 * The loading overlay is hidden after resolution either way.
 *
 * @param {object} config - Full explainer config.
 * @param {Viewer} viewer - The active viewer.
 * @param {AnimationSystem} animations - The active animation system.
 * @param {UIController} ui - The active UI controller.
 * @returns {Promise<void>}
 */
async function loadModelFromConfig(config, viewer, animations, ui) {
  if (!config.model_id || !config.model_path) {
    ui.showTextFallback(
      config.title || 'Anatomy View',
      (config.panels?.[0]?.caption) || 'A 3D diagram is not yet available for this condition.',
    );
    ui.hideLoading();
    return;
  }

  const gltf = await viewer.loadModel(
    config.model_path,
    config.scale ?? 1.0,
    (progress) => console.debug(`[DischargeIQ] Model load: ${Math.round(progress * 100)}%`),
  );

  if (!gltf) {
    ui.showTextFallback(
      config.title || 'Anatomy View',
      'The anatomy diagram could not be loaded. Your care team can walk you through this information.',
    );
  } else {
    wireBakedAnimations(gltf, gltf.scene, animations);
    if (config.default_camera) {
      viewer.setCamera(config.default_camera.position, config.default_camera.target);
    }
  }
  ui.hideLoading();
}

/**
 * Initialise the full explainer with a resolved config object.
 *
 * Creates all subsystems, wires them together, and begins rendering.
 * This function runs once - further config changes would require a page reload.
 *
 * @param {object} config - Merged explainer config from config.js.
 * @returns {Promise<void>}
 */
async function initWithConfig(config) {
  const canvas = document.getElementById('explainer-canvas');
  const container = document.getElementById('canvas-container');

  const viewer = new Viewer(canvas, container);

  const meshNamesMap = config.mesh_names ?? {};

  const animations = new AnimationSystem(
    viewer.getScene(),
    (name) => viewer.getMeshByName(name),
    meshNamesMap,
  );

  const highlight = new HighlightSystem(
    viewer.getCamera(),
    viewer.getDomElement(),
    (name) => viewer.getMeshByName(name),
    meshNamesMap,
    config.voice?.enabled ?? false,
    config.language ?? 'en',
  );

  const ui = new UIController((panelIndex) => {
    const panel = ui.getPanel(panelIndex);
    applyPanel(panel, highlight, animations);
    if (panel?.camera) viewer.setCamera(panel.camera.position, panel.camera.target);
  });

  ui.applyConfig(config);
  viewer.setUpdateCallback(buildUpdateCallback(ui, animations, highlight));
  await loadModelFromConfig(config, viewer, animations, ui);
  ui.play();
}

/**
 * Entry point: attempt synchronous config load, fall back to postMessage listener.
 *
 * @returns {void}
 */
function main() {
  const config = loadConfigSync();
  if (config) {
    initWithConfig(config).catch((err) => {
      console.error('[DischargeIQ] Fatal init error:', err);
    });
    return;
  }
  // Config not yet available - wait for postMessage (Flutter JS channel / Streamlit).
  listenForPostMessageConfig((lateConfig) => {
    initWithConfig(lateConfig).catch((err) => {
      console.error('[DischargeIQ] Fatal init error (postMessage path):', err);
    });
  });
}

main();
