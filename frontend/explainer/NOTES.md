# Anatomy Explainer - Human Work Items

These tasks are explicitly outside the scope of the AI-written engine code.
Every item here requires a human decision and human sign-off before the
corresponding registry entry can serve a model to patients.

---

## 1. Source real anatomy GLB models for each body system

No model file is bundled in this repo. You must download, inspect, and
place each GLB before its registry entry can be activated.

**Candidate repositories (check these in priority order):**

| Repository | URL | Notes |
|---|---|---|
| Z-Anatomy | https://www.z-anatomy.com | Open-source human anatomy atlas; CC-BY likely |
| Open Anatomy Project | https://www.openanatomy.org | Harvard-originated; mixed license per structure |
| AnatomyTOOL Open3DModel | https://www.anatomytool.org | Community-contributed; verify per model |
| Sketchfab (filtered: CC-BY) | https://sketchfab.com | Search with license filter; download GLB/GLTF |
| NIH 3D Print Exchange | https://3d.nih.gov | Public domain, US government; GLB export available |

**Priority order for sourcing (matches the three real registry targets):**
1. Cardiovascular - heart and lungs for heart failure (`cardiovascular/heart_failure.glb`)
2. Respiratory - airways and lungs for COPD (`respiratory/copd_airways.glb`)
3. Endocrine - pancreas region for diabetes (`endocrine/pancreas_diabetes.glb`)

**Where to place models once downloaded:**
```
frontend/explainer/engine/assets/models/<body_system>/<filename>.glb
```
The `model_path` field in `anatomy_registry.json` is relative to that
`assets/models/` root. Match it exactly.

**After placing a model, run the asset pipeline validation script:**
```
python frontend/explainer/scripts/validate_asset.py \
    --model-path frontend/explainer/engine/assets/models/cardiovascular/heart_failure.glb \
    --registry-id cardiovascular.heart_failure
```
The script checks that every mesh node name in `mesh_names` exists in the GLB
and prints a mismatch report. Fix mismatches before proceeding.

---

## 2. Confirm each model's license permits our deployment context

**"Free to view" is not "free to ship."**

Before setting `"license_verified": true` in `anatomy_registry.json` for any
entry, a team member must confirm ALL of the following:

- [ ] The license allows patient-facing deployment (not just personal or academic use).
- [ ] The license allows the deployment context (commercial service, SaaS, hospital portal - whichever applies to DischargeIQ's final deployment).
- [ ] Attribution requirements (if any) are recorded and will be displayed in the UI.
- [ ] Modification rights are confirmed if the model will be edited, segmented, or re-rigged.

**Do not set `license_verified: true` based on a guess. Read the actual license text.**

Once confirmed, update the `"license"` field with the SPDX identifier (e.g.
`"CC-BY-4.0"`) and the `"source"` field with the attribution string required
by the license. Then set `"license_verified": true`.

---

## 3. Clinical review of every model before patient exposure

Before setting `"clinical_review_status": "approved"` in `anatomy_registry.json`
for any entry, a clinical reviewer (physician, NP, or PA familiar with the
condition) must confirm:

- [ ] The model accurately represents the relevant anatomy for the condition.
- [ ] The mesh labels in `mesh_names` are anatomically correct.
- [ ] The animations (e.g. `fluid_accumulation` for heart failure) correctly
  represent the pathophysiology described in the discharge documents.
- [ ] No mesh or animation could be misinterpreted in a way that causes patient
  harm or unnecessary anxiety.

**The engine never serves a model to a patient without APPROVED status.**
The fallback is always clean text - a missing visual is safe; a misleading
one is not.

Document each clinical review with: reviewer name, credentials, date, and
any conditions or caveats attached to the approval.

---

## 4. Mesh name verification after model placement

After downloading and placing a GLB, the mesh node names inside the file
may differ from the names recorded in `mesh_names`. Run the asset pipeline
script (Phase 7, to be implemented) to get a mismatch report, then update
either the GLB (rename nodes in Blender or a GLTF editor) or the registry
`mesh_names` entries to match. The highlight system depends on exact name
matching - a single character difference silently breaks highlighting.

---

## 5. Compression before deployment

Raw GLB files from anatomy repositories can be 50–200 MB. Before deploying:

- Run Draco or meshopt compression (the asset pipeline script handles this).
- Cap texture resolution at 1024×1024 for mobile WebView performance.
- Target compressed file size: < 8 MB per model for acceptable WebView load time.

---

*This file is maintained by the team lead. Update the checkboxes as items are completed.*
