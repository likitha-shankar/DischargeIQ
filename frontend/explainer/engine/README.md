# DischargeIQ Anatomy Explainer Engine

Self-contained three.js web bundle. Embeds in a Streamlit `<iframe>` or a Flutter
`WebView` from one build. No external 3D vendor, no per-view license.

---

## Quick start

```bash
cd frontend/explainer/engine
npm install
npm run dev       # dev server on http://localhost:5173
npm run build     # production bundle → dist/
```

Before building you must copy the Draco decoder files (see "RUN THESE IN YOUR TERMINAL" below).

---

## Architecture

```
src/
├── main.js           Bootstrap. Loads config, wires subsystems, starts render loop.
├── config.js         Config loading: window.__DISCHARGEIQ_CONFIG__ > query param > postMessage.
├── viewer.js         THREE.WebGLRenderer, IBL lighting, GLTFLoader, OrbitControls.
├── highlight.js      Raycast on tap, emissive emphasis, label callout, Web Speech API.
├── ui.js             Play bar, caption, safety lines, gesture hint, text fallback.
└── animations/
    ├── index.js             Animation registry + AnimationSystem coordinator.
    ├── fluid_accumulation.js  Rising fluid plane (heart failure lungs/legs).
    ├── pulse_beat.js          Sine-wave scale pulse (heartbeat).
    ├── airflow_obstruction.js  Lateral squeeze + inflammation emissive (COPD).
    └── inflammation_highlight.js  Pulsing emissive glow (diabetes pancreas).
```

**Adding a new animation:** create a module in `animations/` implementing the interface below, add one entry to `ANIMATION_CLASSES` in `animations/index.js`. No other file changes.

**Animation interface** (all animations must implement):

| Method | Signature | Contract |
|--------|-----------|---------|
| `play()` | `() → void` | Start or restart. |
| `pause()` | `() → void` | Freeze at current state. |
| `stop()` | `() → void` | Stop and restore original mesh state. |
| `update(delta)` | `(number) → void` | Advance one frame. |
| `isPlaying` | `boolean` | Read-only. |

---

## Lighting stack (do not simplify)

The realistic appearance comes from this stack operating together:

1. **PMREMGenerator + RoomEnvironment** — neutral studio IBL. All PBR materials in loaded GLBs sample this for reflections and indirect light.
2. **ACESFilmic tone mapping** — correct colour grading. Required alongside IBL.
3. **sRGB output colour space** — correct gamma. Required for matching real-world colour.
4. **Key light (DirectionalLight 2.5, warm white)** — main shadow direction.
5. **PCFSoftShadowMap, 2048px** — soft shadow edges that read as medical-grade, not videogame.
6. **Fill light (DirectionalLight 0.8, cool blue-white)** — softens key-side shadows.
7. **AmbientLight 0.15** — prevents pure-black shadows (IBL covers most of this already).

Removing or weakening any item in this stack degrades the clinical trustworthiness of the visual.

---

## Config schema

The engine renders from a single config object. The FastAPI endpoint (Phase 5) assembles
this from the discharge pipeline output. The engine also accepts it via three channels (in priority order):

1. `window.__DISCHARGEIQ_CONFIG__ = { ... }` — set by parent before script loads.
2. `?config=<base64url-JSON>` URL query param.
3. `window.postMessage({ type: 'DISCHARGEIQ_CONFIG', payload: { ... } })`.

### Full example: heart failure (John Marcus)

