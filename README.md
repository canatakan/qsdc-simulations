# QSDC Simulations

Independent QSDC protocol simulators organized by protocol/paper reference.

Importable code lives under `src/qsdc`, reusable utilities live under
`src/qsdc/common`, protocol implementations live under
`src/qsdc/protocols/<protocol>`, demos live under `demos/<protocol>`, and paper
notes live under `docs/protocols/<protocol>`.

## Setup

From this repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install
```

## Simulators

- `srikara`: CV QSDC Gaussian-states simulator with analytic and Strawberry Fields backends.

  The simulator optionally applies pure-Python extended Hamming
  SECDED (8,4,4) coding with a depth-3 interleaver. Each 12-bit payload stripe
  becomes an independently accepted 32-state transport block. Failed blocks
  can be retried with an explicit bound; rejected blocks never expose a
  delivered payload.

  > Reference: S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).

## Commands

```bash
make test
make srikara/test
make srikara/demo/basic
make srikara/demo/analytic
make srikara/demo/sf
make srikara/demo/sf-sampled
```

Benchmark configs are stored with the benchmark package:

```bash
cd src/qsdc/protocols/srikara/benchmark
srikara-benchmark
```

## Srikara payload error correction

```python
from qsdc.protocols.srikara.configuration.simulator import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import simulate_qsdc

config = SimulatorConfig(
    error_correction="secded",
    max_attempts_per_block=3,
    seed=11,
)
result = simulate_qsdc("101001110010", config)

assert result.delivery_status == "recovered"
assert result.recovered_bits == "101001110010"
```

`simulate_qsdc` is the only transmission API. Payload framing, correction,
and bounded selective retries are controlled entirely by `SimulatorConfig`.
Benchmark comparison configs live under
`src/qsdc/protocols/srikara/benchmark/configs/error_correction/`.

Benchmark CSV files contain only scalar setup fields and defined measurements;
they do not embed JSON configuration or retry blobs. The generated HTML report
includes the formulas for every headline metric, including separate raw-channel
and post-FEC error rates.

For a compact, interactive optimized message transfer demo:

```bash
python demos/srikara/optimized_message.py "hello"
python demos/srikara/optimized_message.py "hello" --noise --secded --max-attempts 3
```
