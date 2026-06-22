"""
Package: frontend/explainer/registry
Description: Public interface for the DischargeIQ anatomy model registry.

Exports the schema types needed by downstream consumers and the load_registry
entry point. Import from here rather than from schema.py or loader.py directly
so internal module names remain an implementation detail.

Usage:
    from frontend.explainer.registry import load_registry, RegistryStore
    store = load_registry()          # call once at startup, cache the result
    entry = store.lookup_by_id("cardiovascular.heart_failure")
    entry = store.lookup_by_condition_key("heart failure")
"""

from .loader import RegistryStore, load_registry
from .schema import (
    AnatomyRegistry,
    BodySystem,
    CameraConfig,
    ClinicalReviewStatus,
    RegistryEntry,
)

__all__ = [
    "load_registry",
    "RegistryStore",
    "AnatomyRegistry",
    "BodySystem",
    "CameraConfig",
    "ClinicalReviewStatus",
    "RegistryEntry",
]
