import csv
import json
from io import StringIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from qsdc.protocols.srikara.benchmark.artifacts.metrics import (
    ArtifactTables,
    CheckMetrics,
    ComboOutcome,
    CorrectionMetrics,
    DecodingMetrics,
    TrialOutcome,
)
from qsdc.protocols.srikara.benchmark.artifacts.ui.index import write_benchmark_index
from qsdc.protocols.srikara.benchmark.cli import _config_paths
from qsdc.protocols.srikara.benchmark.engine import run_benchmark
from qsdc.protocols.srikara.benchmark.seeds import derive_seed
from qsdc.protocols.srikara.configuration.benchmark import BenchmarkConfig
from qsdc.protocols.srikara.simulator.backends.analytic.ideal import AnalyticBackend

TEST_BENCHMARK_CONFIG = {
    "name": "test",
    "backend": "analytic",
    "random_source": "classical",
    "payload_bit_count": 12,
    "trials_per_combo": 2,
    "base_seed": 1000,
    "tolerance_sigmas": 1.0,
    "output_dir": "results/srikara/benchmark/test",
    "one_probabilities": [0.1, 0.5, 0.9],
    "r_distributions": [
        {"kind": "uniform", "lower": 0.05, "upper": 0.2},
        {"kind": "fixed", "value": 0.4},
    ],
    "alpha_distribution": {"kind": "uniform_square", "bound": 2.0},
    "theta_distribution": {
        "kind": "uniform",
        "lower_pi": 0.0,
        "upper_pi": 2.0,
    },
}


def _test_config():
    return BenchmarkConfig.model_validate(TEST_BENCHMARK_CONFIG)


def test_seed_derivation_is_stable():
    assert derive_seed(1000, 2, 3) == derive_seed(1000, 2, 3)
    assert derive_seed(derive_seed(1000, 2, 3), "message") != derive_seed(
        derive_seed(1000, 2, 3),
        "simulation",
    )


def test_benchmark_config_loads_json_and_derives_transport_counts(tmp_path):
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(TEST_BENCHMARK_CONFIG), encoding="utf-8")
    config = BenchmarkConfig.model_validate_json(path.read_text(encoding="utf-8"))

    assert config.error_correction == "none"
    assert config.padding_bit_count == 0
    assert config.message_symbol_count == 4
    assert config.n_states == 16


def test_secded_is_a_strict_scalar_config_and_derives_coded_counts():
    config = BenchmarkConfig.model_validate(
        {"payload_bit_count": 16, "error_correction": "secded"}
    )

    assert config.codec_padding_bit_count == 8
    assert config.transmitted_message_bit_count == 48
    assert config.message_symbol_count == 16
    assert config.n_states == 64
    assert config.transport_block_count == 2


@pytest.mark.parametrize(
    "error_correction",
    ["enabled", "hamming", {"mode": "enabled"}, {"mode": "disabled"}],
)
def test_error_correction_config_rejects_legacy_shapes(error_correction):
    with pytest.raises(ValidationError):
        BenchmarkConfig.model_validate({"error_correction": error_correction})


def test_retry_configuration_requires_secded():
    with pytest.raises(ValidationError):
        BenchmarkConfig(max_attempts_per_block=2)


def test_benchmark_projects_one_complete_simulator_config():
    config = BenchmarkConfig.model_validate(
        {
            "backend": "sf-noise",
            "random_source": "classical",
            "error_correction": "secded",
            "max_attempts_per_block": 3,
            "noise": {
                "forward": [{"type": "loss", "transmittance": 0.9}],
            },
        }
    )
    simulator = config.simulator_config(
        intervals="optimized_v12",
        squeeze_r_distribution=config.r_distributions[0],
        seed=91,
    )

    assert simulator.backend == "sf-noise"
    assert simulator.random_source == "classical"
    assert simulator.noise.forward[0].transmittance == 0.9
    assert simulator.error_correction == "secded"
    assert simulator.max_attempts_per_block == 3


def test_artifact_metrics_are_split_by_concern():
    assert len(ComboOutcome.__dataclass_fields__) == 9
    assert len(TrialOutcome.__dataclass_fields__) == 9
    assert len(DecodingMetrics.__dataclass_fields__) == 8
    assert len(CheckMetrics.__dataclass_fields__) == 8
    assert len(CorrectionMetrics.__dataclass_fields__) == 5


