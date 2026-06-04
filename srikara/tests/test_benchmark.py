from pathlib import Path

from srikara.benchmark import load_benchmark_config, run_benchmark
from srikara.benchmark.config import LinearSweep, parse_benchmark_config
from srikara.benchmark.seeds import derive_seed
from utils import ClassicalRandomSource, hamming_distance, weighted_random_bits


def test_weighted_random_bits_respects_extreme_probabilities():
    assert weighted_random_bits(6, 0.0, ClassicalRandomSource(1)) == "000000"
    assert weighted_random_bits(6, 1.0, ClassicalRandomSource(1)) == "111111"


def test_seed_derivation_is_stable():
    assert derive_seed(1000, 2, 3) == derive_seed(1000, 2, 3)
    assert derive_seed(derive_seed(1000, 2, 3), "message") != derive_seed(
        derive_seed(1000, 2, 3),
        "simulation",
    )


def test_linear_tolerance_sweep_expands_inclusive_values():
    assert LinearSweep(start=0.0, stop=0.03, step=0.01).expand() == (
        0.0,
        0.01,
        0.02,
        0.03,
    )


def test_benchmark_config_parses_smoke_config():
    config = load_benchmark_config(
        Path("srikara") / "benchmark" / "configs" / "smoke.json"
    )

    assert config.name == "smoke"
    assert config.backend == "analytic"
    assert config.payload_bit_count == 12
    assert config.padding_bit_count == 0
    assert config.message_symbol_count == 4
    assert config.n_states == 16
    assert len(config.tolerance_values()) == 2
    assert len(config.r_distributions) == 2


def test_payload_bit_count_derives_padding_and_protocol_counts():
    config = parse_benchmark_config(
        {
            "payload_bit_count": 16,
            "one_probabilities": [0.5],
            "tolerances": {"kind": "explicit", "values": [0.01]},
            "r_distributions": [{"kind": "fixed", "value": 0.4}],
        }
    )

    assert config.payload_bit_count == 16
    assert config.padding_bit_count == 2
    assert config.transmitted_message_bit_count == 18
    assert config.message_symbol_count == 6
    assert config.n_states == 24


def test_smoke_benchmark_runs_with_analytic_backend(tmp_path):
    config = load_benchmark_config(
        Path("srikara") / "benchmark" / "configs" / "smoke.json"
    ).with_output_dir(str(tmp_path / "smoke"))

    report = run_benchmark(config)

    assert report.summary["combo_count"] == 12
    assert report.summary["trial_count"] == 24
    assert report.summary["accepted_rate"] == 1.0
    assert all(trial["payload_bit_count"] == 12 for trial in report.trials)
    assert all(trial["transmitted_message_bit_count"] == 12 for trial in report.trials)
    assert all(combo["all"]["bit_error_rate"] == 0.0 for combo in report.combos)
    assert all("all_bit_error_rate" not in combo for combo in report.combos)
    assert Path(report.output_dir).parent == tmp_path / "smoke"
    assert (Path(report.output_dir) / "trials.jsonl").exists()


def test_hamming_distance_counts_known_errors():
    assert hamming_distance("0011", "1010") == 2
