"""Run Srikara benchmark configs."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from qsdc.protocols.srikara.benchmark.artifacts.ui.index import write_benchmark_index
from qsdc.protocols.srikara.benchmark.engine import run_benchmark
from qsdc.protocols.srikara.configuration.benchmark import BenchmarkConfig


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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="number of benchmark configs to run at once",
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    output_root = Path(args.output_root)
    selected_configs = tuple(args.config or ())
    config_paths = _config_paths(config_dir, selected_configs)
    if not config_paths:
        raise SystemExit(f"No benchmark configs found in {config_dir}")

    output_root.mkdir(parents=True, exist_ok=True)
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")

    if args.workers == 1:
        failures = _run_sequential(
            config_paths,
            output_root,
            skip_existing=args.skip_existing,
            keep_going=args.keep_going,
        )
    else:
        failures = _run_parallel(
            config_paths,
            output_root,
            workers=args.workers,
            skip_existing=args.skip_existing,
            keep_going=args.keep_going,
        )

    index_path = write_benchmark_index(output_root)
    print(f"Generated benchmark index at {index_path}")
    if failures:
        print(f"{len(failures)} config(s) failed:")
        for config_path, error in failures:
            print(f"- {config_path}: {error}")
        raise SystemExit(1)


def _run_sequential(
    config_paths: list[Path],
    output_root: Path,
    skip_existing: bool,
    keep_going: bool,
) -> list[tuple[Path, BaseException]]:
    failures = []
    for index, config_path in enumerate(config_paths, start=1):
        config = BenchmarkConfig.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )
        config_output_dir = output_root / config.name
        print(f"[{index}/{len(config_paths)}] {config.name}: {config_path}")
        if skip_existing and _has_existing_run(config_output_dir):
            print(f"Skipping existing results in {config_output_dir}")
            continue
        try:
            report = run_benchmark(
                config.with_output_dir(str(config_output_dir)),
                progress=True,
            )
        except Exception as error:
            if not keep_going:
                raise
            failures.append((config_path, error))
            print(f"Failed {config_path}: {error}")
            continue
        print(f"Artifacts written to {report.output_dir}")
    return failures


def _run_parallel(
    config_paths: list[Path],
    output_root: Path,
    workers: int,
    skip_existing: bool,
    keep_going: bool,
) -> list[tuple[Path, BaseException]]:
    failures = []
    print(f"Running {len(config_paths)} config(s) with {workers} worker(s)")
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_config_path,
                config_path,
                output_root,
                skip_existing,
            ): (index, config_path)
            for index, config_path in enumerate(config_paths, start=1)
        }
        for future in as_completed(futures):
            index, config_path = futures[future]
            try:
                result = future.result()
            except Exception as error:
                if not keep_going:
                    raise
                failures.append((config_path, error))
                print(f"[{index}/{len(config_paths)}] Failed {config_path}: {error}")
                continue

            action = "Skipped" if result["skipped"] else "Artifacts written to"
            print(
                f"[{index}/{len(config_paths)}] {result['name']}: "
                f"{action} {result['output_dir']}"
            )
    return failures


def _run_config_path(
    config_path: Path,
    output_root: Path,
    skip_existing: bool,
) -> dict[str, Any]:
    config = BenchmarkConfig.model_validate_json(
        config_path.read_text(encoding="utf-8")
    )
    config_output_dir = output_root / config.name
    if skip_existing and _has_existing_run(config_output_dir):
        return {
            "name": config.name,
            "output_dir": str(config_output_dir),
            "skipped": True,
        }

    report = run_benchmark(
        config.with_output_dir(str(config_output_dir)),
        progress=False,
    )
    return {
        "name": config.name,
        "output_dir": report.output_dir,
        "skipped": False,
    }


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
