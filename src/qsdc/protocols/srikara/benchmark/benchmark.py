from __future__ import annotations

from dataclasses import dataclass
from math import nan, sqrt
from statistics import fmean
from time import perf_counter

from scipy.stats import t

from qsdc.common.config.base import Config, Fraction, PositiveInt
from qsdc.common.random import ClassicalRandomSource, derive_seed, weighted_random_bits
from qsdc.protocols.srikara.benchmark.metrics import RunMetrics, measure, pool
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import Simulator


class Workload(Config):
    payload_bits: PositiveInt = 10_000
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
        reps = self.repetitions
        if len(reps) < 2:
            return nan
        values = [
            getattr(pool(reps[:i] + reps[i + 1 :]), metric) for i in range(len(reps))
        ]
        values = [value for value in values if value is not None]
        n = len(values)
        if n < 2:
            return nan
        mean = fmean(values)
        error = sqrt((n - 1) / n * sum((value - mean) ** 2 for value in values))
        return t.ppf((1 + confidence) / 2, n - 1) * error


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
            transmission = Simulator(simulator).transmit(payloads[workload])
            samples.append(measure(transmission, perf_counter() - case_started))
        runs.append(RunResult(case, pool(samples), tuple(samples)))
    return BenchmarkResult(benchmark, tuple(runs), perf_counter() - started)
