import csv
import json
from dataclasses import replace

import pytest

from qsdc.protocols.srikara.benchmark import cli
from qsdc.protocols.srikara.benchmark.benchmark import (
    Benchmark,
    Case,
    Workload,
    run_benchmark,
)
from qsdc.protocols.srikara.benchmark.catalog import NOISES, WORKLOADS, noise_studies
from qsdc.protocols.srikara.benchmark.metrics import measure, pool
from qsdc.protocols.srikara.benchmark.report import load_result, rerender, write_report
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator

PAYLOAD = "101001110010"


def test_ideal_run_delivers_every_bit():
    metrics = measure(SrikaraSimulator(SimulatorConfig()).transmit(PAYLOAD), 0.0)

    assert metrics.delivered_fraction == 1.0
    assert (metrics.bit_error_rate, metrics.erasure_rate, metrics.rejection_rate) == (
        0.0,
        0.0,
        0.0,
    )
    assert metrics.delivered_bits_per_state == 12 / 16


def test_noiseless_channel_carries_three_bits_per_message_state():
    every_symbol = "000001010011100101110111"
    metrics = measure(SrikaraSimulator(SimulatorConfig()).transmit(every_symbol), 0.0)

    # One state in four carries a message.
    assert metrics.information_per_state == pytest.approx(3 / 4)


def test_partial_delivery_counts_erasures_and_retry_states(reject_every_other_run):
    single = measure(
        SrikaraSimulator(SimulatorConfig(), reject_every_other_run()).transmit(PAYLOAD),
        0.0,
    )
    retried = measure(
        SrikaraSimulator(
            SimulatorConfig(max_attempts=2), reject_every_other_run()
        ).transmit(PAYLOAD),
        0.0,
    )

    assert single.delivered_fraction == 0.5
    assert (single.delivered_bits, single.erased_bits, single.bit_error_rate) == (
        6,
        6,
        0.0,
    )
    assert retried.delivered_fraction == 1.0
    assert (
        retried.states,
        retried.rejection_rate,
        retried.delivered_bits_per_state,
    ) == (32, 0.5, 12 / 32)
    # Every one of the 4 blocks is rejected once, then retried successfully.
    assert (retried.blocks, retried.retries, retried.rejected) == (4, 4, 4)
    # Each 1-symbol send has 2 control checks and 1 decoy; rejected sends fail both controls.
    assert (retried.checks, retried.failed_checks) == (24, 8)


def test_bit_error_rate_is_undefined_when_nothing_is_released(eavesdropper):
    metrics = measure(
        SrikaraSimulator(SimulatorConfig(), eavesdropper()).transmit(PAYLOAD), 0.0
    )

    assert metrics.erasure_rate == 1.0
    assert metrics.bit_error_rate is None
    assert metrics.delivered_bits == 0


def test_noise_sweeps_change_only_their_component():
    medium = NOISES["medium"]
    studies = {
        study.name: study for study in noise_studies("medium", WORKLOADS["light"])
    }

    for case in studies["channel_transmittance"].cases:
        noise = case.simulator.noise
        assert noise.forward.transmittance == noise.backward.transmittance == case.at[0]
        assert noise.forward.nbar == medium.forward.nbar
        assert noise.alice_detector == medium.alice_detector
    for case in studies["detector_efficiency"].cases:
        noise = case.simulator.noise
        assert noise.bob_detector.efficiency == case.at[0]
        assert (
            noise.bob_detector.electronic_variance
            == medium.bob_detector.electronic_variance
        )
        assert noise.forward == medium.forward


def test_repetitions_use_new_seeds_and_pool_their_counts():
    config = SimulatorConfig(backend="sf-sampled", tolerance_sigmas=3.0)
    case = Case(config, Workload(payload_bits=30))
    [single] = run_benchmark(Benchmark("once", (case,))).runs
    [repeated] = run_benchmark(Benchmark("thrice", (case,)), repetitions=3).runs

    # Repetition 0 is the configured run; timing is the only difference.
    assert replace(repeated.repetitions[0], seconds=0) == replace(
        single.metrics, seconds=0
    )
    assert len({m.raw_error_bits for m in repeated.repetitions}) > 1
    assert repeated.metrics.payload_bits == 90
    assert repeated.metrics == pool(repeated.repetitions)


def test_heatmap_report_has_one_figure_per_series(tmp_path):
    workload = Workload(payload_bits=6)
    benchmark = Benchmark(
        "grid",
        tuple(
            Case(
                SimulatorConfig(alpha_bound=a, tolerance_sigmas=t),
                workload,
                series=f"tolerance {t}",
                at=(a, r),
            )
            for t in (1.0, 2.0)
            for a in (1.0, 2.0)
            for r in (0.1, 0.2)
        ),
        axes=("alpha", "r"),
    )
    report = write_report(run_benchmark(benchmark), tmp_path)

    assert sorted(path.name for path in (report / "plots").iterdir()) == [
        "heatmap_1.png",
        "heatmap_2.png",
    ]
    assert (
        json.loads((report / "results.json").read_text())["summary"][
            "delivered_fraction"
        ]
        == 1.0
    )


def test_cli_runs_a_study_into_a_browsable_report(tmp_path, monkeypatch):
    monkeypatch.setitem(WORKLOADS, "light", Workload(payload_bits=6))
    cli.main(
        [
            "run",
            "--study",
            "squeezing_distributions",
            "--noise",
            "low",
            "--workload",
            "light",
            "--output-root",
            str(tmp_path),
        ]
    )

    [results] = (tmp_path / "light" / "low" / "squeezing_distributions").glob(
        "run_*/results.json"
    )
    document = json.loads(results.read_text())
    assert document["benchmark"]["layout"] == "comparison"
    assert len(document["runs"]) == 9
    assert {run["workload"]["payload_bits"] for run in document["runs"]} == {6}
    with (results.parent / "runs.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == 9
    assert (results.parent / "plots" / "comparison.png").is_file()
    assert (
        "Squeezing r: U[0.115, 1.151]" in (results.parent / "report.html").read_text()
    )
    assert "light/low/squeezing_distributions" in (tmp_path / "index.html").read_text()


def test_reports_can_be_rerendered_without_simulating(tmp_path):
    case = Case(SimulatorConfig(), Workload(payload_bits=6))
    result = run_benchmark(Benchmark("tiny", (case,)), repetitions=2)
    report = write_report(result, tmp_path)

    assert load_result(report / "results.json").runs == result.runs
    (report / "report.html").unlink()
    rerender(report / "results.json")
    assert (report / "report.html").is_file()
    assert (report / "plots" / "comparison.png").is_file()
