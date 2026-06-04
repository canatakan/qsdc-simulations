"""Programmatic API for Srikara benchmark runs."""

from srikara.benchmark.config import BenchmarkConfig, load_benchmark_config
from srikara.benchmark.engine import BenchmarkReport, run_benchmark

__all__ = [
    "BenchmarkConfig",
    "BenchmarkReport",
    "load_benchmark_config",
    "run_benchmark",
]
