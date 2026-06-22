/**
 * File: frontend/explainer/engine/src/viewer.js
 * Component: Anatomy Explainer — Rendering Core
 * Description: Owns the WebGLRenderer, scene, camera, orbit controls, lighting,
 *   model loading, and render loop. Everything visual lives here except highlight
 *   overlays and procedural animations (which are separate modules that call back
 *   into this module's scene/mesh references).
 *
 * Lighting design (read before editing):
 *   The realistic look comes entirely from the lighting stack, not the model.
 *   IBL via PMREMGenerator + RoomEnvironment drives PBR material appearance.
 *   ACESFilmic tone mapping and sRGB output color space are required for correct
 *   color grading. The key light casts soft shadows (PCFSoft, 2048px map).
 *   Do not remove or simplify this stack — a flat-lit model reads as untrustworthy.
 *
 * Dependencies: three, three/addons/...
 * Consumed by: src/main.js
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/** Max device pixel ratio rendered. Caps mobile GPU load. */
const MAX_DPR = 2;

/** Shadow map resolution. Must be power of two. 2048 gives clean soft edges. */
const SHADOW_MAP_SIZE = 2048;

/** Camera vertical field of view in degrees. */
const CAMERA_FOV = 45;

class Viewer {
  /**
   * Create a Viewer and immediately begin rendering a placeholder scene.
   * The full lighting pipeline (IBL + tone mapping + shadows) is active before
   * any GLB is loaded, so visual quality is apparent from frame one.
   *
   * @param {HTMLCanvasElement} canvas - The canvas element to render into.
   * @param {HTMLElement} container - The canvas's parent container; used for sizing.
   */
  constructor(canvas, container) {
    this._canvas = canvas;
    this._container = container;
    this._userUpdateCallback = null;
    this._clock = new THREE.Clock();
    this._placeholderMesh = null;
    this._modelRoot = null;

    this._renderer = this._createRenderer();
    this._scene = this._createScene();
    this._camera = this._createCamera();
    this._setupIBL();
    this._setupKeyLight();
    this._setupFillAndAmbient();
    this._placeholderMesh = this._createPlaceholder();
    this._controls = this._setupControls();
    this._setupResize();
    this._startRenderLoop();
  }

