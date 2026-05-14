# CV QSDC Gaussian States

CV QSDC Gaussian-states protocol simulation with analytic and Strawberry Fields
backends.

The implementation includes:

- analytic backend for formula-level checks
- Strawberry Fields ideal backend using Gaussian circuit execution with state
  means
- Strawberry Fields sampled backend using Gaussian circuit execution with
  homodyne measurements
- protocol random-source abstraction with classical and SF beam-splitter QRNG
  simulations
- optical-switch, delay-buffer, and public-announcement flow records
- detailed text-message transfer demo
- method note in `method.pdf`

## Setup

From the `qsdc-simulations` repository root:

```bash
cd srikara
python3.9 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

This installs the package, dependencies, test dependency, and the `qsdc-demo`
console command.

## Quick Start

Transmit a text message through the verbose channel demo:

```bash
qsdc-demo "hello" --backend sf
```

Use `sf-sampled` to run actual sampled homodyne measurements:

```bash
qsdc-demo "hello" --backend sf-sampled
```

Average repeated homodyne samples in the sampled backend:

```bash
qsdc-demo "hello" --backend sf-sampled --repetitions 100
```

Use the Strawberry Fields beam-splitter QRNG simulation for protocol choices:

```bash
qsdc-demo "hello" --backend sf --random-source sf-bs-qrng
```

Print a hand-checkable one-symbol calculation:

```bash
qsdc-basic-demo
```

The `analytic` backend is the exact formula reference. The `sf` backend uses
Strawberry Fields gates and reads exact state means, matching the paper-level
ideal protocol. The `sf-sampled` backend uses Strawberry Fields homodyne
measurement samples, so decoded symbols can differ from the sent symbols.

If `--tolerance` is omitted, the backend chooses the control/decoy tolerance:
`analytic` and `sf` use `1e-7`, while `sf-sampled` uses a 4-sigma homodyne
threshold derived from Strawberry Fields' `hbar`. With `--repetitions N`, the
sampled tolerance scales by `1 / sqrt(N)`.

## Tests

```bash
python -m pytest tests
```

## Layout

```text
simulator/
  backends/
    analytic/      # analytic backend and calculations
    sf/            # SF ideal/sampled backends and calculations
  core/
    config.py      # protocol settings, validation, and backend tolerances
    encoding.py    # 3-bit interval encoding
    flow.py        # optical switching, delay, and announcement records
    protocol.py    # CV QSDC protocol orchestration
    random_source.py
  cli/             # qsdc-demo command implementation
tests/
method.pdf
pyproject.toml
```
