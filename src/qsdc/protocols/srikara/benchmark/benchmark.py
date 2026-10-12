from __future__ import annotations

from dataclasses import dataclass
from math import nan, sqrt
from statistics import stdev
from time import perf_counter
from typing import Annotated

from pydantic import Field
from scipy.stats import t

from qsdc.common.random import ClassicalRandomSource, derive_seed, weighted_random_bits
from qsdc.protocols.srikara.benchmark.metrics import RunMetrics, measure, pool
from qsdc.protocols.srikara.config import Config, Fraction, SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator


class Workload(Config):
    payload_bits: Annotated[int, Field(ge=1)] = 10_000
    one_probability: Fraction = 0.5
    seed: int = 33

    def payload(self) -> str:
        return weighted_random_bits(
            self.payload_bits, self.one_probability, ClassicalRandomSource(self.seed)
        )


@dataclass(frozen=True)
class Case:
    simulator: SimulatorConfig
    workload: Workload
    series: str = "default"
    label: str | None = None
    at: tuple[float, ...] = ()


LAYOUTS = ("comparison", "sweep", "heatmap")


@dataclass(frozen=True)
class Benchmark:
    name: str
    cases: tuple[Case, ...]
    axes: tuple[str, ...] = ()

    @property
    def layout(self) -> str:
        return LAYOUTS[len(self.axes)]


@dataclass(frozen=True)
class RunResult:
    case: Case
    metrics: RunMetrics
    repetitions: tuple[RunMetrics, ...]

    def interval(self, metric: str, confidence: float = 0.95) -> float:
        values = [getattr(m, metric) for m in self.repetitions]
        values = [value for value in values if value is not None]
        if len(values) < 2:
            return nan
        quantile = t.ppf((1 + confidence) / 2, len(values) - 1)
        return quantile * stdev(values) / sqrt(len(values))


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark: Benchmark
    runs: tuple[RunResult, ...]
    seconds: float


def run_benchmark(benchmark: Benchmark, repetitions: int = 1) -> BenchmarkResult:
    started = perf_counter()
    payloads: dict[Workload, str] = {}
    runs = []
    for case in benchmark.cases:
        samples = []
        for repetition in range(repetitions):
            simulator, workload = case.simulator, case.workload
            if repetition:
                simulator = simulator.model_copy(
                    update={
                        "seed": derive_seed(simulator.seed, "repetition", repetition)
                    }
                )
                workload = workload.model_copy(
                    update={
                        "seed": derive_seed(workload.seed, "repetition", repetition)
                    }
                )
            if workload not in payloads:
                payloads[workload] = workload.payload()
            case_started = perf_counter()
            transmission = SrikaraSimulator(simulator).transmit(payloads[workload])
            samples.append(measure(transmission, perf_counter() - case_started))
        runs.append(RunResult(case, pool(samples), tuple(samples)))
    return BenchmarkResult(benchmark, tuple(runs), perf_counter() - started)
