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

  > Reference: S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).

- `cao`: CV QSDC Gaussian-mapping simulator with an analytic backend,
  paper-style bit uniformization, detection/parity checks, equiprobable
  Gaussian mapping, and inverse message recovery.

  > Reference: Z. Cao et al., Continuous-Variable Quantum Secure Direct
  > Communication Based on Gaussian Mapping, Phys. Rev. Applied 16, 024012
  > (2021). See `docs/protocols/cao/methodology.md` for the implementation map
  > and model assumptions.

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
