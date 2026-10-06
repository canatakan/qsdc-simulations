"""Benchmark studies: cases that each transmit one payload, arranged along zero to two axes."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from qsdc.common.bits import weighted_random_bits
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.common.random.seed import derive_seed
from qsdc.protocols.srikara.benchmark.metrics import RunMetrics, measure, pool
from qsdc.protocols.srikara.config import Config, SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator


class Workload(Config):
    payload_bits: int = 1024
    one_probability: float = 0.5
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
    at: tuple[float, ...] = ()  # coordinates on the benchmark's axes


LAYOUTS = ("comparison", "sweep", "heatmap")


@dataclass(frozen=True)
class Benchmark:
    """Cases drawn along the named axes: none for a comparison, one for a sweep, two for a heatmap."""

    name: str
    cases: tuple[Case, ...]
    axes: tuple[str, ...] = ()

    @property
    def layout(self) -> str:
        return LAYOUTS[len(self.axes)]


@dataclass(frozen=True)
class RunResult:
    case: Case
    metrics: RunMetrics  # pooled over repetitions
    repetitions: tuple[RunMetrics, ...]


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark: Benchmark
    runs: tuple[RunResult, ...]
    seconds: float


def run_benchmark(benchmark: Benchmark, repetitions: int = 1) -> BenchmarkResult:
    """Transmit every case `repetitions` times with independent seeds.

    Repetition 0 uses the configured seeds. Within a repetition, cases with the same workload
    send the same payload.
    """
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
