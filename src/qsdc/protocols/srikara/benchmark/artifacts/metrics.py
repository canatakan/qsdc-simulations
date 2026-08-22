"""Focused artifact rows derived from simulator results."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Optional

from pydantic import TypeAdapter

from qsdc.common.bits import hamming_distance
from qsdc.protocols.srikara.configuration.benchmark import BenchmarkConfig
from qsdc.protocols.srikara.configuration.simulator import (
    ErrorCorrection,
    IntervalPolicy,
)
from qsdc.protocols.srikara.simulator.encoding import interval_for_bits
from qsdc.protocols.srikara.simulator.protocol import (
    MessageDecode,
    ProtocolResult,
)


@dataclass(frozen=True)
class BenchmarkTrial:
    combo_index: int
    trial_index: int
    seed: int
    expected_payload_bits: str
    result: ProtocolResult
    include_sigma_diagnostics: bool


@dataclass(frozen=True)
class BenchmarkCombo:
    index: int
    intervals: IntervalPolicy
    one_probability: float
    r_distribution: str
    error_correction: ErrorCorrection
    trials: tuple[BenchmarkTrial, ...]


@dataclass(frozen=True)
class RunMetrics:
    combo_count: int
    trial_count: int
    accepted_count: int
    protocol_acceptance_rate: float
    payload_recovered_count: int
    payload_recovery_rate: float
    total_attempt_count: int
    total_state_count: int
    delivered_payload_bit_count: int
    delivered_bits_per_state: float
    elapsed_seconds: float

    @classmethod
    def from_trials(
        cls,
        combo_count: int,
        trials: Sequence[BenchmarkTrial],
        elapsed_seconds: float,
    ) -> RunMetrics:
        accepted = sum(trial.result.accepted for trial in trials)
        recovered = sum(trial.result.payload_recovered for trial in trials)
        states = sum(trial.result.total_state_count for trial in trials)
        delivered = sum(
            len(trial.expected_payload_bits)
            for trial in trials
            if trial.result.payload_recovered
        )
        return cls(
            combo_count,
            len(trials),
            accepted,
            accepted / len(trials) if trials else 0.0,
            recovered,
            recovered / len(trials) if trials else 0.0,
            sum(trial.result.total_attempt_count for trial in trials),
            states,
            delivered,
            delivered / states if states else 0.0,
            elapsed_seconds,
        )


@dataclass(frozen=True)
class ArtifactManifest:
    benchmark: str = "benchmark.json"
    combos_csv: str = "combos.csv"
    trials_csv: str = "trials.csv"
    decoding_csv: str = "decoding.csv"
    checks_csv: str = "checks.csv"
    corrections_csv: str = "corrections.csv"
    html_report: str = "report.html"
    html_report_css: str = "report.css"
    plots: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkArtifact:
    """The exact typed representation stored in ``benchmark.json``."""

    run_id: str
    output_dir: str
    config: BenchmarkConfig
    metrics: RunMetrics
    artifacts: ArtifactManifest


@dataclass(frozen=True)
class BenchmarkRun:
    run_id: str
    output_dir: str
    config: BenchmarkConfig
    metrics: RunMetrics
    trials: tuple[BenchmarkTrial, ...]
    combos: tuple[BenchmarkCombo, ...]
    artifacts: ArtifactManifest = ArtifactManifest()

    @property
    def artifact(self) -> BenchmarkArtifact:
        return BenchmarkArtifact(
            self.run_id,
            self.output_dir,
            self.config,
            self.metrics,
            self.artifacts,
        )

    @classmethod
    def from_results(
        cls,
        run_id: str,
        output_dir: str,
        config: BenchmarkConfig,
        trials: tuple[BenchmarkTrial, ...],
        combos: tuple[BenchmarkCombo, ...],
        elapsed_seconds: float,
    ) -> BenchmarkRun:
        return cls(
            run_id,
            output_dir,
            config,
            RunMetrics.from_trials(len(combos), trials, elapsed_seconds),
            trials,
            combos,
        )


@dataclass(frozen=True)
class ComboOutcome:
    combo_index: int
    intervals: IntervalPolicy
    one_probability: float
    r_distribution: str
    error_correction: ErrorCorrection
    trial_count: int
    protocol_acceptance_rate: float
    payload_recovery_rate: float
    delivered_bits_per_state: float

    @classmethod
    def from_combo(cls, combo: BenchmarkCombo) -> ComboOutcome:
        states = sum(trial.result.total_state_count for trial in combo.trials)
        delivered = sum(
            len(trial.expected_payload_bits)
            for trial in combo.trials
            if trial.result.payload_recovered
        )
        return cls(
            combo.index,
            combo.intervals,
            combo.one_probability,
            combo.r_distribution,
            combo.error_correction,
            len(combo.trials),
            _fraction(trial.result.accepted for trial in combo.trials),
            _fraction(trial.result.payload_recovered for trial in combo.trials),
            delivered / states if states else 0.0,
        )


@dataclass(frozen=True)
class TrialOutcome:
    combo_index: int
    trial_index: int
    seed: int
    delivery_status: str
    accepted: bool
    payload_recovered: bool
    attempt_count: int
    retry_count: int
    state_count: int

    @classmethod
    def from_trial(cls, trial: BenchmarkTrial) -> TrialOutcome:
        result = trial.result
        return cls(
            trial.combo_index,
            trial.trial_index,
            trial.seed,
            result.delivery_status,
            result.accepted,
            result.payload_recovered,
            result.total_attempt_count,
            result.total_attempt_count - result.frame.transport_block_count,
            result.total_state_count,
        )


@dataclass(frozen=True)
class DecodingMetrics:
    combo_index: int
    raw_bit_error_rate: Optional[float]
    raw_bit_erasure_rate: float
    raw_symbol_error_rate: Optional[float]
    raw_symbol_erasure_rate: float
    mean_abs_value_error: float
    mean_interval_margin: float
    recovered_payload_bit_error_rate: Optional[float]

    @classmethod
    def from_combo(cls, combo: BenchmarkCombo) -> DecodingMetrics:
        messages = tuple(
            message
            for trial in combo.trials
            for attempt in trial.result.attempts
            for message in attempt.protocol.messages
        )
        measured = tuple(
            message for message in messages if message.decoded_bits is not None
        )
        recovered_trials = tuple(
            trial for trial in combo.trials if trial.result.recovered_bits is not None
        )
        measured_bit_count = 3 * len(measured)
        return cls(
            combo.index,
            (
                sum(
                    hamming_distance(message.sent_bits, message.decoded_bits or "")
                    for message in measured
                )
                / measured_bit_count
                if measured_bit_count
                else None
            ),
            (len(messages) - len(measured)) / len(messages) if messages else 0.0,
            (
                sum(message.sent_bits != message.decoded_bits for message in measured)
                / len(measured)
                if measured
                else None
            ),
            (len(messages) - len(measured)) / len(messages) if messages else 0.0,
            _mean(
                abs(message.decoded_value - message.message_value)
                for message in measured
                if message.decoded_value is not None
            ),
            _mean(
                _interval_margin(message)
                for message in measured
                if message.decoded_value is not None
            ),
            (
                sum(
                    hamming_distance(
                        trial.expected_payload_bits,
                        trial.result.recovered_bits or "",
                    )
                    for trial in recovered_trials
                )
                / sum(len(trial.expected_payload_bits) for trial in recovered_trials)
                if recovered_trials
                else None
            ),
        )


@dataclass(frozen=True)
class CheckMetrics:
    combo_index: int
    check: str
    measurement_count: int
    failed_count: int
    invalid_count: int
    failure_rate: float
    mean_abs_deviation: float
    max_abs_deviation: float

    @classmethod
    def from_combo(cls, combo: BenchmarkCombo, check: str) -> CheckMetrics:
        checks = tuple(
            item
            for trial in combo.trials
            for attempt in trial.result.attempts
            for item in (
                attempt.protocol.controls
                if check == "control"
                else attempt.protocol.decoys
            )
        )
        deviations = tuple(
            abs(item.measured - item.expected)
            for item in checks
            if item.measured is not None and item.status != "invalid_measurement"
        )
        return cls(
            combo.index,
            check,
            len(checks),
            sum(not item.passed for item in checks),
            sum(item.status == "invalid_measurement" for item in checks),
            _fraction(not item.passed for item in checks),
            _mean(deviations),
            max(deviations, default=0.0),
        )


@dataclass(frozen=True)
class CorrectionMetrics:
    combo_index: int
    corrected_codewords: int
    corrected_bits: int
    recovered_erasures: int
    uncorrectable_codewords: int

    @classmethod
    def from_combo(cls, combo: BenchmarkCombo) -> CorrectionMetrics:
        decodes = tuple(
            attempt.decode
            for trial in combo.trials
            for attempt in trial.result.attempts
            if attempt.decode is not None
        )
        return cls(
            combo.index,
            sum(decode.corrected_codewords for decode in decodes),
            sum(decode.corrected_bits for decode in decodes),
            sum(decode.recovered_erasures for decode in decodes),
            sum(decode.uncorrectable_codewords for decode in decodes),
        )


@dataclass(frozen=True)
class ArtifactTables:
    combos: tuple[ComboOutcome, ...]
    trials: tuple[TrialOutcome, ...]
    decoding: tuple[DecodingMetrics, ...]
    checks: tuple[CheckMetrics, ...]
    corrections: tuple[CorrectionMetrics, ...]
    check_sigma_deviations: tuple[float, ...]

    @classmethod
    def from_results(
        cls,
        combos: Sequence[BenchmarkCombo],
        trials: Sequence[BenchmarkTrial],
    ) -> ArtifactTables:
        return cls(
            tuple(ComboOutcome.from_combo(combo) for combo in combos),
            tuple(TrialOutcome.from_trial(trial) for trial in trials),
            tuple(DecodingMetrics.from_combo(combo) for combo in combos),
            tuple(
                CheckMetrics.from_combo(combo, check)
                for combo in combos
                for check in ("control", "decoy")
            ),
            tuple(CorrectionMetrics.from_combo(combo) for combo in combos),
            sigma_deviations(trials),
        )

    def combo_plot_rows(self) -> list[dict[str, object]]:
        decoding = {row.combo_index: asdict(row) for row in self.decoding}
        return [{**asdict(row), **decoding[row.combo_index]} for row in self.combos]

    @classmethod
    def read(cls, output_dir: str | Path) -> ArtifactTables:
        output_dir = Path(output_dir)
        return cls(
            TypeAdapter(tuple[ComboOutcome, ...]).validate_python(
                _read_csv(output_dir / "combos.csv")
            ),
            TypeAdapter(tuple[TrialOutcome, ...]).validate_python(
                _read_csv(output_dir / "trials.csv")
            ),
            TypeAdapter(tuple[DecodingMetrics, ...]).validate_python(
                _read_csv(output_dir / "decoding.csv")
            ),
            TypeAdapter(tuple[CheckMetrics, ...]).validate_python(
                _read_csv(output_dir / "checks.csv")
            ),
            TypeAdapter(tuple[CorrectionMetrics, ...]).validate_python(
                _read_csv(output_dir / "corrections.csv")
            ),
            (),
        )


def sigma_deviations(trials: Sequence[BenchmarkTrial]) -> tuple[float, ...]:
    deviations = []
    for trial in trials:
        if not trial.include_sigma_diagnostics:
            continue
        for attempt in trial.result.attempts:
            for check in (*attempt.protocol.controls, *attempt.protocol.decoys):
                if (
                    check.measured is None
                    or check.status == "invalid_measurement"
                    or check.expected_sigma == 0.0
                ):
                    continue
                deviations.append(
                    abs(check.measured - check.expected) / check.expected_sigma
                )
    return tuple(deviations)


def _interval_margin(message: MessageDecode) -> float:
    interval = interval_for_bits(message.sent_bits, intervals=message.intervals)
    value = message.decoded_value
    if value is None:
        return 0.0
    if interval.contains(value):
        if interval.lower == float("-inf"):
            return interval.upper - value
        if interval.upper == float("inf"):
            return value - interval.lower
        return min(value - interval.lower, interval.upper - value)
    return -(
        interval.lower - value if value <= interval.lower else value - interval.upper
    )


def _fraction(values) -> float:
    values = tuple(values)
    return sum(values) / len(values) if values else 0.0


def _mean(values) -> float:
    values = tuple(values)
    return mean(values) if values else 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
