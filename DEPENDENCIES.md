# DischargeIQ - Dependency & License Manifest

LOF LABS gate requirement: a current manifest of third-party libraries,
frameworks, packages, models, tools, and datasets, with licenses.

**Project license:** Apache License 2.0 (see [LICENSE](LICENSE)).
**Last regenerated:** 2026-07-11.

## How to regenerate

```bash
# Python (backend)
.venv/bin/pip install pip-licenses
.venv/bin/pip-licenses --format=markdown --order=name --with-urls

# Flutter (mobile) - licenses are declared per package on pub.dev
cd dischargeiq_mobile && flutter pub deps
```

## Compliance summary

- **No AGPL and no network-copyleft components** anywhere in the tree - the
  category the LOF guide specifically bans.
- **No pure GPL-only components. No LGPL-only components.** Python is
  overwhelmingly MIT / BSD / Apache-2.0.
- The take-home PDF now uses `reportlab` (BSD); the previous LGPL `fpdf2`
  dependency was removed (2026-07-07) to keep the tree copyleft-free.
- One transitive tri-licensed item remains, flagged below - it carries no
  copyleft obligation on our code.

### Flagged (informational - no obligation on DischargeIQ)

| Package | License | Why it is used | Risk assessment |
|---|---|---|---|
| `pyphen` 0.17.2 | Tri-licensed: GPLv2+ **OR** LGPLv2+ **OR** MPL 1.1 | Transitive via `textstat` (Flesch-Kincaid readability scoring - hard rule 4) | **None.** Tri-license lets us use it under LGPLv2+ or MPL 1.1; we do **not** take the GPL option. No pure-GPL obligation, and it is a transitive readability helper, not linked into any distributed binary. |

Nothing in the tree is AGPL, GPL-only, or LGPL-only. No component triggers a
copyleft obligation on DischargeIQ's own Apache-2.0 code.

## Python (backend) - 80 packages

License distribution: ~33 MIT, ~22 BSD, ~13 Apache-2.0, 1 MPL-2.0
(`certifi`), 1 tri-license (`pyphen`, transitive), remainder dual/permissive.
No LGPL-only or GPL-only packages. Direct dependencies are pinned in
`requirements.txt`; the table below is the full resolved tree.

| Name | Version | License |
|---|---|---|
| GitPython | 3.1.47 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| Pygments | 2.20.0 | BSD-2-Clause |
| altair | 6.1.0 | BSD |
| annotated-doc | 0.0.4 | MIT |
| annotated-types | 0.7.0 | MIT |
| anthropic | 0.97.0 | MIT |
| anyio | 4.13.0 | MIT |
| asyncpg | 0.31.0 | Apache-2.0 |
| attrs | 26.1.0 | MIT |
| blinker | 1.9.0 | MIT |
| cachetools | 7.0.6 | MIT |
| certifi | 2026.4.22 | MPL-2.0 |
| cffi | 2.0.0 | MIT |
| charset-normalizer | 3.4.7 | MIT |
| click | 8.3.3 | BSD-3-Clause |
| cryptography | 46.0.7 | Apache-2.0 OR BSD-3-Clause |
| deepdiff | 9.0.0 | MIT |
| defusedxml | 0.7.1 | Python Software Foundation |
| distro | 1.9.0 | Apache-2.0 |
| docstring_parser | 0.18.0 | MIT |
| fastapi | 0.136.1 | MIT |
| fonttools | 4.62.1 | MIT |
| gitdb | 4.0.12 | BSD |
| google-auth | 2.55.1 | Apache-2.0 |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD |
| idna | 3.13 | BSD-3-Clause |
| iniconfig | 2.3.0 | MIT |
| jiter | 0.14.0 | MIT |
| joblib | 1.5.3 | BSD-3-Clause |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| narwhals | 2.20.0 | MIT |
| nltk | 3.9.4 | Apache-2.0 |
| numpy | 2.4.4 | BSD-3-Clause (+ 0BSD/MIT/Zlib/CC0) |
| openai | 2.32.0 | Apache-2.0 |
| orderly-set | 5.5.0 | MIT |
| packaging | 26.1 | Apache-2.0 OR BSD-2-Clause |
| pandas | 3.0.2 | BSD |
| pdfminer.six | 20251230 | MIT |
| pdfplumber | 0.11.9 | MIT |
| pillow | 12.2.0 | MIT-CMU |
| pluggy | 1.6.0 | MIT |
| protobuf | 7.34.1 | BSD-3-Clause |
| pyarrow | 24.0.0 | Apache-2.0 |
| pyasn1 | 0.6.3 | BSD-2-Clause |
| pyasn1_modules | 0.4.2 | BSD |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.13.3 | MIT |
| pydantic_core | 2.46.3 | MIT |
| pydeck | 0.9.2 | Apache-2.0 |
| pypdf | 6.10.2 | BSD-3-Clause |
| pypdfium2 | 5.7.1 | BSD-3-Clause / Apache-2.0 |
| **pyphen** | 0.17.2 | **GPLv2+ / LGPLv2+ / MPL 1.1** (flagged above; used under LGPL/MPL) |
| pytest | 8.4.2 | MIT |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| python-multipart | 0.0.26 | Apache-2.0 |
| referencing | 0.37.0 | MIT |
| regex | 2026.4.4 | Apache-2.0 / CNRI-Python |
| reportlab | 4.4.10 | BSD |
| requests | 2.33.1 | Apache-2.0 |
| rpds-py | 0.30.0 | MIT |
| six | 1.17.0 | MIT |
| smmap | 5.0.3 | BSD |
| sniffio | 1.3.1 | Apache-2.0 / MIT |
| starlette | 1.0.0 | BSD-3-Clause |
| streamlit | 1.56.0 | Apache-2.0 |
| tenacity | 9.1.4 | Apache-2.0 |
| textstat | 0.7.13 | MIT |
| toml | 0.10.2 | MIT |
| tornado | 6.5.5 | Apache-2.0 |
| tqdm | 4.67.3 | MPL-2.0 AND MIT |
| typing-inspection | 0.4.2 | MIT |
| typing_extensions | 4.15.0 | PSF-2.0 |
| urllib3 | 2.6.3 | MIT |
| uvicorn | 0.46.0 | BSD-3-Clause |

