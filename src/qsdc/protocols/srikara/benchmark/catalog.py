"""Built-in studies: reference checks per workload, and parameter and noise studies per noise baseline."""

from __future__ import annotations

from qsdc.protocols.srikara.benchmark.benchmark import Benchmark, Case, Workload
from qsdc.protocols.srikara.config import (
    Channel,
    Detector,
    Fixed,
    Memory,
    NoiseConfig,
    SimulatorConfig,
    Uniform,
)

WORKLOADS = {
    "light": Workload(payload_bits=1024),
    "medium": Workload(payload_bits=10_000),
    "heavy": Workload(payload_bits=1_000_000),
}


def symmetric_noise(
    transmittance: float, nbar: float, efficiency: float, electronic_variance: float
) -> NoiseConfig:
    """The same channel in both directions and the same detector for Alice and Bob."""
    channel = Channel(transmittance=transmittance, nbar=nbar)
    detector = Detector(efficiency=efficiency, electronic_variance=electronic_variance)
    return NoiseConfig(
        forward=channel,
        backward=channel,
        alice_detector=detector,
        bob_detector=detector,
    )


NOISES = {
    "clean": NoiseConfig(),
    "low": symmetric_noise(0.98, 0.005, 0.95, 0.001),
    "medium": symmetric_noise(0.95, 0.01, 0.9, 0.002),
    "high": symmetric_noise(0.9, 0.02, 0.8, 0.004),
}

BASELINE = SimulatorConfig(
    backend="sf-sampled",
    squeeze_r=Fixed(value=0.576),
    theta_pi=Uniform(lower=0.0, upper=2.0),
    tolerance_sigmas=3.0,
    seed=33,
)
AXIS_OPTIMIZED = BASELINE.model_copy(update={"axis_policy": "optimized"})
INTERVALS_OPTIMIZED = AXIS_OPTIMIZED.model_copy(update={"intervals": "optimized_v12"})
# At theta = 5pi/4 Bob's unsqueezing amplifies Alice's q displacement by cosh r + sqrt(2) sinh r.
OPTIMIZED = INTERVALS_OPTIMIZED.model_copy(update={"theta_pi": Fixed(value=1.25)})
SECDED = OPTIMIZED.model_copy(update={"error_correction": "secded"})
RETRY = SECDED.model_copy(update={"max_attempts": 3})
OPTIMIZATION_STEPS = {
    "Default": BASELINE,
    "+ Axis optimization": AXIS_OPTIMIZED,
    "+ Optimized intervals": INTERVALS_OPTIMIZED,
    "+ Fixed theta = 5pi/4": OPTIMIZED,
    "+ SECDED error correction": SECDED,
    "+ Retries": RETRY,
}

R_VALUES = (0.115, 0.345, 0.576, 0.921, 1.151, 1.5)
R_RANGES = ((0.115, 0.345), (0.345, 0.576), (0.115, 1.151))
THETA_PI_VALUES = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75)
INTERVALS = ("default", "optimized_v4", "optimized_v8", "optimized_v12")
ERROR_CORRECTION = {
    "None": ("none", 1),
    "Parity": ("parity", 1),
    "Parity + retries": ("parity", 3),
    "SECDED": ("secded", 1),
    "SECDED + retries": ("secded", 3),
}
TOLERANCES = (1.0, 2.0, 3.0, 4.0, 5.0)
ONE_PROBABILITIES = (0.1, 0.25, 0.5, 0.75, 0.9)
TRANSMITTANCES = (1.0, 0.95, 0.9, 0.8, 0.7, 0.5)
NBARS = (0.0, 0.01, 0.05, 0.1, 0.2)
EFFICIENCIES = (1.0, 0.9, 0.8, 0.7, 0.5)
ELECTRONIC_VARIANCES = (0.0, 0.01, 0.05, 0.1, 0.2)
MEMORY_SECONDS = (0.0, 0.1, 0.25, 0.5, 1.0)


def reference_studies(workload: Workload) -> list[Benchmark]:
    return [
        Benchmark(
            "ideal_backend_check",
            tuple(
                Case(BASELINE.model_copy(update={"backend": backend}), workload)
                for backend in ("analytic", "sf")
            ),
        ),
        Benchmark("paper_baseline", (Case(BASELINE, workload),)),
        Benchmark(
            "noise_profiles",
            tuple(
                Case(OPTIMIZED.model_copy(update={"noise": noise}), workload, name)
                for name, noise in NOISES.items()
            ),
        ),
    ]


