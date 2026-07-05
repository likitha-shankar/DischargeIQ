"""
File: frontend/explainer/registry/schema.py
Component: Anatomy Explainer - Registry Schema
Description: Pydantic v2 models that define and validate every entry in
  anatomy_registry.json. This is the sole type contract between the JSON
  manifest and the rest of the system. No registry data is consumed
  without passing through these models.

Key classes: BodySystem, ClinicalReviewStatus, CameraConfig,
             RegistryEntry, AnatomyRegistry

Dependencies: pydantic>=2.0.0 (already in requirements.txt)

Consumed by: frontend/explainer/registry/loader.py,
             dischargeiq/agents/anatomy_resolver.py,
             dischargeiq/main.py (explainer config endpoint)

Hard rules:
  - Do not add new body system values to BodySystem without a corresponding
    registry entry and a sourcing plan for the GLB model.
  - `license_verified` and `clinical_review_status` default to the blocked
    (safe) state. Only humans set them to True / APPROVED after review.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class BodySystem(str, Enum):
    """
    Controlled vocabulary covering the eleven body systems the engine targets.

    Extending this enum requires a corresponding entry in anatomy_registry.json
    and a GLB sourcing plan. Do not add values for hypothetical future systems.
    """

    CARDIOVASCULAR = "cardiovascular"
    RESPIRATORY = "respiratory"
    DIGESTIVE = "digestive"
    NERVOUS = "nervous"
    MUSCULOSKELETAL = "musculoskeletal"
    URINARY = "urinary"
    ENDOCRINE = "endocrine"
    INTEGUMENTARY = "integumentary"
    REPRODUCTIVE = "reproductive"
    LYMPHATIC_IMMUNE = "lymphatic_immune"
    SPECIAL_SENSES = "special_senses"


class ClinicalReviewStatus(str, Enum):
    """
    Gate that controls whether the engine may serve a model to patients.

    Only a clinician may advance a model from PENDING to APPROVED. The engine
    checks this at render time and falls back to text if not APPROVED.
    """

    PENDING = "pending"
    APPROVED = "approved"


class CameraConfig(BaseModel):
    """
    Opening camera position and look-at target in model-space units.

    Attributes:
        position: [x, y, z] camera eye position. Tuned per model so the
                  default view shows the clinically relevant region.
        target:   [x, y, z] point the camera looks at. Usually the centroid
                  of the primary anatomical structure.
    """

    position: Annotated[list[float], Field(min_length=3, max_length=3)]
    target: Annotated[list[float], Field(min_length=3, max_length=3)]


class RegistryEntry(BaseModel):
    """
    One anatomy model entry in the registry manifest.

    The engine enforces two hard gates before serving a model:
      1. `license_verified` must be True  - set by a human after confirming the
         model's license permits the deployment context (commercial, patient-facing).
      2. `clinical_review_status` must be APPROVED - set by a clinician after
         verifying the model's anatomical accuracy for the target condition.

    Both default to the blocked state. A new entry that has never been reviewed
    is automatically refused by the engine and falls back to text. This is
    intentional: a missing visual is acceptable; a wrong one is not.

    Attributes:
        id: Stable dot-namespaced identifier. Convention: '<system>.<condition>'.
            Never reuse or rename an id - downstream code stores these as keys.
        body_system: Which of the eleven body systems this model belongs to.
        region: Plain-language anatomical region, e.g. 'chest', 'left knee'.
        condition_keys: Lowercase strings matched against discharge diagnoses by
            the anatomy resolver. Longer keys win ties. Include all clinical
            synonyms used in practice.
        model_path: Path to the GLB file relative to the engine's assets root
            (frontend/explainer/engine/assets/models/). The file need not exist
            until the model is sourced; the engine guards against missing files.
        source: Attribution string for the model's origin.
        license: SPDX identifier or a descriptive license string.
        license_verified: Human-set flag. False until a team member confirms the
            license permits our deployment context. The engine blocks on False.
        clinical_review_status: Clinician-set enum. PENDING until a clinical
            reviewer signs off on anatomical accuracy. The engine blocks on PENDING.
        mesh_names: Map of friendly patient-facing label to the exact mesh node
            name inside the GLB, e.g. {'left ventricle': 'LV_mesh'}. Used by the
            highlight system to identify tappable regions.
        available_animations: Animation IDs this model supports. Must match keys
            in the engine's animation library (engine/animations/).
        default_camera: Opening camera position and look-at target.
        scale: Uniform scale applied after model load to normalise size across
            models from different sources. Must be > 0.
    """

    id: str = Field(
        ...,
        description="Stable dot-namespaced id, e.g. 'cardiovascular.heart_failure'.",
    )
    body_system: BodySystem
    region: str = Field(
        ...,
        description="Plain-language anatomical region, e.g. 'chest'.",
    )
    condition_keys: list[str] = Field(
        ...,
        description=(
            "Lowercase strings matched against discharge diagnoses. "
            "Include all clinical synonyms. Longer keys win on ties."
        ),
    )
    model_path: str = Field(
        ...,
        description=(
            "GLB path relative to engine/assets/models/. "
            "Need not exist until the model is sourced."
        ),
    )
    source: str = Field(
        ...,
        description="Attribution for the model's origin, e.g. 'Z-Anatomy project v2024'.",
    )
    license: str = Field(
        ...,
        description="SPDX license identifier or descriptive string, e.g. 'CC-BY-4.0'.",
    )
    license_verified: bool = Field(
        default=False,
        description=(
            "Set to True only after a team member confirms the license permits "
            "patient-facing commercial deployment. Engine blocks on False."
        ),
    )
    clinical_review_status: ClinicalReviewStatus = Field(
        default=ClinicalReviewStatus.PENDING,
        description=(
            "Set to APPROVED only after a clinical reviewer confirms anatomical "
            "accuracy for the target condition. Engine blocks on PENDING."
        ),
    )
    mesh_names: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Friendly label → exact GLB mesh node name. "
            "e.g. {'left ventricle': 'LV_mesh'}. "
            "Run the asset-pipeline validation script to verify names match the GLB."
        ),
    )
    available_animations: list[str] = Field(
        default_factory=list,
        description=(
            "Animation IDs from the engine library this model supports. "
            "e.g. ['pulse_beat', 'fluid_accumulation']."
        ),
    )
    default_camera: CameraConfig = Field(
        ...,
        description="Opening camera position and look-at target in model-space units.",
    )
    scale: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Uniform scale factor applied after GLB load to normalise model size. "
            "Adjust per model to fit the canvas without clipping."
        ),
    )

    @property
    def is_servable(self) -> bool:
        """
        Return True only if this entry passes both human-gated safety checks.

        Both conditions must hold simultaneously:
          1. `license_verified` is True  - a team member confirmed the license
             permits patient-facing deployment for this model.
          2. `clinical_review_status` is APPROVED - a clinician confirmed
             anatomical accuracy for the target condition.

        The resolver and the FastAPI config endpoint call this before returning
        a model_id to the engine. If False, the caller must return None so the
        engine renders its text-only fallback panel.

        This is a pure computed property of the entry's own fields. It never
        touches the filesystem or network, so it is safe to call anywhere.

        Returns:
            bool: True if the model may be served to patients, False otherwise.
        """
        return (
            self.license_verified
            and self.clinical_review_status == ClinicalReviewStatus.APPROVED
        )


class AnatomyRegistry(BaseModel):
    """
    The full parsed registry manifest.

    Wraps a list of validated RegistryEntry objects. The version field allows
    the engine to detect manifest format changes at startup.

    Attributes:
        version: Semver string for the manifest format, e.g. '1.0.0'.
                 Bump the minor version when adding fields; bump major when
                 removing or renaming fields.
        entries: All anatomy model entries defined in this manifest.
    """

    version: str = Field(
        ...,
        description="Semver manifest format version, e.g. '1.0.0'.",
    )
    entries: list[RegistryEntry]
