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
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install
```

This installs the package, dependencies, test dependency, and benchmark console
commands.

## Quick Start

Transmit a text message through the verbose channel demo:

```bash
python demos/srikara/message.py "hello" --backend sf
```

Use `sf-sampled` to run actual sampled homodyne measurements:

```bash
python demos/srikara/message.py "hello" --backend sf-sampled
```

Use the Strawberry Fields beam-splitter QRNG simulation for protocol choices:

```bash
python demos/srikara/message.py "hello" --backend sf --random-source sf-bs-qrng
```

Print a hand-checkable one-symbol calculation:

```bash
python demos/srikara/basic.py
```

The `analytic` backend is the exact formula reference. The `sf` backend uses
Strawberry Fields gates and reads exact state means, matching the paper-level
ideal protocol. The `sf-sampled` backend uses Strawberry Fields homodyne
measurement samples, so decoded symbols can differ from the sent symbols.

If `--tolerance-sigmas` is omitted, the backend chooses the control/decoy
sigma tolerance. `analytic` and `sf` use one numerical-precision sigma, while
`sf-sampled` uses a 4-sigma homodyne threshold derived from Strawberry Fields'
`hbar`.

## Tests

```bash
make srikara/test
```

## Layout

```text
docs/protocols/srikara/
  README.md
  benchmark.md
  method.pdf
demos/srikara/
  basic.py
  message.py
src/qsdc/common/
  bits.py
  random/
    base.py
    classical.py
    sf_beamsplitter.py
src/qsdc/protocols/srikara/
  simulator/
    config.py
    distributions.py
    encoding.py
    flow.py
    protocol.py
    backends/
      base.py
      analytic/
        calculations.py
        ideal.py
      strawberryfields/
        calculations.py
        ideal.py
        sampled.py
  benchmark/
    config.py
    engine.py
    metrics.py
    seeds.py
    cli.py
    configs/
      sf.json
      test.json
    artifacts/
      output.py
      plots.py
      workbook.py
tests/protocols/srikara/
  simulator/
  benchmark/
```
