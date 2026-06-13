"""Shared static UI template helpers."""

from __future__ import annotations

from importlib.resources import files


def read_template(name: str) -> str:
    return files(__package__).joinpath(name).read_text(encoding="utf-8")
