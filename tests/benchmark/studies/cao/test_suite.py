import json

from qsdc.benchmark import cli
from qsdc.benchmark.benchmark import Workload
from qsdc.benchmark.report.report import load_result
from qsdc.benchmark.studies.cao.suite import CAO
from qsdc.benchmark.studies.catalog import Catalog
from qsdc.protocols.cao.config import NOISES, PRESETS, SimulatorConfig
from qsdc.protocols.cao.simulator.backends import AnalyticBackend
from qsdc.protocols.cao.simulator.protocol import CaoSimulator


def test_noiseless_run_delivers_every_bit_and_counts_the_pairs():
    config = SimulatorConfig()
    transmission = CaoSimulator(config, AnalyticBackend(0.0)).transmit("1011")

    metrics = CAO.measure(config, transmission, 0.0)

    assert metrics.delivered_fraction == 1.0
    assert metrics.bit_error_rate == 0.0
    assert metrics.states == 2 * config.check_pairs + config.boxes
    assert metrics.checks == 2 * config.check_pairs
    assert metrics.raw_error_bits == 0
    assert metrics.alphabet == 8


def test_catalog_builds_valid_studies_for_every_baseline():
    studies = {study.name: study for study in Catalog(CAO).studies(Workload())}

    sweep = studies["syndrome_fraction"]
    fractions = [
        case.simulator.reconciliation.syndrome_fraction for case in sweep.cases
    ]
    assert fractions == [case.at[0] for case in sweep.cases]

    for case in studies["noise_profiles"].cases:
        assert case.simulator.noise == NOISES[case.series]


def test_cli_runs_a_study_into_a_report_that_reloads(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "WORKLOAD", Workload(payload_bits=40))
    cli.main(
        CAO, ["run", "--study", "paper_comparison", "--output-root", str(tmp_path)]
    )

    [results] = (tmp_path / "paper_comparison").glob("run_*/results.json")
    document = json.loads(results.read_text())
    assert len(document["runs"]) == 6
    assert "Boxes per block" in (results.parent / "report.html").read_text()

    [first, *_] = load_result(results, CAO).runs
    assert first.case.simulator == PRESETS["paper"].model_copy(
        update={"noise": NOISES["clean"]}
    )
