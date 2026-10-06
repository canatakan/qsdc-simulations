"""Run the built-in Srikara benchmark studies and write their reports."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from qsdc.protocols.srikara.benchmark.benchmark import run_benchmark
from qsdc.protocols.srikara.benchmark.catalog import WORKLOADS, studies
from qsdc.protocols.srikara.benchmark.report import (
    rerender,
    write_index,
    write_report,
)

STUDIES = studies(WORKLOADS["light"])


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the built-in studies")
    run = commands.add_parser("run", help="run studies into <output-root>/<workload>/")
    run.add_argument(
        "--study",
        action="append",
        choices=[study.name for study in STUDIES],
        help="repeatable; default: all",
    )
    run.add_argument(
        "--workload",
        nargs="+",
        choices=list(WORKLOADS),
        default=["medium"],
        help="default: medium",
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
        command.add_argument("--output-root", type=Path, default=Path("results"))
    args = parser.parse_args(argv)

    if args.command == "list":
        for study in STUDIES:
            print(f"{study.name:28} {study.layout:11} {len(study.cases)} runs")
        return

    if args.command == "run":
        for workload_name in args.workload:
            root = args.output_root / workload_name
            for study in studies(WORKLOADS[workload_name]):
                if args.study and study.name not in args.study:
                    continue
                done = any((root / study.name).glob("run_*/results.json"))
                if args.skip_existing and done:
                    print(f"{workload_name}/{study.name}: already done")
                    continue
                print(f"{workload_name}/{study.name}")
                report = write_report(run_benchmark(study, args.repetitions), root)
                print(f"  {report / 'report.html'}")
    if args.command == "rerender":
        for results in sorted(args.output_root.rglob("results.json")):
            rerender(results)
            print(f"Rerendered {results.parent / 'report.html'}")
    print(f"Index: {write_index(args.output_root)}")


if __name__ == "__main__":
    main()