## Flutter (mobile app) - direct dependencies

Declared in `dischargeiq_mobile/pubspec.yaml`. All permissive.

| Package | License | Purpose |
|---|---|---|
| cupertino_icons | MIT | iOS-style icons |
| http | BSD-3-Clause | API calls |
| file_picker | MIT | PDF upload |
| provider | MIT | State management |
| shared_preferences | BSD-3-Clause | On-device quiz game state, theme |
| image_picker | Apache-2.0 | Camera capture for OCR |
| google_mlkit_text_recognition | MIT (plugin) | On-device OCR - see model note below |
| audioplayers | MIT | Per-diagnosis audio explainer |
| video_player | BSD-3-Clause | Per-diagnosis video explainer |
| url_launcher | BSD-3-Clause | Add-to-calendar deep link (Appointments tab) |

## npm

None. The 3D anatomy explainer prototype (three.js/vite) was removed from the
tree on 2026-07-11 - it is out of scope per the accepted work plan ("3D
anatomy visualization: replaced by NotebookLM media") and is archived locally
outside version control.

## Models, services, and datasets (non-package)

| Item | Type | Terms | Notes |
|---|---|---|---|
| Google Gemini API | LLM (primary) | Google APIs Terms of Service | Default provider; `gemini-2.5-flash-lite`. For real patient data the Vertex AI (BAA) path is required. |
| Anthropic Claude API | LLM (fallback option) | Anthropic Commercial Terms | Cross-provider failover path. |
| OpenRouter | LLM (fallback option) | OpenRouter Terms of Service | Alternate failover path (`LLM_FALLBACK_PROVIDER=openrouter`); free-tier models used for demo capacity. |
| Google ML Kit Text Recognition | On-device model | Google APIs Terms | Runs on-device; the photo never leaves the phone. Latin script only. |
| NotebookLM | Media generation tool | Google Terms of Service | Manual generation of per-diagnosis audio/video explainers (no API). |
| Neon PostgreSQL | Hosted database | Neon Terms of Service | History, quiz scores, corpus metadata, clinician review scores. |
| Synthetic discharge corpus | Dataset | Generated by this project | 50 synthetic PDFs in `test-data/synthetic/`. **No real patient data.** Do not commit to a public repo without written LOF/IIT approval. |

## Data-handling note (LOF gate)

All test and evaluation documents are **synthetic or de-identified** (hard
rule 6). No program-provided, clinical, or patient-derived data is committed.
The synthetic corpus and any generated evaluation outputs must stay out of
public repositories unless approved in writing.