def noise_studies(noise_name: str, workload: Workload) -> list[Benchmark]:
    """Studies of the optimized simulator under one noise baseline; noise sweeps change one component."""
    noise = NOISES[noise_name]
    base = OPTIMIZED.model_copy(update={"noise": noise})

    def case(
        simulator: SimulatorConfig = base,
        workload: Workload = workload,
        series: str = noise_name,
        **plot: object,
    ) -> Case:
        return Case(simulator, workload, series, **plot)

    def vary(**changes: object) -> SimulatorConfig:
        return base.model_copy(update=changes)

    def vary_noise(**changes: object) -> SimulatorConfig:
        return vary(noise=noise.model_copy(update=changes))

    def channels(**changes: object) -> SimulatorConfig:
        return vary_noise(
            forward=noise.forward.model_copy(update=changes),
            backward=noise.backward.model_copy(update=changes),
        )

    def detectors(**changes: object) -> SimulatorConfig:
        return vary_noise(
            alice_detector=noise.alice_detector.model_copy(update=changes),
            bob_detector=noise.bob_detector.model_copy(update=changes),
        )

    squeeze_distributions = [Fixed(value=r) for r in R_VALUES] + [
        Uniform(lower=a, upper=b) for a, b in R_RANGES
    ]
    return [
        Benchmark(
            "squeezing_r",
            tuple(case(vary(squeeze_r=Fixed(value=r)), at=(r,)) for r in R_VALUES),
            axes=("Fixed squeezing r",),
        ),
        Benchmark(
            "squeezing_distributions",
            tuple(case(vary(squeeze_r=d)) for d in squeeze_distributions),
        ),
        Benchmark(
            "theta_fixed",
            tuple(
                case(vary(theta_pi=Fixed(value=t)), at=(t,)) for t in THETA_PI_VALUES
            ),
            axes=("Fixed theta / pi",),
        ),
        Benchmark(
            "r_theta_heatmap",
            tuple(
                case(vary(squeeze_r=Fixed(value=r), theta_pi=Fixed(value=t)), at=(r, t))
                for r in R_VALUES
                for t in THETA_PI_VALUES
            ),
            axes=("Fixed squeezing r", "Fixed theta / pi"),
        ),
        Benchmark(
            "optimization_comparison",
            tuple(
                case(step.model_copy(update={"noise": noise}), label=label)
                for label, step in OPTIMIZATION_STEPS.items()
            ),
        ),
        Benchmark(
            "axis_comparison",
            tuple(
                case(step.model_copy(update={"noise": noise}))
                for step in (BASELINE, AXIS_OPTIMIZED)
            ),
        ),
        Benchmark(
            "interval_comparison",
            tuple(case(vary(intervals=intervals)) for intervals in INTERVALS),
        ),
        Benchmark(
            "error_correction_comparison",
            tuple(
                case(vary(error_correction=code, max_attempts=attempts), label=label)
                for label, (code, attempts) in ERROR_CORRECTION.items()
            ),
        ),
        Benchmark(
            "tolerance_safety",
            tuple(case(vary(tolerance_sigmas=t), at=(t,)) for t in TOLERANCES),
            axes=("Check tolerance (sigma)",),
        ),
        Benchmark(
            "one_probability",
            tuple(
                case(
                    workload=workload.model_copy(update={"one_probability": p}), at=(p,)
                )
                for p in ONE_PROBABILITIES
            ),
            axes=("Probability of one",),
        ),
        Benchmark(
            "channel_transmittance",
            tuple(case(channels(transmittance=t), at=(t,)) for t in TRANSMITTANCES),
            axes=("Transmittance per path",),
        ),
        Benchmark(
            "thermal_occupation",
            tuple(case(channels(nbar=n), at=(n,)) for n in NBARS),
            axes=("Environment nbar",),
        ),
        Benchmark(
            "detector_efficiency",
            tuple(case(detectors(efficiency=e), at=(e,)) for e in EFFICIENCIES),
            axes=("Detector efficiency",),
        ),
        Benchmark(
            "electronic_noise",
            tuple(
                case(detectors(electronic_variance=v), at=(v,))
                for v in ELECTRONIC_VARIANCES
            ),
            axes=("Electronic variance (SNU)",),
        ),
        Benchmark(
            "memory_delay",
            tuple(
                case(vary_noise(memory=Memory(seconds=s, nbar=0.01)), at=(s,))
                for s in MEMORY_SECONDS
            ),
            axes=("Memory duration (s)",),
        ),
    ]
