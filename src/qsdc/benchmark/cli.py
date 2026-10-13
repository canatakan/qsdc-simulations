from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .benchmark import Workload, run_benchmark
from .catalog import Catalog
from .report import rerender, write_index, write_report
from .suite import Suite

WORKLOAD = Workload()


def main(suite: Suite, argv: Sequence[str] | None = None) -> None:
    studies = Catalog(suite).studies(WORKLOAD)

    parser = argparse.ArgumentParser(
        description=f"Run the built-in {suite.title} benchmark studies and write "
        "their reports."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the built-in studies")

    run = commands.add_parser("run", help="run studies into <output-root>/<study>/")
    run.add_argument(
        "--study",
        action="append",
        choices=[study.name for study in studies],
        help="repeatable; default: all",
    )
    run.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="independent seeds per case, pooled into each result (default: 1)",
    )
    run.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip studies that already have a report, e.g. to resume a run",
    )

    index = commands.add_parser("index", help="rebuild <output-root>/index.html")
    rerender_parser = commands.add_parser(
        "rerender",
        help="rebuild every report's plots, CSV and HTML from its results.json",
    )
    for command in (run, index, rerender_parser):
        command.add_argument("--output-root", type=Path, default=suite.output_root)

    args = parser.parse_args(argv)

    if args.command == "list":
        for study in studies:
            print(f"{study.name:28} {study.layout:11} {len(study.cases)} runs")
        return

    if args.command == "run":
        for study in studies:
            if args.study and study.name not in args.study:
                continue
            done = any((args.output_root / study.name).glob("run_*/results.json"))
            if args.skip_existing and done:
                print(f"{study.name}: already done")
                continue

            print(study.name)
            report = write_report(
                run_benchmark(study, args.repetitions), args.output_root
            )
            print(f"  {report / 'report.html'}")

    if args.command == "rerender":
        for results in sorted(args.output_root.rglob("results.json")):
            rerender(results, suite)
            print(f"Rerendered {results.parent / 'report.html'}")

    print(f"Index: {write_index(args.output_root, suite)}")
