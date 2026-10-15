from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from qsdc.common.coding.bits import hamming_distance
from qsdc.common.transmission import Transmission
from qsdc.protocols.srikara.config import NOISES, PRESETS, SimulatorConfig
from qsdc.protocols.srikara.constants import INTERVAL_CODES
from qsdc.protocols.srikara.simulator.protocol import Simulator

from ... import cli
from ...metrics import RunMetrics, count_blocks, count_symbols
from ...suite import Suite


class SrikaraSuite(Suite):
    name = "srikara"
    config = SimulatorConfig
    presets = PRESETS
    noises = NOISES
    studies = Path(__file__).with_name("studies.yaml")
    output_root = Path(__file__).parents[2] / "results" / "srikara"

    def simulate(self, config: SimulatorConfig, payload: str) -> Transmission:
        return Simulator(config).transmit(payload)

    def measure(
        self, config: SimulatorConfig, transmission: Transmission, seconds: float
    ) -> RunMetrics:
        attempts = transmission.attempts
        messages = [m for run in transmission.runs for m in run.messages]
        checks = [c for attempt in attempts for c in attempt.controls + attempt.decoys]
        symbols = [(m.sent_bits, m.decoded_bits) for m in messages]

        return RunMetrics(
            **count_blocks(transmission),
            raw_bits=3 * len(messages),
            raw_error_bits=sum(
                hamming_distance(sent, decoded) for sent, decoded in symbols
            ),
            states=sum(len(attempt.states) for attempt in attempts),
            checks=len(checks),
            failed_checks=sum(not check.passed for check in checks),
            seconds=seconds,
            symbol_counts=count_symbols(symbols, width=3),
        )

    def parameters(self, config: SimulatorConfig) -> dict[str, str]:
        parameters = {
            "Backend": config.backend,
            "Random source": config.random_source,
            "Alpha variance (SNU)": f"{config.alpha_variance_snu:g}",
            "Squeezing r": str(config.squeeze_r),
            "Theta / pi": str(config.theta_pi),
            "Tolerance (sigma)": f"{config.tolerance_sigmas:g}",
            "Intervals": config.intervals,
            "Axis policy": config.axis_policy,
            "Error correction": config.error_correction,
            "Max attempts": str(config.max_attempts),
        }

        if config.error_correction == "ldpc":
            parameters.update(
                {
                    "LDPC data bits": str(config.ldpc.data_bits),
                    "LDPC parity bits": str(config.ldpc.parity_bits),
                    "LDPC column weight": str(config.ldpc.column_weight),
                    "LDPC iterations": str(config.ldpc.max_iterations),
                    "LDPC seed": str(config.ldpc.seed),
                }
            )

        return parameters

    def symbols(self, config: SimulatorConfig) -> tuple[str, ...]:
        return INTERVAL_CODES[config.intervals].labels


SRIKARA = SrikaraSuite()


def main(argv: Sequence[str] | None = None) -> None:
    cli.main(SRIKARA, argv)


if __name__ == "__main__":
    main()
