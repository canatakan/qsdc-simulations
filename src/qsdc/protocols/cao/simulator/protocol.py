"""Cao Gaussian-mapping protocol orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.bits import bits_to_bytes, bytes_to_bits, chunk_bits
from qsdc.common.gaussian import EncodingInterval
from qsdc.common.random.base import RandomSource
from qsdc.common.random.classical import ClassicalRandomSource
from qsdc.protocols.cao.simulator.backends.analytic.ideal import AnalyticBackend
from qsdc.protocols.cao.simulator.backends.base import (
    CorrelationNoise,
    GaussianMappingBackend,
    VacuumQuadratures,
)
from qsdc.protocols.cao.simulator.config import MappingConfig
from qsdc.protocols.cao.simulator.encoding import (
    bits_for_real,
    decode_box,
    encode_box,
    gaussian_encoding,
    interval_for_bits,
    sample_gaussian,
    sample_gaussian_from_interval,
    restore_block_bits,
    restore_message_bits,
    uniformize_block_bits,
    uniformize_message_bits,
)


@dataclass(frozen=True)
class SecurityCheck:
    index: int
    delta_x: float
    delta_p: float
    noise_power: float


@dataclass(frozen=True)
class MappedBox:
    index: int
    bits: str
    interval: EncodingInterval
    x_value: float
    p_value: float
    correlation_delta_x: float
    correlation_delta_p: float
    measured_x: float
    measured_p: float
    recovered_bits: str
    payload_bits: str
    recovered_payload_bits: str
    detection_positions: tuple[int, ...]
    detection_bits: str
    parity_bit: int
    detection_valid: bool
    parity_valid: bool


@dataclass(frozen=True)
class MappingResult:
    backend_name: str
    random_source_name: str
    message: str
    raw_bits: str
    message_uniformized_bits: str
    block_uniformized_bits: str
    recovered_block_uniformized_bits: str
    recovered_message_uniformized_bits: str
    recovered_raw_bits: str
    recovered_message: str | None
    decoding_error: str | None
    channel_checks: tuple[SecurityCheck, ...]
    authentication_checks: tuple[SecurityCheck, ...]
    channel_accepted: bool
    authentication_accepted: bool
    boxes: tuple[MappedBox, ...]

    @property
    def recovered_box_bits(self) -> tuple[str, ...]:
        return tuple(box.recovered_bits for box in self.boxes)

    @property
    def round_trip_ok(self) -> bool:
        return (
            self.recovered_message == self.message
            and self.recovered_raw_bits == self.raw_bits
            and all(
                box.bits == box.recovered_bits
                and box.detection_valid
                and box.parity_valid
                for box in self.boxes
            )
        )

    @property
    def accepted(self) -> bool:
        return self.channel_accepted and self.authentication_accepted


def simulate_mapping(
    message: str,
    config: MappingConfig | None = None,
    backend: GaussianMappingBackend | None = None,
    random_source: RandomSource | None = None,
) -> MappingResult:
    config = config or MappingConfig.from_options()

    active_backend = backend if backend is not None else AnalyticBackend()
    active_random = random_source or ClassicalRandomSource(config.seed)

    raw_bits = bytes_to_bits(message.encode(config.encoding))
    message_uniformized = uniformize_message_bits(raw_bits)
    block_uniformized = uniformize_block_bits(message_uniformized, active_random)
    payload_boxes = chunk_bits(
        block_uniformized,
        config.payload_box_bit_length,
    )
    mapping = gaussian_encoding(config.box_bit_length, config.gaussian_variance)

    channel_checks = _run_security_checks(
        active_backend,
        active_random,
        config.squeeze_r,
        config.channel_check_count,
    )
    authentication_checks = _run_security_checks(
        active_backend,
        active_random,
        config.squeeze_r,
        config.authentication_check_count,
    )
    channel_accepted = _mean_noise_power(channel_checks) < config.security_threshold
    authentication_accepted = (
        _mean_noise_power(authentication_checks) < config.security_threshold
    )

    boxes: list[MappedBox] = []
    for index, payload_bits in enumerate(payload_boxes):
        encoded_box = encode_box(
            payload_bits,
            config.detection_bit_count,
            active_random,
        )
        bits = encoded_box.mapping_bits
        interval = interval_for_bits(bits, mapping)
        x_value = sample_gaussian_from_interval(
            interval,
            config.gaussian_variance,
            active_random,
        )
        p_value = sample_gaussian(config.gaussian_variance, active_random)
        beams = active_backend.prepare_correlated_beams(
            config.squeeze_r,
            _sample_vacuum(active_random),
        )
        noise = active_backend.correlation_noise(beams)
        modulated = active_backend.modulate(beams, x_value, p_value)
        measurement = active_backend.measure_message(modulated)
        recovered_bits = bits_for_real(
            measurement.x_message - noise.delta_x,
            mapping,
        )
        decoded_box = decode_box(
            recovered_bits,
            encoded_box.detection_positions,
            encoded_box.detection_bits,
            encoded_box.parity_bit,
        )
        boxes.append(
            MappedBox(
                index=index,
                bits=bits,
                interval=interval,
                x_value=x_value,
                p_value=p_value,
                correlation_delta_x=noise.delta_x,
                correlation_delta_p=noise.delta_p,
                measured_x=measurement.x_message,
                measured_p=measurement.p_message,
                recovered_bits=recovered_bits,
                payload_bits=payload_bits,
                recovered_payload_bits=decoded_box.payload_bits,
                detection_positions=encoded_box.detection_positions,
                detection_bits=encoded_box.detection_bits,
                parity_bit=encoded_box.parity_bit,
                detection_valid=decoded_box.detection_valid,
                parity_valid=decoded_box.parity_valid,
            )
        )

    recovered_block_uniformized = "".join(
        box.recovered_payload_bits for box in boxes
    )[:len(block_uniformized)]
    recovered_message_uniformized = restore_block_bits(
        recovered_block_uniformized
    )
    recovered_raw_bits = restore_message_bits(recovered_message_uniformized)
    try:
        recovered_message = bits_to_bytes(recovered_raw_bits).decode(
            config.encoding
        )
        decoding_error = None
    except UnicodeDecodeError as error:
        recovered_message = None
        decoding_error = str(error)

    return MappingResult(
        backend_name=active_backend.name,
        random_source_name=active_random.name,
        message=message,
        raw_bits=raw_bits,
        message_uniformized_bits=message_uniformized,
        block_uniformized_bits=block_uniformized,
        recovered_block_uniformized_bits=recovered_block_uniformized,
        recovered_message_uniformized_bits=recovered_message_uniformized,
        recovered_raw_bits=recovered_raw_bits,
        recovered_message=recovered_message,
        decoding_error=decoding_error,
        channel_checks=channel_checks,
        authentication_checks=authentication_checks,
        channel_accepted=channel_accepted,
        authentication_accepted=authentication_accepted,
        boxes=tuple(boxes),
    )


def _run_security_checks(
    backend: GaussianMappingBackend,
    random_source: RandomSource,
    squeeze_r: float,
    count: int,
) -> tuple[SecurityCheck, ...]:
    checks = []
    for index in range(count):
        beams = backend.prepare_correlated_beams(
            squeeze_r,
            _sample_vacuum(random_source),
        )
        checks.append(_security_check(index, backend.correlation_noise(beams)))
    return tuple(checks)


def _security_check(index: int, noise: CorrelationNoise) -> SecurityCheck:
    return SecurityCheck(
        index=index,
        delta_x=noise.delta_x,
        delta_p=noise.delta_p,
        noise_power=noise.delta_x**2 + noise.delta_p**2,
    )


def _mean_noise_power(checks: tuple[SecurityCheck, ...]) -> float:
    return sum(check.noise_power for check in checks) / len(checks)


def _sample_vacuum(random_source: RandomSource) -> VacuumQuadratures:
    return VacuumQuadratures(
        x1=sample_gaussian(1.0, random_source),
        p1=sample_gaussian(1.0, random_source),
        x2=sample_gaussian(1.0, random_source),
        p2=sample_gaussian(1.0, random_source),
    )
