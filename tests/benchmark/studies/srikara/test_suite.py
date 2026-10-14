import pytest

from qsdc.benchmark.benchmark import Workload
from qsdc.benchmark.metrics import RunMetrics
from qsdc.benchmark.studies.catalog import Catalog
from qsdc.benchmark.studies.srikara.suite import SRIKARA
from qsdc.protocols.srikara.config import NOISES, SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import Simulator

PAYLOAD = "101001110010"


def measure(simulator: Simulator, payload: str) -> RunMetrics:
    return SRIKARA.measure(simulator.config, simulator.transmit(payload), 0.0)


def test_ideal_run_delivers_every_bit():
    metrics = measure(Simulator(SimulatorConfig()), PAYLOAD)

    assert metrics.delivered_fraction == 1.0
    assert (metrics.bit_error_rate, metrics.erasure_rate) == (0.0, 0.0)
    assert metrics.aborted_attempts == 0
    assert metrics.delivered_bits_per_state == 12 / 16


def test_noiseless_channel_carries_three_bits_per_message_state():
    every_symbol = "000001010011100101110111"
    metrics = measure(Simulator(SimulatorConfig()), every_symbol)

    assert metrics.information_per_state == pytest.approx(3 / 4)


def test_aborted_attempts_count_erasures_and_retry_states(reject_every_other_run):
    single = measure(Simulator(SimulatorConfig(), reject_every_other_run()), PAYLOAD)
    retried = measure(
        Simulator(SimulatorConfig(max_attempts=2), reject_every_other_run()),
        PAYLOAD,
    )

    assert single.delivered_fraction == 0.0
    assert (single.delivered_bits, single.erased_bits, single.bit_error_rate) == (
        0,
        12,
        None,
    )

    assert retried.delivered_fraction == 1.0
    assert (retried.states, retried.delivered_bits_per_state) == (32, 12 / 32)
    assert (retried.blocks, retried.retries, retried.aborted_attempts) == (4, 4, 1)

    # Aborted sends end after their 2 control checks; accepted ones also check a decoy.
    assert (retried.checks, retried.failed_checks) == (20, 8)
    assert retried.raw_bits == 12


def test_raw_bit_error_rate_is_undefined_when_every_send_is_aborted(
    reject_every_other_run,
):
    metrics = measure(Simulator(SimulatorConfig(), reject_every_other_run()), "101")

    assert metrics.raw_bits == 0
    assert metrics.as_dict()["raw_bit_error_rate"] is None


def test_bit_error_rate_is_undefined_when_nothing_is_released(eavesdropper):
    metrics = measure(Simulator(SimulatorConfig(), eavesdropper()), PAYLOAD)

    assert metrics.erasure_rate == 1.0
    assert metrics.bit_error_rate is None
    assert metrics.delivered_bits == 0


def test_noise_sweeps_change_only_their_component():
    lab = NOISES["lab"]
    by_name = {study.name: study for study in Catalog(SRIKARA).studies(Workload())}

    for case in by_name["channel_transmittance"].cases:
        noise = case.simulator.noise
        assert noise.forward.transmittance == noise.backward.transmittance == case.at[0]
        assert noise.forward.nbar == lab.forward.nbar
        assert noise.alice_detector == lab.alice_detector

    for case in by_name["detector_efficiency"].cases:
        noise = case.simulator.noise
        assert noise.bob_detector.efficiency == case.at[0]
        assert (
            noise.bob_detector.electronic_variance
            == lab.bob_detector.electronic_variance
        )
        assert noise.forward == lab.forward


def test_noise_dependent_comparisons_run_every_case_under_every_baseline():
    ladder = {study.name: study for study in Catalog(SRIKARA).studies(Workload())}[
        "optimization_comparison"
    ]
    steps = len(ladder.cases) // len(NOISES)

    assert [case.series for case in ladder.cases] == [
        noise for noise in NOISES for _ in range(steps)
    ]

    for case in ladder.cases:
        assert case.simulator.noise == NOISES[case.series]
