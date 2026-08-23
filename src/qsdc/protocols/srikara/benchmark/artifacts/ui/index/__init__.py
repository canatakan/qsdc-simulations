"""Generate the browsable index for a collection of benchmark runs."""

from __future__ import annotations

from pathlib import Path

from ..rendering import copy_asset, render_template
from .data import load_runs
from .view import build_index_context

__all__ = ["write_benchmark_index"]


def write_benchmark_index(results_dir: str | Path) -> str:
    """Discover benchmark runs and write their browsable static index."""
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    copy_asset("index.css", root / "index.css")
    index_path = root / "index.html"
    index_path.write_text(
        render_template("index.html", **build_index_context(root, load_runs(root))),
        encoding="utf-8",
    )
    return str(index_path)
