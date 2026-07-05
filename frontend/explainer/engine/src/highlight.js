/**
 * File: frontend/explainer/engine/src/highlight.js
 * Component: Anatomy Explainer - Highlight System
 * Description: Handles tap/click raycast on the 3D canvas. Resolves the hit mesh
 *   to a friendly label using the registry mesh_names map (reversed at init time).
 *   On a hit: visually emphasises the mesh with an emissive boost and shows a
 *   floating HTML label callout. Optionally reads the label aloud via Web Speech API.
 *   Tapping empty space or the same mesh again clears the highlight.
 *
 * Integration point with Viewer:
 *   Receives Viewer.getCamera(), Viewer.getDomElement(), and a getMeshByName()
 *   function. Does NOT own the render loop - call updateLabelPosition() from the
 *   Viewer's update callback each frame to keep the callout tracking the mesh.
 *
 * Dependencies: three
 * Consumed by: src/main.js
 */

import * as THREE from 'three';

/** Emissive colour applied to a highlighted mesh (warm amber). */
const HIGHLIGHT_EMISSIVE = new THREE.Color(0xd47020);

/** Emissive intensity multiplier on highlight. */
const HIGHLIGHT_INTENSITY = 0.5;

class HighlightSystem {
  /**
   * Initialise the highlight system.
   *
   * @param {THREE.PerspectiveCamera} camera - The scene camera used for raycasting.
   * @param {HTMLCanvasElement} canvas - The renderer's canvas element.
   * @param {function(string): THREE.Mesh|null} getMeshByName - Viewer method to look up a mesh by node name.
   * @param {Map<string, string>} meshNamesMap - Registry mesh_names map (friendly label → node name).
   * @param {boolean} voiceEnabled - Whether the Web Speech API read-aloud button is active.
   * @param {string} [language='en'] - BCP-47 language tag for speech synthesis.
   */
  constructor(camera, canvas, getMeshByName, meshNamesMap, voiceEnabled, language = 'en') {
    this._camera = camera;
    this._canvas = canvas;
    this._getMeshByName = getMeshByName;
    this._voiceEnabled = voiceEnabled;
    this._language = language;

    // Build reverse map: node name → friendly label (for hit resolution)
    this._nodeToLabel = _buildReverseMap(meshNamesMap);

    // Build forward map: friendly label → node name (for external emphasis calls)
    this._labelToNode = new Map(Object.entries(meshNamesMap));

    this._raycaster = new THREE.Raycaster();
    this._pointer = new THREE.Vector2();
    this._highlightedMesh = null;
    this._savedEmissive = new THREE.Color();
    this._savedEmissiveIntensity = 0;

    this._callout = document.getElementById('label-callout');
    this._calloutName = document.getElementById('label-name-text');
    this._speakBtn = document.getElementById('label-speak-btn');
    this._closeBtn = document.getElementById('label-close-btn');

    this._bindEvents();
  }

  /**
   * Attach pointer and close-button event listeners.
   *
   * Uses 'pointerup' (not click) so touch and mouse are both handled with
   * one handler and no 300ms delay on mobile.
   *
   * @returns {void}
   */
  _bindEvents() {
    this._canvas.addEventListener('pointerup', (ev) => this._onPointerUp(ev));
    this._closeBtn.addEventListener('click', () => this.clearHighlight());
    this._speakBtn.addEventListener('click', () => {
      if (this._currentLabel) _speakText(this._currentLabel, this._language);
    });
  }

  /**
   * Handle a pointer-up event: raycast and update highlight state.
   *
   * Normalises pointer coordinates to [-1, 1] clip space before raycasting.
   * Ignores pointers that moved more than 8px - they were drag gestures, not taps.
   *
   * @param {PointerEvent} ev
   * @returns {void}
   */
  _onPointerUp(ev) {
    if (ev.movementX ** 2 + ev.movementY ** 2 > 64) return;

    const rect = this._canvas.getBoundingClientRect();
    this._pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    this._pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;

    this._raycaster.setFromCamera(this._pointer, this._camera);
    const hits = this._raycaster.intersectObjects(
      this._camera.parent ? this._camera.parent.children : [],
      true,
    );

    const hit = hits.find(
      (h) => h.object.isMesh && h.object.name !== '__placeholder',
    );

    if (!hit) {
      this.clearHighlight();
      return;
    }

    const label = this._nodeToLabel.get(hit.object.name);
    if (!label) {
      this.clearHighlight();
      return;
    }

    if (this._highlightedMesh === hit.object) {
      this.clearHighlight();
    } else {
      this._applyHighlight(hit.object, label);
    }
  }

