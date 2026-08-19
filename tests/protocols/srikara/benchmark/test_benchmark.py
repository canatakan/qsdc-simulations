import json
from io import StringIO
from pathlib import Path

import pytest

from qsdc.protocols.srikara.benchmark.artifacts.tables import (
    read_combo_csv,
    read_trial_csv,
)
from qsdc.protocols.srikara.benchmark.artifacts.report import _plot_cards
from qsdc.protocols.srikara.benchmark.artifacts.ui.index import write_benchmark_index
from qsdc.protocols.srikara.benchmark.cli import _config_paths
from qsdc.protocols.srikara.benchmark.metrics import aggregate_trial_metrics
from qsdc.protocols.srikara.benchmark.engine import run_benchmark
from qsdc.protocols.srikara.benchmark.seeds import derive_seed
from qsdc.protocols.srikara.configuration.benchmark import BenchmarkConfig
from qsdc.protocols.srikara.simulator.backends import make_backend


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
        {
            "kind": "uniform",
            "lower": 0.05,
            "upper": 0.2,
        },
        {
            "kind": "fixed",
            "value": 0.4,
        },
    ],
    "alpha_distribution": {
        "kind": "uniform_square",
        "bound": 2.0,
    },
    "theta_distribution": {
        "kind": "uniform",
        "lower_pi": 0.0,
        "upper_pi": 2.0,
    },
}


def _write_test_benchmark_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(TEST_BENCHMARK_CONFIG, indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path


def _test_benchmark_config():
    return BenchmarkConfig.model_validate(TEST_BENCHMARK_CONFIG)


def test_seed_derivation_is_stable():
    assert derive_seed(1000, 2, 3) == derive_seed(1000, 2, 3)
    assert derive_seed(derive_seed(1000, 2, 3), "message") != derive_seed(
        derive_seed(1000, 2, 3),
        "simulation",
    )


def test_benchmark_config_loads_json_file(tmp_path):
    config_path = _write_test_benchmark_config(tmp_path)
    config = BenchmarkConfig.model_validate_json(
        config_path.read_text(encoding="utf-8")
    )

    assert config.name == "test"
    assert config.backend == "analytic"
    assert config.interval_policies == ["default"]
    assert config.sigma_diagnostics is False
    assert config.check_axis_policy == "random"
    assert config.payload_bit_count == 12
    assert config.tolerance_sigmas == 1.0
    assert config.padding_bit_count == 0
    assert config.message_symbol_count == 4
    assert config.n_states == 16
    assert len(config.r_distributions) == 2
    assert config.noise.forward == []
    assert config.noise.bob_readout == []
    assert "noise" in config.model_dump(mode="json")


def test_benchmark_loads_executable_noise_model(tmp_path):
    raw = {
        **TEST_BENCHMARK_CONFIG,
        "backend": "sf-noise",
        "noise": {
            "forward": [{"type": "loss", "transmittance": 0.9}],
            "bob_readout": [
                {"type": "electronic_noise", "variance_snu": 0.0042}
            ],
        },
    }
    config_path = tmp_path / "noise.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")

    config = BenchmarkConfig.model_validate_json(
        config_path.read_text(encoding="utf-8")
    )

    assert config.backend == "sf-noise"
    assert config.noise.forward[0].transmittance == 0.9
    assert config.noise.bob_readout[0].variance_snu == 0.0042


@pytest.mark.parametrize(
    "noise",
    [
        {},
        {"forward": [{"type": "loss", "transmittance": 0.9}]},
    ],
)
def test_benchmark_accepts_noise_key_for_any_backend(tmp_path, noise):
    raw = {
        **TEST_BENCHMARK_CONFIG,
        "backend": "analytic",
        "noise": noise,
    }
    config_path = tmp_path / "old-noise-shape.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")

    config = BenchmarkConfig.model_validate_json(
        config_path.read_text(encoding="utf-8")
    )

    assert config.backend == "analytic"
    assert len(config.noise.forward) == len(noise.get("forward", []))
    assert "noise" in config.model_dump(mode="json")


def test_noisy_backend_accepts_empty_noise_configuration():
    config = BenchmarkConfig.model_validate(
        {
            **TEST_BENCHMARK_CONFIG,
            "backend": "sf-noise",
            "noise": {},
        }
    )

    assert config.backend == "sf-noise"
    assert config.noise.forward == []
    assert config.noise.bob_readout == []


