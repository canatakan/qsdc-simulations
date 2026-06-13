from io import StringIO
from pathlib import Path

from qsdc.protocols.srikara.benchmark.artifacts.tables import (
    read_combo_csv,
    read_trial_csv,
)
from qsdc.protocols.srikara.benchmark.artifacts.ui.index import write_benchmark_index
from qsdc.protocols.srikara.benchmark.config import (
    load_benchmark_config,
    parse_benchmark_config,
)
from qsdc.protocols.srikara.benchmark.metrics import aggregate_trial_metrics
from qsdc.protocols.srikara.benchmark.engine import run_benchmark
from qsdc.protocols.srikara.benchmark.seeds import derive_seed


def test_seed_derivation_is_stable():
    assert derive_seed(1000, 2, 3) == derive_seed(1000, 2, 3)
    assert derive_seed(derive_seed(1000, 2, 3), "message") != derive_seed(
        derive_seed(1000, 2, 3),
        "simulation",
    )


def test_benchmark_config_parses_test_config():
    config = load_benchmark_config(
        Path("src")
        / "qsdc"
        / "protocols"
        / "srikara"
        / "benchmark"
        / "configs"
        / "test.json"
    )

    assert config.name == "test"
    assert config.backend == "analytic"
    assert config.payload_bit_count == 12
    assert config.tolerance_sigmas == 1.0
    assert config.padding_bit_count == 0
    assert config.message_symbol_count == 4
    assert config.n_states == 16
    assert len(config.r_distributions) == 2


def test_payload_bit_count_derives_padding_and_protocol_counts():
    config = parse_benchmark_config(
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


def test_benchmark_config_rejects_tolerances_field():
    try:
        parse_benchmark_config(
            {
                "payload_bit_count": 16,
                "one_probabilities": [0.5],
                "tolerances": {"kind": "explicit", "values": [0.01]},
                "r_distributions": [{"kind": "fixed", "value": 0.4}],
            }
        )
    except ValueError as error:
        assert "unknown benchmark config field(s): 'tolerances'" in str(error)
    else:
        raise AssertionError("expected tolerances to be rejected")


def test_aggregate_metrics_include_symbol_errors_and_thresholds():
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
                "required_acceptance_tolerance_sigmas": 0.8,
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
                "required_acceptance_tolerance_sigmas": 1.2,
            },
        ]
    )

    assert metrics["bit_error_rate"] == 0.15
    assert metrics["symbol_error_rate"] == 0.3
    assert abs(float(metrics["mean_interval_miss_distance"]) - 0.3) < 1e-12
    assert metrics["required_acceptance_tolerance_sigmas"] == {
        "min": 0.8,
        "mean": 1.0,
        "median": 1.0,
        "p95": 1.2,
        "max": 1.2,
    }


def test_benchmark_runs_with_analytic_backend(tmp_path):
    config = load_benchmark_config(
        Path("src")
        / "qsdc"
        / "protocols"
        / "srikara"
        / "benchmark"
        / "configs"
        / "test.json"
    ).with_output_dir(str(tmp_path / "test"))

    report = run_benchmark(config)

    assert report.summary["combo_count"] == 6
    assert report.summary["trial_count"] == 12
    assert report.summary["accepted_rate"] == 1.0
    assert all(trial["payload_bit_count"] == 12 for trial in report.trials)
    assert all(trial["transmitted_message_bit_count"] == 12 for trial in report.trials)
    assert all(
        trial["required_acceptance_tolerance_sigmas"] == 0.0
        for trial in report.trials
    )
    assert all(combo["all"]["bit_error_rate"] == 0.0 for combo in report.combos)
    assert all(combo["all"]["symbol_error_rate"] == 0.0 for combo in report.combos)
    assert all(combo["check_tolerance_sigmas"] == 1.0 for combo in report.combos)
    assert all(combo["measurement_noise_sigma"] == 1e-7 for combo in report.combos)
    assert all(trial["check_tolerance_sigmas"] == 1.0 for trial in report.trials)
    assert all(trial["measurement_noise_sigma"] == 1e-7 for trial in report.trials)
    assert all("control_max_sigma_deviation" not in trial for trial in report.trials)
    assert all("decoy_max_sigma_deviation" not in trial for trial in report.trials)
    assert all(combo["control_check_count"] > 0 for combo in report.combos)
    assert all(combo["control_failed_check_count"] == 0 for combo in report.combos)
    assert all(combo["decoy_check_count"] > 0 for combo in report.combos)
    assert all(combo["decoy_failed_check_count"] == 0 for combo in report.combos)
    assert all("interval_miss_rate" not in combo["all"] for combo in report.combos)
    assert all("interval_miss_count" not in trial for trial in report.trials)
    assert all(
        combo["all"]["required_acceptance_tolerance_sigmas"]["max"] == 0.0
        for combo in report.combos
    )
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
    assert combo_rows[0]["required_acceptance_tolerance_sigmas_max"] == "0.0"
    assert trial_rows[0]["required_acceptance_tolerance_sigmas"] == "0.0"
    assert report.summary["artifacts"]["combos_csv"] == "combos.csv"
    assert report.summary["artifacts"]["trials_csv"] == "trials.csv"
    assert report.summary["artifacts"]["html_report"] == "report.html"
    assert report.summary["artifacts"]["html_report_css"] == "report.css"
    assert "effective_config" not in report.summary
    assert "benchmark_run_unix_seconds" not in report.summary
    assert (Path(report.output_dir) / "report.html").exists()
    assert (Path(report.output_dir) / "report.css").exists()
    assert report.summary["artifacts"]["plots"] == [
        "plots/bit_error_by_r.png",
        "plots/symbol_error_by_r.png",
        "plots/value_error_by_r.png",
        "plots/derived_acceptance_tolerance_sigmas_curve.png",
    ]
    for plot_path in report.summary["artifacts"]["plots"]:
        assert (Path(report.output_dir) / plot_path).exists()


def test_benchmark_report_contains_core_sections(tmp_path):
    config = load_benchmark_config(
        Path("src")
        / "qsdc"
        / "protocols"
        / "srikara"
        / "benchmark"
        / "configs"
        / "test.json"
    ).with_output_dir(str(tmp_path / "test"))

    report = run_benchmark(config)
    html = (Path(report.output_dir) / "report.html").read_text(encoding="utf-8")

    assert "Run Setup" in html
    assert "Combo Outcomes" in html
    assert "Check Failures" in html
    assert "Tolerance Thresholds" in html
    assert "Raw Tables" in html
    assert "Metric Meanings" in html
    assert "combos.csv" in html
    assert "trials.csv" in html
    assert "benchmark.xlsx" not in html
    assert "config.json" not in html


def test_benchmark_ui_index_lists_runs(tmp_path):
    config = load_benchmark_config(
        Path("src")
        / "qsdc"
        / "protocols"
        / "srikara"
        / "benchmark"
        / "configs"
        / "test.json"
    ).with_output_dir(str(tmp_path / "test"))
    report = run_benchmark(config)

    index_path = Path(write_benchmark_index(Path(report.output_dir).parent))
    html = index_path.read_text(encoding="utf-8")

    assert index_path.name == "index.html"
    assert "Run Comparison" in html
    assert "alpha=uniform_square" in html
    assert "theta=uniform" in html
    assert "open" in html
    assert (index_path.parent / "index.css").exists()


def test_benchmark_progress_reports_completed_trials(tmp_path):
    config = load_benchmark_config(
        Path("src")
        / "qsdc"
        / "protocols"
        / "srikara"
        / "benchmark"
        / "configs"
        / "test.json"
    ).with_output_dir(str(tmp_path / "test"))
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
