"""
File: frontend/explainer/registry/loader.py
Component: Anatomy Explainer - Registry Loader
Description: Reads anatomy_registry.json from disk, validates every entry
  against the Pydantic v2 schema, builds id and condition-key indexes, and
  exposes a RegistryStore with O(1) lookups. This is the single gate through
  which all registry data must pass; nothing reaches the engine unvalidated.

Key public API:
  load_registry(manifest_path) -> RegistryStore   - call once at startup, cache result
  RegistryStore.lookup_by_id(id) -> RegistryEntry | None
  RegistryStore.lookup_by_condition_key(key) -> RegistryEntry | None

Dependencies:
  - schema.py in this package (AnatomyRegistry, RegistryEntry)
  - anatomy_registry.json in this package (default manifest path)
  - pydantic>=2.0.0, json (stdlib), pathlib (stdlib)

Consumed by:
  - dischargeiq/agents/anatomy_resolver.py (diagnosis → registry id)
  - dischargeiq/main.py (explainer config endpoint)

Do NOT call load_registry() on every request. Cache the returned RegistryStore
at module or app startup (e.g. in a FastAPI lifespan handler).
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from .schema import AnatomyRegistry, RegistryEntry

logger = logging.getLogger(__name__)

# Absolute path to the manifest shipped alongside this module.
_MANIFEST_DEFAULT = Path(__file__).parent / "anatomy_registry.json"


def _read_raw_manifest(manifest_path: Path) -> dict:
    """
    Open anatomy_registry.json and return its parsed content as a plain dict.

    Wraps file I/O so callers do not need to handle open() errors directly.
    Logs the error before re-raising so the caller has context in the log.

    Args:
        manifest_path: Absolute or relative path to the JSON manifest file.

    Returns:
        dict: Parsed JSON content before any schema validation.

    Raises:
        FileNotFoundError: If no file exists at manifest_path.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.error("Registry manifest not found: %s", manifest_path)
        raise
    except json.JSONDecodeError as exc:
        logger.error(
            "Registry manifest at %s contains invalid JSON: %s",
            manifest_path,
            exc,
        )
        raise


def _validate_manifest(raw: dict) -> AnatomyRegistry:
    """
    Run the raw manifest dict through the AnatomyRegistry Pydantic schema.

    Logs the full validation error detail before re-raising so the team can
    identify which entry failed and why without reading raw tracebacks.

    Args:
        raw: Plain dict returned by _read_raw_manifest.

    Returns:
        AnatomyRegistry: Fully validated registry object.

    Raises:
        pydantic.ValidationError: If any field in any entry fails validation.
    """
    try:
        return AnatomyRegistry.model_validate(raw)
    except ValidationError as exc:
        logger.error(
            "Registry manifest failed schema validation - %d error(s):\n%s",
            exc.error_count(),
            exc,
        )
        raise


def _build_id_index(entries: list[RegistryEntry]) -> dict[str, RegistryEntry]:
    """
    Build a dict keyed by entry.id for O(1) id-based lookups.

    Raises ValueError immediately on a duplicate id. A duplicate id is a data
    error - two entries cannot share a stable identifier - so silently keeping
    one would hide a broken manifest. Fail-fast here forces the author to fix
    the manifest before any code can run against it.

    Args:
        entries: Validated list of RegistryEntry objects from the manifest.

    Returns:
        dict[str, RegistryEntry]: Mapping from id string to RegistryEntry.

    Raises:
        ValueError: If two entries share the same id string.
    """
    index: dict[str, RegistryEntry] = {}
    for entry in entries:
        if entry.id in index:
            raise ValueError(
                f"Registry manifest contains duplicate id '{entry.id}'. "
                "Each entry must have a unique stable id. Fix anatomy_registry.json."
            )
        index[entry.id] = entry
    return index