def test_noisy_backend_defaults_to_empty_noise_configuration():
    config = BenchmarkConfig.model_validate(
        {**TEST_BENCHMARK_CONFIG, "backend": "sf-noise"}
    )

    assert config.noise.forward == []
    assert config.noise.bob_readout == []


def test_benchmark_factory_receives_one_complete_backend_config():
    received = []

    def backend_factory(name, noise):
        received.append((name, noise))
        return make_backend(name, noise)

    config = BenchmarkConfig.model_validate(
        {
            **TEST_BENCHMARK_CONFIG,
            "trials_per_combo": 1,
            "one_probabilities": [0.5],
            "r_distributions": [{"kind": "fixed", "value": 0.4}],
        }
    )

    run_benchmark(
        config,
        write_artifacts=False,
        backend_factory=backend_factory,
    )

    assert received == [(config.backend, config.noise)]


def test_payload_bit_count_derives_padding_and_protocol_counts():
    config = BenchmarkConfig.model_validate(
        {
            "payload_bit_count": 16,
            "one_probabilities": [0.5],
            "r_distributions": [{"kind": "fixed", "value": 0.4}],
        }
    )

    assert config.payload_bit_count == 16
    assert config.padding_bit_count == 2
    assert config.transmitted_message_bit_count == 18
    assert config.message_symbol_count == 6
    assert config.n_states == 24



def test_aggregate_metrics_include_symbol_errors():
    metrics = aggregate_trial_metrics(
        [
            {
                "accepted": False,
                "message_bit_error_count": 2,
                "message_bit_count": 10,
                "message_symbol_error_count": 1,
                "message_symbol_count": 5,
                "mean_abs_value_error": 0.4,
                "mean_interval_miss_distance": 0.2,
                "mean_interval_margin": -0.2,
            },
            {
                "accepted": False,
                "message_bit_error_count": 1,
                "message_bit_count": 10,
                "message_symbol_error_count": 2,
                "message_symbol_count": 5,
                "mean_abs_value_error": 0.6,
                "mean_interval_miss_distance": 0.4,
                "mean_interval_margin": -0.4,
            },
        ]
    )

    assert metrics["bit_error_rate"] == 0.15
    assert metrics["symbol_error_rate"] == 0.3
    assert abs(float(metrics["mean_interval_miss_distance"]) - 0.3) < 1e-12


