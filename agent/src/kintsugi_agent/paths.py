"""Shared path-component validation for retained agent artifacts."""

from __future__ import annotations

import re


def require_safe_directory_name(value: str, *, field: str) -> str:
    """Return one safe path component or reject traversal and nested paths."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError(f"{field} must be a safe single directory name")
    return value
