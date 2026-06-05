"""Command-line interface for Srikara benchmark runs."""

from __future__ import annotations

import argparse

from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.common.random.sf_beamsplitter import SFBeamSplitterQRNG
from qsdc.protocols.srikara.benchmark.config import load_benchmark_config
from qsdc.protocols.srikara.benchmark.engine import run_benchmark
from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.ideal import SFBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.sampled import (
    SFSampledBackend,
)


def make_backend(name):
    if name == "analytic":
        return AnalyticBackend()
    if name == "sf":
        return SFBackend()
    if name == "sf-sampled":
        return SFSampledBackend()
    raise ValueError(f"unknown backend {name!r}")


def make_random_source(name, seed):
    if name == "classical":
        return ClassicalRandomSource(seed)
    if name == "sf-bs-qrng":
        return SFBeamSplitterQRNG(seed=seed)
    raise ValueError(f"unknown random source {name!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path")
    parser.add_argument("--output", dest="output_dir", default=None)
    args = parser.parse_args()

    config = load_benchmark_config(args.config_path)
    report = run_benchmark(
        config,
        output_dir=args.output_dir,
        progress=True,
        backend_factory=make_backend,
        random_source_factory=make_random_source,
    )
    print(
        "Benchmark complete: "
        f"{report.summary['trial_count']} trials across "
        f"{report.summary['combo_count']} combos, "
        f"accepted_rate={report.summary['accepted_rate']:.3f}"
    )
    print(f"Artifacts written to {report.output_dir}")


if __name__ == "__main__":
    main()