  /**
   * Visually emphasise a mesh and show its label callout.
   *
   * Saves the current emissive state before modifying so clearHighlight()
   * can restore exactly what was there, including any existing emissive from
   * the model's own material.
   *
   * @param {THREE.Mesh} mesh - The mesh to highlight.
   * @param {string} label - Friendly name to display in the callout.
   * @returns {void}
   */
  _applyHighlight(mesh, label) {
    this.clearHighlight();

    this._savedEmissive.copy(mesh.material.emissive);
    this._savedEmissiveIntensity = mesh.material.emissiveIntensity ?? 1;
    mesh.material.emissive.copy(HIGHLIGHT_EMISSIVE);
    mesh.material.emissiveIntensity = HIGHLIGHT_INTENSITY;

    this._highlightedMesh = mesh;
    this._currentLabel = label;
    this._calloutName.textContent = label;
    this._speakBtn.style.display = this._voiceEnabled ? '' : 'none';
    this._callout.style.display = 'block';
  }

  /**
   * Remove the highlight from the currently highlighted mesh and hide the callout.
   *
   * Safe to call when nothing is highlighted.
   *
   * @returns {void}
   */
  clearHighlight() {
    if (this._highlightedMesh) {
      this._highlightedMesh.material.emissive.copy(this._savedEmissive);
      this._highlightedMesh.material.emissiveIntensity = this._savedEmissiveIntensity;
      this._highlightedMesh = null;
    }
    this._currentLabel = null;
    this._callout.style.display = 'none';
    window.speechSynthesis && window.speechSynthesis.cancel();
  }

  /**
   * Emphasise a set of meshes by friendly label name (called by animation panels).
   *
   * Used when a panel config specifies highlight_meshes to draw attention to
   * specific structures as the caption advances. Does not show a label callout.
   *
   * @param {string[]} friendlyNames - Friendly labels from the registry mesh_names map.
   * @returns {void}
   */
  emphasiseMeshes(friendlyNames) {
    for (const name of friendlyNames) {
      const nodeName = this._labelToNode.get(name);
      if (!nodeName) continue;
      const mesh = this._getMeshByName(nodeName);
      if (!mesh) continue;
      mesh.material.emissive.copy(HIGHLIGHT_EMISSIVE);
      mesh.material.emissiveIntensity = 0.3;
    }
  }

  /**
   * Update the callout div position each frame to track the highlighted mesh.
   *
   * Projects the mesh bounding-box centre from world space to screen space.
   * Called from the Viewer's update callback so the label stays pinned even
   * as the user rotates the model.
   *
   * @returns {void}
   */
  updateLabelPosition() {
    if (!this._highlightedMesh || this._callout.style.display === 'none') return;
    const pos = _projectMeshCentreToScreen(
      this._highlightedMesh,
      this._camera,
      this._canvas,
    );
    this._callout.style.left = `${pos.x + 12}px`;
    this._callout.style.top = `${pos.y - 20}px`;
  }
}

// ── Module-level helpers ──────────────────────────────────────────────────────

/**
 * Build a reverse map from node name to friendly label.
 *
 * The registry stores {friendlyLabel: nodeName}. Raycasting returns node names,
 * so we need the reverse direction for hit resolution.
 *
 * @param {Object<string, string>} meshNamesMap - {friendlyLabel: nodeName}
 * @returns {Map<string, string>} - {nodeName: friendlyLabel}
 */
function _buildReverseMap(meshNamesMap) {
  const reverse = new Map();
  for (const [label, nodeName] of Object.entries(meshNamesMap)) {
    reverse.set(nodeName, label);
  }
  return reverse;
}

/**
 * Project a mesh's bounding-box centre into canvas pixel coordinates.
 *
 * @param {THREE.Mesh} mesh
 * @param {THREE.Camera} camera
 * @param {HTMLCanvasElement} canvas
 * @returns {{x: number, y: number}} - Pixel coordinates on the canvas element.
 */
function _projectMeshCentreToScreen(mesh, camera, canvas) {
  const box = new THREE.Box3().setFromObject(mesh);
  const centre = new THREE.Vector3();
  box.getCenter(centre);
  centre.project(camera);
  const halfW = canvas.clientWidth / 2;
  const halfH = canvas.clientHeight / 2;
  return {
    x: Math.round(centre.x * halfW + halfW),
    y: Math.round(-centre.y * halfH + halfH),
  };
}

/**
 * Speak a text string via the Web Speech API.
 *
 * Silently skips when speechSynthesis is unavailable (common in some WebViews).
 * Cancels any in-progress speech before starting the new utterance.
 *
 * @param {string} text - Text to speak.
 * @param {string} lang - BCP-47 language tag, e.g. 'en-US'.
 * @returns {void}
 */
function _speakText(text, lang) {
  if (!('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 0.9;
    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.warn('[DischargeIQ] Speech synthesis failed:', err);
  }
}

export { HighlightSystem };