def test_benchmark_keeps_simulator_results_and_writes_focused_csvs(tmp_path):
    config = _test_config().with_output_dir(str(tmp_path / "test"))
    report = run_benchmark(config)

    assert report.metrics.combo_count == 6
    assert report.metrics.trial_count == 12
    assert report.metrics.protocol_acceptance_rate == 1.0
    assert all(trial.result.frame.payload_bit_count == 12 for trial in report.trials)
    assert all(trial.result.payload_recovered for trial in report.trials)
    assert Path(report.output_dir).parent == tmp_path / "test"

    tables = ArtifactTables.from_results(report.combos, report.trials)
    assert all(row.raw_bit_error_rate == 0.0 for row in tables.decoding)
    assert all(row.raw_symbol_error_rate == 0.0 for row in tables.decoding)

    with (Path(report.output_dir) / "combos.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        combo_rows = list(csv.DictReader(handle))
    with (Path(report.output_dir) / "trials.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        trial_rows = list(csv.DictReader(handle))
    with (Path(report.output_dir) / "decoding.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        decoding_rows = list(csv.DictReader(handle))
    with (Path(report.output_dir) / "checks.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        check_rows = list(csv.DictReader(handle))
    with (Path(report.output_dir) / "corrections.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        correction_rows = list(csv.DictReader(handle))
    assert len(combo_rows) == 6
    assert len(trial_rows) == 12
    assert len(decoding_rows) == 6
    assert len(check_rows) == 12
    assert len(correction_rows) == 6
    assert decoding_rows[0]["raw_bit_error_rate"] == "0.0"
    assert combo_rows[0]["error_correction"] == "none"
    assert "raw_bit_error_rate" not in combo_rows[0]
    assert "error_correction" not in trial_rows[0]
    assert max(map(len, (combo_rows[0], trial_rows[0], decoding_rows[0]))) <= 9

    summary = json.loads(
        (Path(report.output_dir) / "benchmark.json").read_text(encoding="utf-8")
    )
    assert set(summary) == {"run_id", "output_dir", "config", "metrics", "artifacts"}
    assert summary["config"]["error_correction"] == "none"
    assert summary["metrics"]["trial_count"] == 12
    assert "parameters" not in summary
    assert "derived_counts" not in summary

    assert report.artifacts.plots == (
        "plots/raw_bit_error_by_r_by_interval.png",
        "plots/raw_symbol_error_by_r_by_interval.png",
        "plots/value_error_by_r_by_interval.png",
    )
    html = (Path(report.output_dir) / "report.html").read_text(encoding="utf-8")
    assert "Metric Definitions" not in html


def test_enabled_benchmark_reports_fec_metrics_and_plot(tmp_path):
    config = BenchmarkConfig.model_validate(
        {
            **TEST_BENCHMARK_CONFIG,
            "output_dir": str(tmp_path / "fec"),
            "trials_per_combo": 1,
            "one_probabilities": [0.5],
            "r_distributions": [{"kind": "fixed", "value": 0.4}],
            "error_correction": "secded",
        }
    )

    report = run_benchmark(config)
    trial = report.trials[0]

    assert report.config.error_correction == "secded"
    assert report.config.transport_block_count == 1
    assert trial.result.payload_recovered
    tables = ArtifactTables.from_results(report.combos, report.trials)
    assert tables.decoding[0].recovered_payload_bit_error_rate == 0.0
    assert tables.decoding[0].raw_bit_error_rate == 0.0
    assert trial.result.total_state_count == 32
    assert "plots/recovered_payload_bit_error_by_r_by_interval.png" in (
        report.artifacts.plots
    )


def test_benchmark_retry_counts_every_attempt_resource(tmp_path):
    class FailFirstRunBackend(AnalyticBackend):
        def __init__(self):
            object.__setattr__(self, "run_index", -1)

        def begin_run(self, seed):
            object.__setattr__(self, "run_index", self.run_index + 1)

        def control_measurement(self, alpha, squeeze_r, theta, axis):
            if self.run_index == 0:
                return None
            return super().control_measurement(alpha, squeeze_r, theta, axis)

    config = BenchmarkConfig.model_validate(
        {
            **TEST_BENCHMARK_CONFIG,
            "output_dir": str(tmp_path / "retry"),
            "trials_per_combo": 1,
            "one_probabilities": [0.5],
            "r_distributions": [{"kind": "fixed", "value": 0.4}],
            "error_correction": "secded",
            "max_attempts_per_block": 2,
        }
    )

    report = run_benchmark(
        config,
        write_artifacts=False,
        backend=FailFirstRunBackend(),
    )
    trial = report.trials[0]

    assert trial.result.delivery_status == "recovered"
    assert trial.result.total_attempt_count == 2
    assert trial.result.total_state_count == 64
    tables = ArtifactTables.from_results(report.combos, report.trials)
    assert tables.trials[0].retry_count == 1
    assert tables.checks[0].failed_count > 0


def test_benchmark_report_and_index_have_core_sections(tmp_path):
    config = _test_config().with_output_dir(str(tmp_path / "test"))
    report = run_benchmark(config)
    html = (Path(report.output_dir) / "report.html").read_text(encoding="utf-8")

    assert "Configuration" in html
    assert "Metric Definitions" not in html
    assert "Combination outcomes" in html
    assert "Channel checks" in html
    assert "Data tables" in html
    assert "decoding.csv" in html
    assert "checks.csv" in html
    assert "corrections.csv" in html

    index_path = Path(write_benchmark_index(Path(report.output_dir).parent))
    index_html = index_path.read_text(encoding="utf-8")
    assert "Report families" in index_html
    assert "Run History by Family" in index_html
    assert "accepted" in index_html


def test_benchmark_config_discovery_recurses_into_groups(tmp_path):
    config_dir = tmp_path / "configs"
    base_dir = config_dir / "base"
    base_dir.mkdir(parents=True)
    alpha = base_dir / "alpha_low.json"
    fixed = base_dir / "r_fixed.json"
    alpha.write_text("{}", encoding="utf-8")
    fixed.write_text("{}", encoding="utf-8")

    assert _config_paths(config_dir, ()) == [alpha, fixed]
    assert _config_paths(config_dir, ("base",)) == [alpha, fixed]
    assert _config_paths(config_dir, ("base/r_fixed",)) == [fixed]


def test_benchmark_progress_reports_completed_trials(tmp_path):
    config = _test_config().with_output_dir(str(tmp_path / "test"))
    output = StringIO()

    run_benchmark(
        config,
        write_artifacts=False,
        progress=True,
        progress_stream=output,
    )

    assert "12/12 trials" in output.getvalue()
    assert "Benchmark run finished." in output.getvalue()
