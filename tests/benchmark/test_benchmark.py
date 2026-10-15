import csv
import json
from dataclasses import replace

from qsdc.benchmark import cli
from qsdc.benchmark.benchmark import Benchmark, Case, Workload, run_benchmark
from qsdc.benchmark.metrics import RunMetrics
from qsdc.benchmark.report.report import load_result, rerender, write_report
from qsdc.benchmark.studies.srikara.suite import SRIKARA
from qsdc.protocols.srikara.config import SimulatorConfig


def test_repetitions_use_new_seeds_and_pool_their_counts():
    config = SimulatorConfig(backend="sf-sampled", tolerance_sigmas=3.0)
    case = Case(config, Workload(payload_bits=30))
    [single] = run_benchmark(Benchmark(SRIKARA, "once", (case,))).runs
    [repeated] = run_benchmark(
        Benchmark(SRIKARA, "thrice", (case,)), repetitions=3
    ).runs

    assert replace(repeated.repetitions[0], seconds=0) == replace(
        single.metrics, seconds=0
    )
    assert len({m.raw_error_bits for m in repeated.repetitions}) > 1
    assert repeated.metrics.payload_bits == 90
    assert repeated.metrics == RunMetrics.pool(repeated.repetitions)


def test_heatmap_report_has_one_figure_per_series(tmp_path):
    workload = Workload(payload_bits=6)
    benchmark = Benchmark(
        SRIKARA,
        "grid",
        tuple(
            Case(
                SimulatorConfig(alpha_variance_snu=a, tolerance_sigmas=t),
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

    runs = json.loads((report / "results.json").read_text())["runs"]
    assert {run["metrics"]["delivered_fraction"] for run in runs} == {1.0}


def test_cli_runs_a_study_into_a_browsable_report(tmp_path):
    cli.main(
        [
            "srikara",
            "run",
            "--study",
            "squeezing_distributions",
            "--payload-bits",
            "6",
            "--output-root",
            str(tmp_path),
        ],
    )

    [results] = (tmp_path / "squeezing_distributions").glob("run_*/results.json")
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
    assert "squeezing_distributions/run_" in (tmp_path / "index.html").read_text()


def test_reports_can_be_rerendered_without_simulating(tmp_path):
    case = Case(SimulatorConfig(), Workload(payload_bits=6))
    result = run_benchmark(Benchmark(SRIKARA, "tiny", (case,)), repetitions=2)
    report = write_report(result, tmp_path)

    assert load_result(report / "results.json", SRIKARA).runs == result.runs

    (report / "report.html").unlink()
    rerender(report / "results.json", SRIKARA)

    assert (report / "report.html").is_file()
    assert (report / "plots" / "comparison.png").is_file()