def test_benchmark_runs_with_analytic_backend(tmp_path):
    config = _test_benchmark_config().with_output_dir(str(tmp_path / "test"))

    report = run_benchmark(config)

    assert report.summary["combo_count"] == 6
    assert report.summary["trial_count"] == 12
    assert report.summary["parameters"]["interval_policies"] == ["default"]
    assert report.summary["accepted_rate"] == 1.0
    assert all(trial["payload_bit_count"] == 12 for trial in report.trials)
    assert all(trial["transmitted_message_bit_count"] == 12 for trial in report.trials)
    assert all(combo["all"]["bit_error_rate"] == 0.0 for combo in report.combos)
    assert all(combo["all"]["symbol_error_rate"] == 0.0 for combo in report.combos)
    assert all("control_max_sigma_deviation" not in trial for trial in report.trials)
    assert all("decoy_max_sigma_deviation" not in trial for trial in report.trials)
    assert all("check_sigma_deviations" not in trial for trial in report.trials)
    assert all(combo["control_check_count"] > 0 for combo in report.combos)
    assert all(combo["control_failed_check_count"] == 0 for combo in report.combos)
    assert all(combo["decoy_check_count"] > 0 for combo in report.combos)
    assert all(combo["decoy_failed_check_count"] == 0 for combo in report.combos)
    assert all("interval_miss_rate" not in combo["all"] for combo in report.combos)
    assert all("interval_miss_count" not in trial for trial in report.trials)
    assert all("check_sigma_deviations" not in combo["all"] for combo in report.combos)
    assert all("all_bit_error_rate" not in combo for combo in report.combos)
    assert Path(report.output_dir).parent == tmp_path / "test"
    assert (Path(report.output_dir) / "combos.csv").exists()
    assert (Path(report.output_dir) / "trials.csv").exists()
    assert not (Path(report.output_dir) / "benchmark.xlsx").exists()
    assert not (Path(report.output_dir) / "config.json").exists()
    assert not (Path(report.output_dir) / "combos.json").exists()
    assert not (Path(report.output_dir) / "trials.jsonl").exists()
    combo_rows = read_combo_csv(Path(report.output_dir) / "combos.csv")
    trial_rows = read_trial_csv(Path(report.output_dir) / "trials.csv")
    assert len(combo_rows) == 6
    assert len(trial_rows) == 12
    assert combo_rows[0]["bit_error_rate"] == "0.0"
    assert "check_sigma_deviation_max" not in combo_rows[0]
    assert trial_rows[0]["intervals"] == "default"
    assert trial_rows[0]["check_axis_policy"] == "random"
    assert trial_rows[0]["message_axis_policy"] == "random"
    assert "required_acceptance_tolerance_sigmas" not in trial_rows[0]
    assert report.summary["artifacts"]["combos_csv"] == "combos.csv"
    assert report.summary["artifacts"]["trials_csv"] == "trials.csv"
    assert report.summary["artifacts"]["html_report"] == "report.html"
    assert report.summary["artifacts"]["html_report_css"] == "report.css"
    assert "effective_config" not in report.summary
    assert "benchmark_run_unix_seconds" not in report.summary
    assert (Path(report.output_dir) / "report.html").exists()
    assert (Path(report.output_dir) / "report.css").exists()
    assert report.summary["artifacts"]["plots"] == [
        "plots/bit_error_by_r_by_interval.png",
        "plots/symbol_error_by_r_by_interval.png",
        "plots/value_error_by_r_by_interval.png",
    ]
    for plot_path in report.summary["artifacts"]["plots"]:
        assert (Path(report.output_dir) / plot_path).exists()


def test_benchmark_report_contains_core_sections(tmp_path):
    config = _test_benchmark_config().with_output_dir(str(tmp_path / "test"))

    report = run_benchmark(config)
    html = (Path(report.output_dir) / "report.html").read_text(encoding="utf-8")

    assert "Run Setup" in html
    assert "Combo Outcomes" in html
    assert "Check Failures" in html
    assert "Raw Tables" in html
    assert "combos.csv" in html
    assert "trials.csv" in html
    assert "benchmark.xlsx" not in html
    assert "config.json" not in html
    assert "Mean bit error" in html
    assert "Mean symbol error" in html
    assert "Mean numeric error" in html
    assert "Worst symbol error" not in html


def test_benchmark_report_hides_delta_vs_default_plots():
    html = _plot_cards(
        [
            "plots/bit_error_by_r_by_interval.png",
            "plots/bit_error_by_r_delta_vs_default.png",
        ]
    )

    assert "bit_error_by_r_by_interval.png" in html
    assert "delta_vs_default" not in html


def test_benchmark_ui_index_lists_runs(tmp_path):
    config = _test_benchmark_config().with_output_dir(str(tmp_path / "test"))
    report = run_benchmark(config)

    index_path = Path(write_benchmark_index(Path(report.output_dir).parent))
    html = index_path.read_text(encoding="utf-8")

    assert index_path.name == "index.html"
    assert "uniform_square" in html
    assert "alpha=uniform_square" not in html
    assert "uniform[0,2pi]" in html
    assert "theta=uniform" not in html
    assert "accepted" in html
    assert "open" in html
    assert "Report families" in html
    assert "top-level report collections" in html
    assert "Report configuration" in html
    assert "One probability" in html
    assert "Run History by Family" in html
    assert "max symbol error" not in html
    assert (index_path.parent / "index.css").exists()


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
    assert _config_paths(config_dir, ("r_fixed",)) == [fixed]


def test_benchmark_progress_reports_completed_trials(tmp_path):
    config = _test_benchmark_config().with_output_dir(str(tmp_path / "test"))
    progress_output = StringIO()

    run_benchmark(
        config,
        write_artifacts=False,
        progress=True,
        progress_stream=progress_output,
    )

    output = progress_output.getvalue()
    assert "12/12 trials" in output
    assert "Benchmark run finished." in output
