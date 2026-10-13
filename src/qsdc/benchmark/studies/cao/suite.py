from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from qsdc.common.coding.bits import hamming_distance
from qsdc.protocols.cao.config import NOISES, PRESETS, SimulatorConfig
from qsdc.protocols.cao.simulator.mapping import interval_code
from qsdc.protocols.cao.simulator.protocol import CaoSimulator, Transmission

from ... import cli
from ...metrics import RunMetrics, count_blocks, count_symbols
from ...suite import Suite


class CaoSuite(Suite):
    # A state is an EPR pair, and a symbol is a box with its detection bits.
    name = "cao"
    config = SimulatorConfig
    presets = PRESETS
    noises = NOISES
    studies = Path(__file__).with_name("studies.yaml")
    output_root = Path(__file__).parents[2] / "results" / "cao"

    def simulate(self, config: SimulatorConfig, payload: str) -> Transmission:
        return CaoSimulator(config).transmit(payload)

    def measure(
        self, config: SimulatorConfig, transmission: Transmission, seconds: float
    ) -> RunMetrics:
        attempts = transmission.attempts
        signals = [signal for attempt in attempts for signal in attempt.run.signals]
        stages = [
            stage
            for attempt in attempts
            for stage in (attempt.run.channel, attempt.run.authentication)
            if stage is not None
        ]
        checks = [check for stage in stages for check in stage.checks]
        symbols = [(signal.box.bits, signal.decoded_bits) for signal in signals]

        return RunMetrics(
            **count_blocks(transmission),
            raw_bits=sum(len(sent) for sent, _ in symbols),
            raw_error_bits=sum(
                hamming_distance(sent, decoded) for sent, decoded in symbols
            ),
            states=sum(attempt.run.pairs for attempt in attempts),
            checks=len(checks),
            failed_checks=sum(not check.passed for check in checks),
            seconds=seconds,
            symbol_counts=count_symbols(
                symbols, width=config.box_bits + config.detection_bits
            ),
        )

    def parameters(self, config: SimulatorConfig) -> dict[str, str]:
        reconciliation = config.reconciliation
        syndrome = (
            "none"
            if reconciliation is None
            else f"{reconciliation.syndrome_fraction:g}"
        )

        return {
            "Backend": config.backend,
            "Random source": config.random_source,
            "Squeezing r": f"{config.squeeze_r:.4g}",
            "Modulation variance (SNU)": f"{config.modulation_variance_snu:g}",
            "Boxes per block": str(config.boxes),
            "Payload bits per box": str(config.box_bits),
            "Detection bits per box": str(config.detection_bits),
            "Check pairs per stage": str(config.check_pairs),
            "Check tolerance (sigma)": f"{config.check_tolerance_sigmas:g}",
            "Syndrome fraction": syndrome,
            "Message bits per block": str(config.block_bits),
            "Max attempts": str(config.max_attempts),
        }

    def symbols(self, config: SimulatorConfig) -> tuple[str, ...]:
        return interval_code(config).labels


CAO = CaoSuite()


def main(argv: Sequence[str] | None = None) -> None:
    cli.main(CAO, argv)


if __name__ == "__main__":
    main()
