# QSDC Simulations

Simulators for quantum secure direct communication (QSDC) protocols, one
package per paper. There is currently one: [`srikara`](#srikara-protocol).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install
```

`make install` adds two commands to `.venv/bin`: `srikara-demo` and
`srikara-benchmark`. To run the tests, use `make test` for everything or
`make srikara/test` for the Srikara tests only.

## Layout

| Path | Contents |
| --- | --- |
| `src/qsdc/common/` | Paper-independent helpers: bits, random sources, quadratures, error correction |
| `src/qsdc/protocols/srikara/simulator/` | The protocol and its backends |
| `src/qsdc/protocols/srikara/benchmark/` | Studies, metrics and reports |
| `src/qsdc/protocols/srikara/demo.py` | The demo |
| `tests/` | Tests, laid out like `src/` |

## Srikara protocol

> S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure
> quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).

Alice sends a message to Bob over two optical passes. Each 3-bit symbol uses
4 squeezed coherent states:

1. Bob prepares the states with random α, r and θ and sends them to Alice.
2. Alice checks half of them (the controls) against the values Bob reveals.
   If any control check fails, the run aborts here.
3. Alice displaces a quarter (the messages) by m(1 + i), where the interval of
   m encodes 3 bits. She leaves the last quarter (the decoys) unchanged and
   sends both back.
4. Bob unsqueezes and measures the returned states, checks the decoys, and
   decodes m from the messages.

A run is accepted when every control and decoy check falls within
`tolerance_sigmas` of its expected value. `AGENTS.md` lists every step and
formula.

### Usage

```python
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator

config = SimulatorConfig(error_correction="secded", max_attempts=3)
transmission = SrikaraSimulator(config).transmit("101001110010")
assert transmission.recovered_bits == "101001110010"
```

`SimulatorConfig` (`config.py`) holds every option. Its defaults are the
noiseless paper setting. `recovered_bits` is set only when every block was
released.

### Backends

| `backend` | Behaviour |
| --- | --- |
| `analytic` | The paper's algebra. Ignores `noise`. |
| `sf` | Strawberry Fields Gaussian circuits with noise, read out as exact means |
| `sf-sampled` | The same circuits, read out as homodyne samples |

The Strawberry Fields backends model `noise` as a thermal loss channel in each
direction, Alice's memory, and each party's detector efficiency and electronic
noise. Checks compare against the expectation of the same noisy circuit. If
no signal reaches Bob, he decodes m = 0.

### Measurement axis

`axis_policy` sets the quadrature Bob measures on a message mode. Control and
decoy checks always measure q or p at random.

| `axis_policy` | Bob measures |
| --- | --- |
| `random` | q or p at random, as in the paper |
| `best_qp` | whichever of q and p responds more to Alice's displacement |
| `aligned` | the quadrature along the unsqueezed displacement, which Bob computes from s |

The squeezing angle sets how much signal Bob reads per unit m:

- `aligned` reads the most at θ = 3π/2: √2·e^r.
- q or p alone read the most at θ = 5π/4 or 7π/4: cosh r + √2 sinh r. That is
  about 15% less than `aligned` at the same angle.
- The signal is weakest at θ = π/2.

### Intervals

| `intervals` | Layout |
| --- | --- |
| `default` | The paper's 8 intervals of m, labelled in binary order |
| `gray` | The same intervals with Gray labels, so neighbouring intervals differ by one bit |
| `gaussian_gray` | Cao et al.'s equiprobable intervals for Gaussian m, with Gray labels |

Cao et al. give their intervals for V_A = 8 SNU and a vacuum standard
deviation of 1. Here they are scaled to the paper's mean energy of 64/3 SNU and
to this simulator's vacuum standard deviation of 1/2. Only the layout differs
from `gray`.

### Error correction and retries

| `error_correction` | Payload bits per block | Symbols per block | States per block | Effect |
| --- | --- | --- | --- | --- |
| `none` | 3 | 1 | 4 | none |
| `parity` | 2 | 1 | 4 | detects an odd number of wrong bits |
| `secded` | 12 | 8 | 32 | corrects one wrong symbol per block |

- **Parity:** the parity bit is part of the symbol. Blocks alternate between
  odd and even parity, so all 8 intervals are used and m stays zero-mean, as
  Cao et al. require. With Gray labels, an error into a neighbouring interval is
  always detected.
- **SECDED:** the block is three extended Hamming (8, 4) codewords,
  interleaved so each symbol carries one bit of each codeword.
- **Retries:** a block is sent again, up to `max_attempts` sends in total, when
  its run is rejected or its code finds an error it cannot correct. Each send
  draws fresh states.
- **Padding:** the last block is padded with zeros. The padding is removed
  after decoding.

## Demo

`srikara-demo` sends a text message. It prints one line per send, then every
protocol step of one block. It uses the `retry` simulator under `lab` noise
unless told otherwise.

```bash
srikara-demo "hello"
srikara-demo "hello" --simulator baseline --noise clean
srikara-demo "hello" --noise metro_10km --block 3 --trace
```

| Option | Effect |
| --- | --- |
| `--simulator`, `--noise` | A simulator preset and a noise baseline from the [catalog](#catalog) |
| `--block` | The block to show step by step, counted from 0 (default: the one with the most sends) |
| `--trace` | Adds the noise path of each mode in that block |

`srikara-demo --help` lists every option.

## Benchmarks

### Running

```bash
srikara-benchmark list                                  # list the studies
srikara-benchmark run                                   # run every study
srikara-benchmark run --study theta_band --repetitions 3
srikara-benchmark run --skip-existing                   # resume an interrupted run
srikara-benchmark index                                 # rebuild results/index.html
srikara-benchmark rerender                              # rebuild reports without simulating
```

- `--repetitions N` reruns every case with N seeds and pools their counts. The
  first seed is the configured one.
- `--skip-existing` skips studies that already have a report.
- `rerender` rebuilds the plots, CSV and HTML from each `results.json`.

### Catalog

The presets and studies are YAML files in `benchmark/catalog/`.

**Simulator presets** (`simulators.yaml`). `best_qp` and `aligned` extend
`baseline`; every later preset extends the row above it:

| Preset | Change |
| --- | --- |
| `baseline` | The paper's protocol: `sf-sampled`, θ uniform over 0 to 2π, 3σ checks, r = 0.576 (5 dB) |
| `best_qp` | `baseline` with `best_qp` measurement |
| `aligned` | `baseline` with `aligned` measurement |
| `gray` | Gray labels |
| `optimized` | θ uniform within 3π/2 ± π/4 |
| `parity` | Parity error detection |
| `retry` | Up to 3 sends per block |

**Noise baselines** (`noises.yaml`, with the source of each value):

| Baseline | Fibre per direction | Excess noise | Detectors | Memory |
| --- | --- | --- | --- | --- |
| `clean` | none | 0 | ideal | ideal |
| `lab` | 1 km spool | 0.002 SNU | η = 0.95, 0.01 SNU | 0.95 |
| `metro_5km` | 5 km | 0.005 SNU | η = 0.85, 0.05 SNU | 0.9 |
| `metro_10km` | 10 km | 0.01 SNU | η = 0.8, 0.1 SNU | 0.9 |
| `record_27km` | 27.27 km, ultralow loss | 0.0015 SNU | η = 0.613, 0.122 SNU | 0.9 |

`record_27km` is the shortest link of Zhang et al., PRL 125, 010502 (2020).

**Studies** (`studies.yaml`). There are 19. Each case sends a random
10,000-bit payload under `optimized` unless the study says otherwise.

| Group | Studies | Noise |
| --- | --- | --- |
| Reference | `ideal_backend_check`, `paper_baseline`, `noise_profiles` | `clean`; `noise_profiles` uses all five |
| Signal | `squeezing_r`, `squeezing_distributions`, `theta_fixed`, `theta_band`, `r_theta_heatmap` | `lab` |
| Optimizations | `optimization_comparison`, `axis_comparison`, `interval_comparison`, `error_correction_comparison` | all five |
| Protocol | `tolerance_safety`, `one_probability` | `lab` |
| Hardware | `channel_transmittance`, `thermal_occupation`, `detector_efficiency`, `electronic_noise`, `memory_efficiency` | `lab` |

A study either lists its cases or sweeps one or two axes. Cases change fields
by dotted path, such as `noise.forward.transmittance`. Each noise baseline is
one series in the report. `error_correction_comparison` covers no coding,
parity and SECDED, with retries for parity and SECDED only.

### Custom benchmarks

A `Benchmark` is a name, its `Case`s and its axis names: no axes gives a
comparison, one a sweep, two a heatmap. A `Case` is a `SimulatorConfig`, a
`Workload` (payload size, probability of a one, seed), a series, an optional
label and its coordinates `at`.

```python
from pathlib import Path

from qsdc.protocols.srikara.benchmark.benchmark import Benchmark, Case, Workload, run_benchmark
from qsdc.protocols.srikara.benchmark.catalog import SIMULATORS
from qsdc.protocols.srikara.benchmark.report import write_report

cases = tuple(
    Case(SIMULATORS["optimized"], Workload(payload_bits=1024, one_probability=p), at=(p,))
    for p in (0.1, 0.5, 0.9)
)
benchmark = Benchmark("one_probability", cases, axes=("Probability of one",))
print(write_report(run_benchmark(benchmark), Path("results")) / "report.html")
```

### Output

Each run writes `results/<study>/run_<time>/`, and `results/index.html` links
the latest run of every study.

| File | Contents |
| --- | --- |
| `report.html` | One row per case, plots, sent vs. decoded symbol tables, shared parameters |
| `results.json` | Each case's configuration, counts, rates and per-repetition counts |
| `runs.csv` | One row per case: configuration, axes, metrics and symbol counts |

### Metrics

`benchmark/metrics.py` records counts and derives every rate from them.
Repetitions are pooled by adding their counts. A send is one run of a block;
a released block is one that passed its checks and its code.

| Metric | Definition |
| --- | --- |
| Bit error rate | Wrong bits / bits in released blocks (undefined if nothing was released) |
| Erasure rate | Bits in blocks never released / payload bits |
| Delivered | Correct released bits / payload bits |
| Delivered bits per state | Correct released bits / all prepared states, retries included |
| Raw bit error rate | Wrong symbol bits before correction / symbol bits measured, code bits included |
| Raw-symbol MI per state | Mutual information between sent and decoded symbols × symbols measured / prepared states |
| Rejection rate | Sends rejected by a check / all sends |
| Check failure rate | Failed checks / checks made |
| Uncorrectable | Sends that passed the checks but whose code found an error it could not correct |