```json
{
  "model_id": "cardiovascular.heart_failure",
  "model_path": "assets/models/cardiovascular/heart_failure.glb",
  "scale": 1.0,
  "language": "en",
  "title": "What Happened to Your Heart",
  "subtitle": "Based on your discharge papers from Memorial General",
  "mesh_names": {
    "left ventricle": "LV_mesh",
    "right ventricle": "RV_mesh",
    "left atrium": "LA_mesh",
    "right atrium": "RA_mesh",
    "aorta": "Aorta_mesh",
    "pulmonary artery": "PA_mesh",
    "left lung": "LLung_mesh",
    "right lung": "RLung_mesh"
  },
  "default_camera": {
    "position": [0.0, 0.08, 0.55],
    "target": [0.0, 0.0, 0.0]
  },
  "panels": [
    {
      "caption": "Your heart is a pump. In heart failure, the pump became weak. Blood was not moving forward well, so it backed up.",
      "highlight_meshes": ["left ventricle"],
      "animation": "pulse_beat",
      "camera": null
    },
    {
      "caption": "When blood backs up, fluid leaks into your lungs. That is why breathing felt so hard when you came in.",
      "highlight_meshes": ["left lung", "right lung"],
      "animation": "fluid_accumulation",
      "camera": {
        "position": [0.0, 0.12, 0.60],
        "target": [0.0, 0.05, 0.0]
      }
    },
    {
      "caption": "The medicines you are going home with — furosemide and lisinopril — help your heart pump better and remove the extra fluid.",
      "highlight_meshes": ["left ventricle", "aorta"],
      "animation": "pulse_beat",
      "camera": null
    },
    {
      "caption": "Weigh yourself every morning before eating. If you gain more than 2 pounds in one day, call your doctor right away.",
      "highlight_meshes": [],
      "animation": null,
      "camera": null
    }
  ],
  "safety_lines": [
    "Call 911 if you have sudden shortness of breath, chest pain, or feel faint.",
    "Limit fluids to 1.5 litres per day as instructed by your care team.",
    "Do not stop taking furosemide or lisinopril without talking to your doctor."
  ],
  "footer": "This explanation is based on your discharge papers from Memorial General Hospital and has been reviewed by a clinician. It is not medical advice. Always follow your care team's instructions.",
  "voice": {
    "enabled": true,
    "panel_texts": [
      "Your heart is a pump. In heart failure, the pump became weak.",
      "When blood backs up, fluid leaks into your lungs.",
      "The medicines help your heart pump better and remove the extra fluid.",
      "Weigh yourself every morning. Call your doctor if you gain more than 2 pounds in one day."
    ]
  }
}
```

---

## Text-only fallback

When `model_id` is null (resolver returned no verified match) or a model file fails to load,
the engine shows the `text-fallback` div instead of the 3D canvas. The patient still sees
their caption content as plain text. The play bar, safety lines, and grounding footer remain
visible and functional.

---

## Phase 4 resolver logging — note for implementer

The backend resolver (Phase 4) must log two **distinct** outcomes, not one:

| Outcome | Log label | What it means |
|---------|-----------|---------------|
| Entry found but `is_servable` = False | `BLOCKED_NOT_SERVABLE` | Model exists in registry, not yet licensed or clinically approved. Worth sourcing next. |
| No entry matched the diagnosis at all | `NO_MATCH` | Condition not in registry at all. Rare enough to defer, or a new body system to add. |

Both result in `model_id: null` in the config response so the engine always renders the
text fallback — but the distinction in the backend logs is how you prioritise what to source
next. Log both with the original diagnosis string and the matched entry id (if any).

---

## Draco decoder files

The `DRACOLoader` in `viewer.js` points to `./draco/` relative to the built bundle.
Copy the decoder files there before building:

```bash
# Run from frontend/explainer/engine/ after npm install
cp -r node_modules/three/examples/jsm/libs/draco/ public/draco/
```

This is included in the terminal block below.

---

## RUN THESE IN YOUR TERMINAL

```bash
# 1. Install dependencies
cd "/Users/likitha/Desktop/hmm/masters/sem4/healthcare & AI/DischargeIQ/frontend/explainer/engine"
npm install

# 2. Copy Draco decoder files so GLTFLoader can decompress Draco-compressed GLBs
cp -r node_modules/three/examples/jsm/libs/draco/ public/draco/

# 3. Start the dev server (open http://localhost:5173 to see the placeholder sphere
#    with the full realistic lighting pipeline — IBL, ACES tone mapping, soft shadows)
npm run dev

# 4. Build the production bundle for Streamlit and Flutter
npm run build
# Output: dist/  (copy this folder into Flutter assets and reference in pubspec.yaml)
```

Expected in the browser (dev mode, no model file):
- Dark background, warm PBR sphere in the centre
- Key-light shadow visible on the sphere surface
- IBL reflections giving the sphere depth and material quality
- Orbit controls work: drag to rotate, pinch/scroll to zoom
- Play bar visible at bottom with caption area
- Grounding footer always visible
- "Drag to rotate" hint fades on first interaction
