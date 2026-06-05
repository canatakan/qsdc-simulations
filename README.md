# QSDC Simulations

Independent QSDC protocol simulators organized by the paper reference.

Importable code lives under `src/qsdc`, tests live under `tests`, checked-in
benchmark presets live with their benchmark package, and paper notes live under
`docs`.

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

## Commands

```bash
make test
make srikara/demo/sf
make srikara/demo/sf-sampled
```