def _build_condition_index(entries: list[RegistryEntry]) -> dict[str, RegistryEntry]:
    """
    Build a dict keyed by normalised condition_key for O(1) condition lookups.

    Each entry may declare multiple condition_keys (synonyms). All are indexed.
    Normalisation: strip whitespace, lowercase. If two entries share a key the
    second overwrites the first and a warning is logged - duplicate keys signal
    an authoring error that a human must resolve.

    Args:
        entries: Validated list of RegistryEntry objects from the manifest.

    Returns:
        dict[str, RegistryEntry]: Mapping from normalised key to RegistryEntry.
    """
    index: dict[str, RegistryEntry] = {}
    for entry in entries:
        for key in entry.condition_keys:
            normalised = key.strip().lower()
            if normalised in index:
                logger.warning(
                    "Duplicate condition_key '%s' in entries '%s' and '%s'. "
                    "Second entry ('%s') overwrites first. Resolve in registry.",
                    normalised,
                    index[normalised].id,
                    entry.id,
                    entry.id,
                )
            index[normalised] = entry
    return index


class RegistryStore:
    """
    Parsed, validated, and indexed registry ready for synchronous lookups.

    Construct via load_registry(), not directly. Cache at app startup.

    Attributes:
        registry:          The validated AnatomyRegistry object (all entries).
        _by_id:            Internal id-keyed index.
        _by_condition_key: Internal condition-key-keyed index.
    """

    def __init__(
        self,
        registry: AnatomyRegistry,
        by_id: dict[str, RegistryEntry],
        by_condition_key: dict[str, RegistryEntry],
    ) -> None:
        """
        Initialise the store with pre-built indexes.

        Direct construction is allowed but prefer load_registry() which
        performs file I/O, validation, and index building in the correct order.

        Args:
            registry:          Validated AnatomyRegistry object.
            by_id:             Pre-built id index from _build_id_index.
            by_condition_key:  Pre-built condition index from _build_condition_index.
        """
        self.registry = registry
        self._by_id = by_id
        self._by_condition_key = by_condition_key

    def lookup_by_id(self, entry_id: str) -> Optional[RegistryEntry]:
        """
        Return the RegistryEntry for the given stable id, or None if absent.

        Does not raise on a miss; callers treat None as "no model available."

        Args:
            entry_id: Dot-namespaced id string, e.g. 'cardiovascular.heart_failure'.

        Returns:
            RegistryEntry if found, else None.
        """
        return self._by_id.get(entry_id)

    def lookup_by_condition_key(self, condition_key: str) -> Optional[RegistryEntry]:
        """
        Return the RegistryEntry whose condition_keys list contains the given key.

        Normalises the input to lowercase with stripped whitespace before lookup,
        matching the normalisation applied at index-build time.

        Does not raise on a miss; callers treat None as "no model available."

        Args:
            condition_key: Discharge diagnosis string, e.g. 'heart failure'.
                           Case and leading/trailing whitespace are ignored.

        Returns:
            RegistryEntry if a condition_key matches, else None.
        """
        return self._by_condition_key.get(condition_key.strip().lower())

    def all_entries(self) -> list[RegistryEntry]:
        """
        Return all registry entries in manifest order.

        Useful for admin tooling and test assertions. Not used in hot paths.

        Returns:
            list[RegistryEntry]: All entries from the loaded manifest.
        """
        return list(self.registry.entries)


def load_registry(manifest_path: Path = _MANIFEST_DEFAULT) -> RegistryStore:
    """
    Read, validate, and index the anatomy registry manifest from disk.

    This is the primary public entry point. The result is a RegistryStore
    ready for lookups. Callers must cache the result - do not call this
    function on every request, as it performs file I/O and full Pydantic
    validation on every invocation.

    Typical usage at FastAPI startup:
        _registry_store = load_registry()  # cached module-level singleton

    Args:
        manifest_path: Path to anatomy_registry.json. Defaults to the manifest
                       bundled alongside this module. Override in tests.

    Returns:
        RegistryStore: Parsed, validated, and indexed registry.

    Raises:
        FileNotFoundError:       If the manifest file is missing.
        json.JSONDecodeError:    If the manifest is malformed JSON.
        pydantic.ValidationError: If any entry fails schema validation.
    """
    raw = _read_raw_manifest(manifest_path)
    registry = _validate_manifest(raw)
    by_id = _build_id_index(registry.entries)
    by_condition_key = _build_condition_index(registry.entries)
    logger.info(
        "Anatomy registry loaded: %d entries, manifest v%s, source: %s.",
        len(registry.entries),
        registry.version,
        manifest_path,
    )
    return RegistryStore(
        registry=registry,
        by_id=by_id,
        by_condition_key=by_condition_key,
    )
