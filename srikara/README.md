# CV QSDC Gaussian States

CV QSDC Gaussian-states protocol simulation with analytic and Strawberry Fields
backends.

The implementation includes:

- analytic backend for formula-level checks
- Strawberry Fields backend for Gaussian circuit execution
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

## Tests

```bash
python -m pytest tests
```

## Layout

```text
simulator/
  backends.py      # analytic and Strawberry Fields backends
  encoding.py      # 3-bit interval encoding
  gaussian.py      # Gaussian-state identities and SF amplitude conversions
  protocol.py      # Alice-Bob QSDC protocol orchestration
  cli/             # qsdc-demo command implementation
tests/
method.pdf
pyproject.toml
```
