"""Generate the static multi-run benchmark index."""

from __future__ import annotations

import argparse
from pathlib import Path

from qsdc.protocols.srikara.benchmark.artifacts.ui import copy_asset, render_template
from qsdc.protocols.srikara.benchmark.artifacts.ui.utils.index_data import find_runs
from qsdc.protocols.srikara.benchmark.artifacts.ui.utils.index_view import (
    build_index_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        help="directory containing benchmark run folders",
    )
    args = parser.parse_args()
    print(f"Generated benchmark UI at {write_benchmark_index(args.results_dir)}")


def write_benchmark_index(results_dir: str | Path) -> str:
    """Discover benchmark runs and write their browsable static index."""
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    copy_asset("index.css", root / "index.css")
    (root / "index.html").write_text(
        render_template("index.html", **build_index_context(root, find_runs(root))),
        encoding="utf-8",
    )
    return str(root / "index.html")


if __name__ == "__main__":
    main()
