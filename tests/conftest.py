"""
Pytest configuration for ``tests/`` at repo root.

``tests/manual/`` holds real API/DB smoke scripts; they are excluded from
collection when running ``pytest tests/``.
"""

collect_ignore = [
    "manual/test_claude_api.py",
    "manual/test_neon_db.py",
]
