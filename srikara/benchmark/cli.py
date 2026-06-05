"""Command-line interface for Srikara benchmark runs."""

from __future__ import annotations

import argparse

from srikara.benchmark.config import load_benchmark_config
from srikara.benchmark.engine import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path")
    parser.add_argument("--output", dest="output_dir", default=None)
    args = parser.parse_args()

    config = load_benchmark_config(args.config_path)
    report = run_benchmark(config, output_dir=args.output_dir, progress=True)
    print(
        "Benchmark complete: "
        f"{report.summary['trial_count']} trials across "
        f"{report.summary['combo_count']} combos, "
        f"accepted_rate={report.summary['accepted_rate']:.3f}"
    )
    print(f"Artifacts written to {report.output_dir}")


if __name__ == "__main__":
    main()
