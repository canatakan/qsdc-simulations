"""Run Srikara benchmark configs."""

from __future__ import annotations

import argparse
from pathlib import Path

from qsdc.common.random import make_random_source
from qsdc.protocols.srikara.benchmark.artifacts.ui.index import write_benchmark_index
from qsdc.protocols.srikara.benchmark.config import load_benchmark_config
from qsdc.protocols.srikara.benchmark.engine import run_benchmark
from qsdc.protocols.srikara.simulator.backends import make_backend


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        default="configs",
        help="directory containing benchmark JSON configs",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=None,
        help="config name or path to run; can be passed more than once",
    )
    parser.add_argument(
        "--output-root",
        default="results",
        help="directory where per-config result folders are written",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip configs that already have a run under the output root",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="continue running remaining configs if one config fails",
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    output_root = Path(args.output_root)
    selected_configs = tuple(args.config or ())
    config_paths = _config_paths(config_dir, selected_configs)
    if not config_paths:
        raise SystemExit(f"No benchmark configs found in {config_dir}")

    output_root.mkdir(parents=True, exist_ok=True)
    failures = []
    for index, config_path in enumerate(config_paths, start=1):
        config = load_benchmark_config(config_path)
        config_output_dir = output_root / config.name
        print(f"[{index}/{len(config_paths)}] {config.name}: {config_path}")
        if args.skip_existing and _has_existing_run(config_output_dir):
            print(f"Skipping existing results in {config_output_dir}")
            continue
        try:
            report = run_benchmark(
                config.with_output_dir(str(config_output_dir)),
                progress=True,
                backend_factory=make_backend,
                random_source_factory=make_random_source,
            )
        except Exception as error:
            if not args.keep_going:
                raise
            failures.append((config_path, error))
            print(f"Failed {config_path}: {error}")
            continue
        print(f"Artifacts written to {report.output_dir}")

    index_path = write_benchmark_index(output_root)
    print(f"Generated benchmark index at {index_path}")
    if failures:
        print(f"{len(failures)} config(s) failed:")
        for config_path, error in failures:
            print(f"- {config_path}: {error}")
        raise SystemExit(1)


def _config_paths(config_dir: Path, selected_configs: tuple[str, ...]) -> list[Path]:
    if not config_dir.exists():
        raise SystemExit(f"Config directory does not exist: {config_dir}")
    if not selected_configs:
        return sorted(config_dir.rglob("*.json"))
    paths: list[Path] = []
    for selected in selected_configs:
        paths.extend(_resolve_config_paths(config_dir, selected))
    return paths


def _resolve_config_paths(config_dir: Path, selected_config: str) -> list[Path]:
    path = Path(selected_config)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(config_dir / path)
        if path.suffix != ".json":
            candidates.append(config_dir / f"{selected_config}.json")
    elif path.suffix != ".json":
        candidates.append(path.with_suffix(".json"))

    for candidate in candidates:
        if candidate.is_file():
            return [candidate]
        if candidate.is_dir():
            return sorted(candidate.rglob("*.json"))

    matches: list[Path] = []
    if not path.is_absolute() and path.suffix != ".json":
        matches = sorted(config_dir.rglob(f"{selected_config}.json"))
    if len(matches) == 1:
        return matches
    if len(matches) > 1:
        joined = ", ".join(str(match) for match in matches)
        raise SystemExit(f"Config name is ambiguous: {selected_config} ({joined})")

    tried = ", ".join(str(candidate) for candidate in candidates)
    raise SystemExit(f"Config not found: {selected_config} (tried {tried})")


def _has_existing_run(config_output_dir: Path) -> bool:
    return any(config_output_dir.glob("run_*/benchmark.json"))


if __name__ == "__main__":
    main()