  /**
   * Create the WebGLRenderer with realistic rendering settings.
   *
   * All quality flags must be set before the first render frame. Changing
   * toneMapping or outputColorSpace after first render causes a flash.
   *
   * @returns {THREE.WebGLRenderer}
   */
  _createRenderer() {
    const renderer = new THREE.WebGLRenderer({
      canvas: this._canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    renderer.setPixelRatio(dpr);
    renderer.setSize(this._container.clientWidth, this._container.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.9;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    return renderer;
  }

  /**
   * Create the scene with a dark clinical background.
   *
   * Background color #1a1a1a matches the surrounding HTML dark theme.
   * No fog — anatomy models need clear depth at all distances.
   *
   * @returns {THREE.Scene}
   */
  _createScene() {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);
    return scene;
  }

  /**
   * Create a perspective camera positioned for a front-on torso view.
   *
   * Near plane at 0.01 prevents z-fighting on small anatomical structures.
   * Far plane at 100 is generous — anatomy models are rarely deeper than 5 units.
   *
   * @returns {THREE.PerspectiveCamera}
   */
  _createCamera() {
    const { clientWidth, clientHeight } = this._container;
    const aspect = clientWidth / (clientHeight || 1);
    const camera = new THREE.PerspectiveCamera(CAMERA_FOV, aspect, 0.01, 100);
    camera.position.set(0, 0.08, 0.55);
    camera.lookAt(0, 0, 0);
    return camera;
  }

  /**
   * Set up Image-Based Lighting using PMREMGenerator and RoomEnvironment.
   *
   * This is the single biggest contributor to a "realistic" look. PBR materials
   * in loaded GLBs sample this environment map for reflections and indirect light.
   * The RoomEnvironment generates a neutral studio HDRI suitable for clinical
   * anatomy presentation. Dispose the generator after use — it holds GPU memory.
   *
   * @returns {void}
   */
  _setupIBL() {
    const pmrem = new THREE.PMREMGenerator(this._renderer);
    pmrem.compileEquirectangularShader();
    const envTexture = pmrem.fromScene(
      new RoomEnvironment(),
      0.04,
    ).texture;
    this._scene.environment = envTexture;
    pmrem.dispose();
  }

  /**
   * Add the primary key light that casts soft shadows.
   *
   * Warm white (0xfff8f0) at upper-right-front creates the main shadow direction.
   * Shadow camera is sized to cover a ~2m cube centred on origin (typical anatomy scale).
   *
   * @returns {void}
   */
  _setupKeyLight() {
    const key = new THREE.DirectionalLight(0xfff8f0, 2.5);
    key.position.set(2, 4, 3);
    key.castShadow = true;
    key.shadow.mapSize.set(SHADOW_MAP_SIZE, SHADOW_MAP_SIZE);
    key.shadow.camera.near = 0.1;
    key.shadow.camera.far = 20;
    key.shadow.camera.left = -2;
    key.shadow.camera.right = 2;
    key.shadow.camera.top = 2;
    key.shadow.camera.bottom = -2;
    key.shadow.bias = -0.001;
    this._scene.add(key);
  }

  /**
   * Add the fill light and residual ambient light.
   *
   * Cool blue-white fill from upper-left-back softens key-light shadows without
   * flattening the model. Ambient at 0.15 prevents pure-black shadows (IBL already
   * provides most ambient contribution; this is just a safety floor).
   *
   * @returns {void}
   */
  _setupFillAndAmbient() {
    const fill = new THREE.DirectionalLight(0xe8f0ff, 0.8);
    fill.position.set(-3, 1, -2);
    this._scene.add(fill);

    const ambient = new THREE.AmbientLight(0xffffff, 0.15);
    this._scene.add(ambient);
  }

  /**
   * Create and add a PBR placeholder sphere visible before any model loads.
   *
   * The sphere uses MeshStandardMaterial (PBR) so it demonstrates the full
   * lighting pipeline — IBL reflections, key shadow, fill gradient — from
   * frame one. This is the visual checkpoint to confirm realistic rendering
   * is working before a real GLB is sourced.
   *
   * @returns {THREE.Mesh}
   */
  _createPlaceholder() {
    const geo = new THREE.SphereGeometry(0.15, 64, 64);
    const mat = new THREE.MeshStandardMaterial({
      color: 0xd46050,
      roughness: 0.4,
      metalness: 0.0,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.name = '__placeholder';
    this._scene.add(mesh);
    return mesh;
  }

  /**
   * Create touch-first OrbitControls with momentum damping.
   *
   * enableDamping gives the natural feeling of inertia on touch swipe.
   * dampingFactor and rotateSpeed are tuned for one-thumb phone use.
   * Min/max distance prevents the user from clipping inside the mesh or
   * zooming out to a dot. Polar limits keep the model right-side-up.
   *
   * @returns {OrbitControls}
   */
  _setupControls() {
    const controls = new OrbitControls(this._camera, this._renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.6;
    controls.zoomSpeed = 0.8;
    controls.panSpeed = 0.5;
    controls.minDistance = 0.15;
    controls.maxDistance = 3.0;
    controls.minPolarAngle = 0;
    controls.maxPolarAngle = Math.PI;
    controls.touches = {
      ONE: THREE.TOUCH.ROTATE,
      TWO: THREE.TOUCH.DOLLY_PAN,
    };
    return controls;
  }

  /**
   * Attach a ResizeObserver to the container so the renderer and camera
   * aspect ratio update whenever the iframe or WebView is resized.
   *
   * Caps DPR at MAX_DPR after resize — device DPR does not change at runtime
   * but the explicit cap prevents the renderer from reading an inflated value.
   *
   * @returns {void}
   */
  _setupResize() {
    const ro = new ResizeObserver(() => {
      const w = this._container.clientWidth;
      const h = this._container.clientHeight;
      if (w === 0 || h === 0) return;
      this._camera.aspect = w / h;
      this._camera.updateProjectionMatrix();
      this._renderer.setSize(w, h);
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      this._renderer.setPixelRatio(dpr);
    });
    ro.observe(this._container);
  }

  /**
   * Start the requestAnimationFrame render loop.
   *
   * Calls the user-supplied update callback (if any) with deltaTime each frame
   * so animation and highlight systems can hook in without owning the loop.
   *
   * @returns {void}
   */
  _startRenderLoop() {
    const tick = () => {
      requestAnimationFrame(tick);
      const delta = this._clock.getDelta();
      this._controls.update();
      if (typeof this._userUpdateCallback === 'function') {
        this._userUpdateCallback(delta);
      }
      this._renderer.render(this._scene, this._camera);
    };
    tick();
  }

  /**
   * Build a GLTFLoader pre-configured with DRACOLoader.
   *
   * Draco decoder WASM files must be present in public/draco/ (copied there by
   * the Phase 7 asset pipeline script). Without them, uncompressed GLBs still
   * load correctly — Draco is only needed for compressed models.
   *
   * @returns {GLTFLoader}
   */
  _buildGLTFLoader() {
    const draco = new DRACOLoader();
    draco.setDecoderPath('./draco/');
    const loader = new GLTFLoader();
    loader.setDRACOLoader(draco);
    return loader;
  }

  /**
   * Traverse a loaded GLTF scene graph to enable shadows and normalise scale.
   *
   * Every Mesh node receives castShadow and receiveShadow so shadows work
   * correctly regardless of how the GLB author structured the hierarchy.
   * A uniform scale factor (from the registry entry) is applied to the root
   * to normalise models from different sources to a common size.
   *
   * @param {THREE.Group} gltfScene - The scene root from GLTF.scene.
   * @param {number} scale - Uniform scale from registry entry (typically 1.0).
   * @returns {void}
   */
  _processGLTFScene(gltfScene, scale) {
    gltfScene.scale.setScalar(scale);
    gltfScene.traverse((node) => {
      if (node.isMesh) {
        node.castShadow = true;
        node.receiveShadow = true;
      }
    });
  }

  /**
   * Remove the placeholder sphere from the scene and free its GPU memory.
   *
   * Called after a real model has been successfully loaded. Safe to call
   * multiple times — guards against double-dispose.
   *
   * @returns {void}
   */
  _disposePlaceholder() {
    if (!this._placeholderMesh) return;
    this._scene.remove(this._placeholderMesh);
    this._placeholderMesh.geometry.dispose();
    this._placeholderMesh.material.dispose();
    this._placeholderMesh = null;
  }

  /**
   * Asynchronously load a GLB model from the given path.
   *
   * On success: disposes the placeholder, adds the model to the scene, stores
   * the root for later mesh lookup, and returns the GLTF object.
   * On failure: leaves the placeholder visible, logs the error, and returns null.
   * The engine never crashes on a bad model path — a missing visual is safe.
   *
   * @param {string} modelPath - URL or relative path to the GLB file.
   * @param {number} [scale=1.0] - Uniform scale to apply after load.
   * @param {function(number): void} [onProgress] - Progress callback (0–1).
   * @returns {Promise<object|null>} - Resolved GLTF object, or null on failure.
   */
  async loadModel(modelPath, scale = 1.0, onProgress = null) {
    const loader = this._buildGLTFLoader();
    try {
      const gltf = await new Promise((resolve, reject) => {
        loader.load(
          modelPath,
          resolve,
          onProgress ? (ev) => {
            if (ev.lengthComputable) onProgress(ev.loaded / ev.total);
          } : undefined,
          reject,
        );
      });
      this._disposePlaceholder();
      this._processGLTFScene(gltf.scene, scale);
      this._scene.add(gltf.scene);
      this._modelRoot = gltf.scene;
      return gltf;
    } catch (err) {
      console.error('[DischargeIQ Viewer] Model load failed:', err);
      return null;
    }
  }

  /**
   * Smoothly move the camera to a new position and look-at target.
   *
   * Sets OrbitControls target so orbit rotation stays centred on the new target.
   * Does not animate (instant snap) — smooth interpolation can be added in a
   * future pass once the panel navigation UX is validated.
   *
   * @param {number[]} position - [x, y, z] camera position.
   * @param {number[]} target   - [x, y, z] look-at target.
   * @returns {void}
   */
  setCamera(position, target) {
    this._camera.position.set(...position);
    this._controls.target.set(...target);
    this._controls.update();
  }

  /**
   * Find a mesh in the loaded model by its node name.
   *
   * Used by the highlight and animation systems to resolve names from the
   * registry `mesh_names` map to actual THREE.Mesh objects.
   * Returns null if no model is loaded or no mesh with that name exists.
   *
   * @param {string} name - Exact GLB mesh node name, e.g. 'LV_mesh'.
   * @returns {THREE.Mesh|null}
   */
  getMeshByName(name) {
    if (!this._modelRoot) return null;
    let found = null;
    this._modelRoot.traverse((node) => {
      if (node.isMesh && node.name === name) found = node;
    });
    return found;
  }

  /**
   * Register a callback invoked each frame with the elapsed delta time.
   *
   * Only one callback is supported. Animation and highlight systems use this
   * to run per-frame updates without owning the render loop.
   *
   * @param {function(number): void} callback - Called with deltaTime in seconds.
   * @returns {void}
   */
  setUpdateCallback(callback) {
    this._userUpdateCallback = callback;
  }

  /**
   * Return the underlying THREE.Scene for external systems that need scene access.
   *
   * @returns {THREE.Scene}
   */
  getScene() { return this._scene; }

  /**
   * Return the active camera.
   *
   * @returns {THREE.PerspectiveCamera}
   */
  getCamera() { return this._camera; }

  /**
   * Return the renderer DOM element (the canvas).
   *
   * @returns {HTMLCanvasElement}
   */
  getDomElement() { return this._renderer.domElement; }
}

export { Viewer };
