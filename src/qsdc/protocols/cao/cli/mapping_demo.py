"""Run the Cao Gaussian-mapping demo."""

from __future__ import annotations

import argparse

from qsdc.protocols.cao.simulator.backends import make_backend
from qsdc.protocols.cao.simulator.config import MappingConfig
from qsdc.protocols.cao.simulator.protocol import simulate_mapping


def main() -> None:
    defaults = MappingConfig.from_options()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", default="hello")
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--variance", type=float, default=defaults.gaussian_variance)
    parser.add_argument("--box-bits", type=int, default=defaults.box_bit_length)
    parser.add_argument("--squeeze-r", type=float, default=defaults.squeeze_r)
    parser.add_argument("--encoding", default=defaults.encoding)
    parser.add_argument("--backend", choices=("analytic",), default="analytic")
    args = parser.parse_args()

    result = simulate_mapping(
        args.message,
        config=MappingConfig.from_options(
            gaussian_variance=args.variance,
            box_bit_length=args.box_bits,
            squeeze_r=args.squeeze_r,
            seed=args.seed,
            encoding=args.encoding,
        ),
        backend=make_backend(args.backend),
    )

    print(f"message = {result.message!r}")
    print(f"backend = {result.backend_name}")
    print(f"accepted = {result.accepted}")
    print(f"round trip = {result.round_trip_ok}")
    for box in result.boxes:
        print(
            f"{box.index}: {box.bits} -> {box.recovered_bits}, "
            f"x={box.x_value:.6f}, measured={box.measured_x:.6f}"
        )


if __name__ == "__main__":
    main()
