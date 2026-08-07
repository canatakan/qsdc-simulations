import numpy as np
import pytest
import strawberryfields as sf
from pydantic import ValidationError
from strawberryfields import ops

from qsdc.protocols.srikara.simulator.backends.strawberryfields.noisy import (
    SFNoiseBackend,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.sampled import (
    SFSampledBackend,
)
from qsdc.protocols.srikara.configuration.models import NoiseConfig
from qsdc.protocols.srikara.simulator.noise import (
    DetectorInefficiency,
    ElectronicNoise,
    NoiseModel,
    PureLoss,
    ThermalLoss,
)


def noise(**stages):
    return NoiseModel(stages)


def test_effects_are_executable_and_independently_composable():
    model = noise(
        forward=(PureLoss(0.9),),
        alice_delay=(PureLoss(0.7),),
        return_path=(ThermalLoss(0.8, 0.02),),
        bob_detector=(DetectorInefficiency(0.6),),
    )
    backend = SFNoiseBackend(model)

    program = backend._returned_program(1 + 2j, 0.3, 0.4, 0.5 + 0.5j)
    operation_types = [type(command.op) for command in program.circuit]

    assert operation_types == [
        ops.Dgate,
        ops.Sgate,
        ops.LossChannel,
        ops.LossChannel,
        ops.Dgate,
        ops.ThermalLossChannel,
        ops.Sgate,
        ops.LossChannel,
    ]
    assert float(program.circuit[2].op.p[0]) == pytest.approx(0.9)
    assert float(program.circuit[3].op.p[0]) == pytest.approx(0.7)
    assert float(program.circuit[5].op.p[0]) == pytest.approx(0.8)
    assert float(program.circuit[5].op.p[1]) == pytest.approx(0.02)
    assert float(program.circuit[7].op.p[0]) == pytest.approx(0.6)


def test_control_pipeline_places_forward_and_alice_detector_effects():
    backend = SFNoiseBackend(
        noise(
            forward=(ThermalLoss(0.8, 0.02),),
            alice_detector=(DetectorInefficiency(0.6),),
        )
    )

    program = backend._control_program(1 + 2j, 0.3, 0.4)
    operation_types = [type(command.op) for command in program.circuit]

    assert operation_types == [
        ops.Dgate,
        ops.Sgate,
        ops.ThermalLossChannel,
        ops.Sgate,
        ops.LossChannel,
    ]
    assert float(program.circuit[2].op.p[0]) == pytest.approx(0.8)
    assert float(program.circuit[2].op.p[1]) == pytest.approx(0.02)
    assert float(program.circuit[4].op.p[0]) == pytest.approx(0.6)


def test_alice_delay_applies_only_to_stored_modes_before_message_encoding():
    backend = SFNoiseBackend(noise(alice_delay=(PureLoss(0.64),)))

    control_program = backend._control_program(1 + 0j, 0.0, 0.0)
    returned_program = backend._returned_program(
        1 + 0j,
        0.0,
        0.0,
        0.5 + 0.5j,
    )

    assert not any(
        isinstance(command.op, ops.LossChannel)
        for command in control_program.circuit
    )
    assert [type(command.op) for command in returned_program.circuit] == [
        ops.Dgate,
        ops.Sgate,
        ops.LossChannel,
        ops.Dgate,
        ops.Sgate,
    ]
    assert float(returned_program.circuit[2].op.p[0]) == pytest.approx(0.64)


def test_alice_delay_changes_expected_baseline_not_message_response():
    backend = SFNoiseBackend(noise(alice_delay=(PureLoss(0.64),)))

    expectation = backend.returned_expectation(
        alpha=1.5 + 0j,
        squeeze_r=0.0,
        theta=0.0,
        axis="q",
    )

    assert expectation.mean == pytest.approx(0.8 * 1.5)
    assert backend.message_response_factor(0.0, 0.0, "q") == pytest.approx(1.0)


def test_sf_moments_match_thermal_loss_and_detector_calculation():
    backend = SFNoiseBackend(
        noise(
            return_path=(ThermalLoss(0.64, 0.5),),
            bob_detector=(DetectorInefficiency(0.64),),
        )
    )
    program = backend._returned_program(
        alpha=1.5 + 0j,
        squeeze_r=0.0,
        theta=0.0,
        beta=0.75 + 0.75j,
    )

    state = sf.Engine("gaussian").run(program).state
    reported_mean = float(state.means()[0]) / 2.0
    reported_variance = float(state.cov()[0, 0]) / 4.0

    vacuum_variance = 0.25
    mean_after_thermal_loss = np.sqrt(0.64) * (1.5 + 0.75)
    variance_after_thermal_loss = (
        0.64 * vacuum_variance
        + (1.0 - 0.64) * (2.0 * 0.5 + 1.0) * vacuum_variance
    )
    expected_mean = np.sqrt(0.64) * mean_after_thermal_loss
    expected_variance = (
        0.64 * variance_after_thermal_loss
        + (1.0 - 0.64) * vacuum_variance
    )

    assert reported_mean == pytest.approx(expected_mean)
    assert reported_variance == pytest.approx(expected_variance)


def test_returned_expectation_includes_calibrated_optical_and_readout_noise():
    backend = SFNoiseBackend(
        noise(
            return_path=(ThermalLoss(0.64, 0.5),),
            bob_detector=(DetectorInefficiency(0.64),),
            bob_readout=(ElectronicNoise(0.5),),
        )
    )

    expectation = backend.returned_expectation(
        alpha=1.5 + 0j,
        squeeze_r=0.0,
        theta=0.0,
        axis="q",
    )

    variance_after_thermal_loss = 0.64 * 0.25 + 0.36 * 0.5
    variance_after_detector = 0.64 * variance_after_thermal_loss + 0.36 * 0.25
    expected_variance = variance_after_detector + 0.5 * 0.25
    assert expectation.mean == pytest.approx(0.8 * 0.8 * 1.5)
    assert expectation.sigma == pytest.approx(np.sqrt(expected_variance))


def test_noisy_measurement_executes_sf_once_and_homodyne_once(monkeypatch):
    import qsdc.protocols.srikara.simulator.backends.strawberryfields.noisy as noisy

    executed_programs = []

    class FakeResult:
        samples = np.array([[1.5]])

    class FakeEngine:
        def __init__(self, backend_name):
            assert backend_name == "gaussian"

        def run(self, program):
            executed_programs.append(program)
            return FakeResult()

    monkeypatch.setattr(noisy.sf, "Engine", FakeEngine)
    backend = SFNoiseBackend(noise(forward=(PureLoss(0.9),)))

    measured = backend.control_measurement(1 + 0j, 0.2, 0.1, "q")

    assert measured == pytest.approx(0.75)
    assert len(executed_programs) == 1
    homodyne_count = sum(
        isinstance(command.op, ops.MeasureHomodyne)
        for command in executed_programs[0].circuit
    )
    assert homodyne_count == 1


def test_electronic_noise_is_one_separate_post_measurement_draw(monkeypatch):
    draws = []

    def fake_normal(mean, sigma):
        draws.append((mean, sigma))
        return 0.125

    monkeypatch.setattr(
        "qsdc.protocols.srikara.simulator.noise.effects.np.random.normal",
        fake_normal,
    )
    effect = ElectronicNoise(variance_snu=0.04)

    assert effect.apply(2.0) == pytest.approx(2.125)
    assert draws == [(0.0, pytest.approx(0.1))]


def test_zero_electronic_noise_does_not_draw(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("zero electronic variance must not sample")

    monkeypatch.setattr(
        "qsdc.protocols.srikara.simulator.noise.effects.np.random.normal",
        fail_if_called,
    )

    assert ElectronicNoise(0.0).apply(2.0) == 2.0


def test_empty_noise_model_matches_sf_sampled_for_same_seed():
    noisy = SFNoiseBackend()
    sampled = SFSampledBackend()

    noisy.begin_run(17)
    noisy_value = noisy.returned_measurement(0.5 + 0.2j, 0.3, 0.7, 0.1 + 0.1j, "p")
    sampled.begin_run(17)
    sampled_value = sampled.returned_measurement(
        0.5 + 0.2j, 0.3, 0.7, 0.1 + 0.1j, "p"
    )

    assert noisy_value == pytest.approx(sampled_value)


def test_message_response_includes_return_and_bob_detector_gain():
    backend = SFNoiseBackend(
        noise(
            forward=(PureLoss(0.01),),
            return_path=(PureLoss(0.25),),
            bob_detector=(DetectorInefficiency(0.25),),
        )
    )

    assert backend.message_response_factor(0.0, 0.0, "q") == pytest.approx(0.25)
    assert backend.measurement_noise_sigma == pytest.approx(0.5)


def test_backend_configuration_round_trip_builds_executable_effects():
    raw = {
        "forward": [{"type": "loss", "transmittance": 0.9}],
        "alice_delay": [{"type": "loss", "transmittance": 0.7}],
        "return_path": [
            {
                "type": "thermal_loss",
                "transmittance": 0.8,
                "environment_nbar": 0.02,
            }
        ],
        "bob_detector": [
            {"type": "detector_inefficiency", "efficiency": 0.6}
        ],
        "bob_readout": [
            {"type": "electronic_noise", "variance_snu": 0.0042}
        ],
    }

    model = NoiseConfig.model_validate(raw).build()

    assert isinstance(model.at("forward")[0], PureLoss)
    assert isinstance(model.at("alice_delay")[0], PureLoss)
    assert isinstance(model.at("return_path")[0], ThermalLoss)
    assert isinstance(model.at("bob_detector")[0], DetectorInefficiency)
    assert isinstance(model.at("bob_readout")[0], ElectronicNoise)
    serialized = NoiseConfig.from_runtime(model).model_dump(mode="json")
    assert serialized["forward"] == raw["forward"]
    assert serialized["alice_delay"] == raw["alice_delay"]
    assert serialized["return_path"] == raw["return_path"]
    assert serialized["bob_detector"] == raw["bob_detector"]
    assert serialized["bob_readout"] == raw["bob_readout"]
    assert serialized["alice_detector"] == []
    assert serialized["alice_readout"] == []


@pytest.mark.parametrize(
    "raw, location, error_code",
    [
        (
            {
                "name": "sf-noise",
                "noise": {
                    "forward": [
                        {"type": "electronic_noise", "variance_snu": 0.1}
                    ]
                },
            },
            ("forward", 0),
            "union_tag_invalid",
        ),
        (
            {
                "name": "sf-noise",
                "noise": {
                    "bob_readout": [
                        {"type": "loss", "transmittance": 0.9}
                    ]
                },
            },
            ("bob_readout", 0, "type"),
            "literal_error",
        ),
        (
            {"name": "sf-noise", "noise": {"unknown": []}},
            ("unknown",),
            "extra_forbidden",
        ),
    ],
)
def test_noise_configuration_rejects_effects_at_wrong_stage(
    raw, location, error_code
):
    with pytest.raises(ValidationError) as exc_info:
        NoiseConfig.model_validate(raw["noise"])

    assert any(
        error["loc"][-len(location):] == location
        and error["type"] == error_code
        for error in exc_info.value.errors()
    )


@pytest.mark.parametrize(
    "raw, location, error_code",
    [
        (
            {
                "name": "sf-noise",
                "noise": {"forward": [{"type": "loss"}]},
            },
            ("forward", 0, "loss", "transmittance"),
            "missing",
        ),
        (
            {
                "name": "sf-noise",
                "noise": {
                    "forward": [
                        {
                            "type": "loss",
                            "transmittance": 0.9,
                            "extra": 1,
                        }
                    ]
                },
            },
            ("forward", 0, "loss", "extra"),
            "extra_forbidden",
        ),
        (
            {
                "name": "sf-noise",
                "noise": {
                    "forward": [{"type": "loss", "transmittance": 1.1}]
                },
            },
            ("forward", 0, "loss", "transmittance"),
            "less_than_equal",
        ),
        (
            {
                "name": "sf-noise",
                "noise": {
                    "bob_readout": [
                        {"type": "electronic_noise", "variance_snu": "0.1"}
                    ]
                },
            },
            ("bob_readout", 0, "variance_snu"),
            "float_type",
        ),
        (
            {
                "name": "sf-noise",
                "noise": {
                    "return_path": [
                        {
                            "type": "thermal_loss",
                            "transmittance": 0.9,
                            "environment_nbar": float("inf"),
                        }
                    ]
                },
            },
            ("return_path", 0, "thermal_loss", "environment_nbar"),
            "finite_number",
        ),
    ],
)
def test_backend_configuration_rejects_invalid_nested_values(
    raw, location, error_code
):
    with pytest.raises(ValidationError) as exc_info:
        NoiseConfig.model_validate(raw["noise"])

    assert any(
        error["loc"][-len(location):] == location
        and error["type"] == error_code
        for error in exc_info.value.errors()
    )


def test_noise_model_applies_any_configured_stage_parametrically():
    calls = []

    class Effect:
        def apply(self, value):
            calls.append(value)
            return value + 1

    model = noise(custom=(Effect(), Effect()))

    assert model.apply("custom", 3) == 5
    assert model.apply("missing", 3) == 3
    assert calls == [3, 4]
