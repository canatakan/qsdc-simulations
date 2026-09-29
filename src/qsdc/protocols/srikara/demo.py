"""`srikara-demo NAME [options]`: run one of the scripts in demos/srikara/ of this checkout."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parents[4] / "demos" / "srikara"
HELPERS = {"walkthrough"}


def main() -> None:
    names = sorted(path.stem for path in DEMOS.glob("*.py") if path.stem not in HELPERS)
    if len(sys.argv) < 2 or sys.argv[1] not in names:
        print(f"usage: srikara-demo {{{','.join(names)}}} [options]")
        print("       srikara-demo NAME --help   shows the options of one demo")
        sys.exit(2)
    script = DEMOS / f"{sys.argv[1]}.py"
    sys.argv = [str(script), *sys.argv[2:]]
    sys.path.insert(0, str(DEMOS))
    runpy.run_path(str(script), run_name="__main__")
