from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .benchmark import Workload, run_benchmark
from .report.report import rerender, write_index, write_report
from .studies.cao.suite import CAO
from .studies.catalog import Catalog
from .studies.srikara.suite import SRIKARA
from .suite import Suite


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="benchmark", description="Run QSDC benchmarks."
    )
    protocols = parser.add_subparsers(dest="protocol", required=True)
    suites = {suite.name: suite for suite in (SRIKARA, CAO)}
    for suite in suites.values():
        protocol = protocols.add_parser(suite.name, help=f"{suite.title} benchmarks")
        add_commands(protocol, suite)

    args = parser.parse_args(argv)
    suite = suites[args.protocol]
    catalog = Catalog(suite)

    if args.command == "list":
        list_studies(catalog, Workload())
    elif args.command == "run":
        run_studies(suite, catalog, args)
    elif args.command == "rerender":
        rerender_reports(suite, args.output_root)
    elif args.command == "index":
        rebuild_index(suite, args.output_root)


def add_commands(parser: argparse.ArgumentParser, suite: Suite) -> None:
    catalog = Catalog(suite)
    default = Workload()

    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the built-in studies")

    run = commands.add_parser("run", help="run studies into <output-root>/<study>/")
    run.add_argument(
        "--study",
        action="append",
        choices=catalog.names,
        help="repeatable; default: all",
    )
    run.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="independent seeds per case, pooled into each result (default: 1)",
    )
    run.add_argument(
        "--payload-bits",
        type=int,
        default=default.payload_bits,
        help=f"random payload bits per case (default: {default.payload_bits})",
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
        command.add_argument(
            "--output-root",
            type=Path,
            default=suite.output_root,
            help=f"default: {suite.output_root}",
        )


def list_studies(catalog: Catalog, workload: Workload) -> None:
    for study in catalog.studies(workload):
        print(f"{study.name:28} {study.layout:11} {len(study.cases)} runs")


def run_studies(suite: Suite, catalog: Catalog, args: argparse.Namespace) -> None:
    workload = Workload(payload_bits=args.payload_bits)
    for study in catalog.studies(workload):
        if args.study and study.name not in args.study:
            continue
        done = any((args.output_root / study.name).glob("run_*/results.json"))
        if args.skip_existing and done:
            print(f"{study.name}: already done")
            continue

        print(study.name)
        report = write_report(run_benchmark(study, args.repetitions), args.output_root)
        print(f"  {report / 'report.html'}")

    rebuild_index(suite, args.output_root)


def rerender_reports(suite: Suite, output_root: Path) -> None:
    for results in sorted(output_root.rglob("results.json")):
        rerender(results, suite)
        print(f"Rerendered {results.parent / 'report.html'}")

    rebuild_index(suite, output_root)


def rebuild_index(suite: Suite, output_root: Path) -> None:
    print(f"Index: {write_index(output_root, suite)}")
