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

  The payload can optionally be protected by a parity bit per symbol, as in
  Cao et al.'s Gaussian-mapping QSDC, or by extended Hamming SECDED (8,4,4)
  coding with a depth-3 interleaver. Failed blocks can be retried with an
  explicit bound.

  > Reference: S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).

## Commands

`make install` installs the package with two commands, `srikara-demo` and
`srikara-benchmark`, into `.venv/bin`. Use them after
`source .venv/bin/activate`, or call them as `.venv/bin/srikara-demo`.

```bash
make test
make srikara/test
```

### Demos

| Demo | What it shows | Command |
| --- | --- | --- |
| `basic` | The paper's algebra for one symbol, by hand, plus the effect of theta | `srikara-demo basic` |
| `message` | A text message through every protocol step, with per-mode noise traces on the Strawberry Fields backends | `srikara-demo message "hello"` |
| `noise` | The noise model, then a short message through a noisy channel, every mode through every stage | `srikara-demo noise` |
| `optimized` | A message with the fully optimized settings (parity, retries, r = 0.576): one line per block and a short look inside one block | `srikara-demo optimized "hello world"` |

`srikara-demo NAME --help` lists a demo's options. For example:

```bash
srikara-demo message "hello" --backend analytic
srikara-demo message "hello" --backend sf-sampled --random-source sf-bs-qrng --seed 30
srikara-demo message "hello" --optimized --noise medium --error-correction secded --max-attempts 3
srikara-demo noise "Hi" --error-correction parity --max-attempts 2
srikara-demo optimized "hello world" --noise high --example 3
```

### Benchmarks

```bash
srikara-benchmark list
srikara-benchmark run --study theta_fixed --workload light
srikara-benchmark rerender
```

`rerender` rebuilds every report's plots, `runs.csv`, `report.html` and the index
from its `results.json`, without simulating again, for example after a change
to the report layout.

## Srikara simulator

`SimulatorConfig` (`srikara/config.py`) holds every choice for one simulator; its
defaults are the noiseless paper setting.

```python
from qsdc.protocols.srikara.config import SimulatorConfig
from qsdc.protocols.srikara.simulator.protocol import SrikaraSimulator

config = SimulatorConfig(error_correction="secded", max_attempts=3)
transmission = SrikaraSimulator(config).transmit("101001110010")
assert transmission.recovered_bits == "101001110010"
```

The payload is split into blocks (`simulator/transport.py`), whose size
depends on `error_correction`:

- `none`: one symbol carrying 3 payload bits.
- `parity`: one symbol carrying 2 payload bits and an odd-parity bit, as in Cao
  et al. A parity bit detects an odd number of wrong bits but cannot locate
  them. With Gray-coded intervals the valid symbols are every second interval,
  so an error into a neighbouring interval is always detected.
- `secded`: 12 payload bits coded as three interleaved extended Hamming (8, 4)
  codewords, sent as 8 symbols. One wrong symbol is corrected.

Each block runs the protocol once with 4 states per symbol
(`simulator/protocol.py`). A run is accepted when all of its control and decoy
checks fall within `tolerance_sigmas`. A rejected block, or one whose code
detects an error it cannot correct, is sent again up to `max_attempts` times.
`recovered_bits` is only set when every block was recovered.

The squeezing angle matters: Alice displaces along the diagonal 1 + i, and
after Bob's unsqueezing the better quadrature carries it with gain
cosh r + √2 sinh r at θ = 5π/4 (or 7π/4) but only e^-r at θ = π/2. With the
aligned measurement below, the best angle is θ = 3π/2: the displacement is
stretched by e^r along the diagonal, and Bob reads √2·e^r per unit m_A.

`axis_policy` decides which quadrature Bob measures on a message mode:

- `random`: q or p at random, as in the paper.
- `best_qp`: whichever of q and p responds more to Alice's displacement.
- `aligned`: the quadrature along Alice's displacement after unsqueezing, which
  Bob can compute because he chose s. It reads the full displacement, about 15%
  more signal than `best_qp` at θ = 5π/4. This goes beyond the paper; it
  only needs Bob's local oscillator phase set per mode, like any homodyne
  basis choice.

Control and decoy checks always measure q or p at random.

Backends (`simulator/backends.py`):

- `analytic`: the paper's algebra, noiseless.
- `sf`: Strawberry Fields Gaussian circuits, read out as exact means.
- `sf-sampled`: the same circuits, read out as homodyne samples.

Both Strawberry Fields backends apply `SimulatorConfig.noise`: a thermal loss
channel in each direction, Alice's memory, and each party's detector efficiency
and electronic noise. Checks compare measurements against the expectation of
the noisy circuit, so honest noise is not mistaken for an eavesdropper.

## Benchmarks

A `Benchmark` is a name, a tuple of `Case`s and the names of its plotted axes:
no axes draws a comparison, one a sweep, two a heatmap. Each case is a
`SimulatorConfig`, a `Workload` (payload size, probability of a one, seed), a
series name, an optional label, and its coordinates `at` on those axes.

```python
from pathlib import Path

from qsdc.protocols.srikara.benchmark.benchmark import Benchmark, Case, Workload, run_benchmark
from qsdc.protocols.srikara.benchmark.catalog import OPTIMIZED
from qsdc.protocols.srikara.benchmark.report import write_report

benchmark = Benchmark(
    "one_probability",
    tuple(Case(OPTIMIZED, Workload(payload_bits=1024, one_probability=p), at=(p,)) for p in (0.1, 0.5, 0.9)),
    axes=("Probability of one",),
)
print(write_report(run_benchmark(benchmark), Path("results")) / "report.html")
```

`catalog.py` defines the presets (`WORKLOADS`, `NOISES`, the cumulative
`OPTIMIZATION_STEPS`) and 18 built-in studies: 3 reference studies per workload
and 15 studies of the optimized simulator per noise baseline, so a full run of
one workload writes 3 + 4 × 15 = 63 reports. `error_correction_comparison`
compares no coding, parity and SECDED, each with and without retries.

The optimized simulator measures along Alice's displacement (`aligned`), uses
Gray-coded Gaussian intervals with the same mean energy as the paper's
(`optimized_equal_energy`, about 18.6 SNU of variance), θ = 3π/2 and
r = 0.576, which is 5 dB of squeezing, the top of the paper's 1–5 dB range.
The optimization steps separate the two parts of the interval change: Gray
labels on the paper's intervals (`default_gray`) first, then the Gaussian
layout. Parity error detection and retries come last. The squeezing sweep goes up to
r = 1.5 (13 dB) as an idealized trend: the simulated squeezed states are pure,
without the anti-squeezing noise that limits real squeezers.

Run the studies with `srikara-benchmark` (in `.venv/bin`):

```bash
srikara-benchmark list
srikara-benchmark run --study optimization_comparison --noise low
srikara-benchmark run --workload light --repetitions 5
srikara-benchmark run --skip-existing
srikara-benchmark index
```

`run` defaults to every study, all four noise baselines, the `medium` workload
and one repetition. `--repetitions N` reruns every case with N independent
seeds (the first is the configured one), and rates pool all repetitions.
`--skip-existing` skips studies that already have a report,
so an interrupted run can be resumed. Reports go to
`results/<workload>/<reference|noise>/<study>/run_<time>/`:

- `report.html`: a results table with one row per case, plots, a table of sent
  vs. decoded symbols for each case, and the parameters shared by all cases.
  The summary cards show totals (cases × repetitions, prepared states,
  simulation time); delivery and information values appear there only for a
  single-case study, because the rates of different cases do not add up.
- `results.json`: every case's configuration, counts, rates and
  per-repetition counts.
- `runs.csv`: one row per case, with a column per configuration field, axis,
  metric and sent → decoded symbol pair.

`results/index.html` lists the latest execution of every study.

Measurements (`benchmark/metrics.py`) are counts; rates are derived from them.
A payload is split into blocks, and a block is sent again (a retry) when the
checks reject it or its code detects an error it cannot correct, while
attempts remain.

- Blocks, retries: blocks in the payload, and extra sends of failed blocks.
- Rejected by checks: sends whose control or decoy checks failed.
- Uncorrectable: sends that passed the checks, but where parity or SECDED
  detected an error it could not correct.
- Bit error rate: wrong bits / bits in released blocks (undefined when nothing
  was released).
- Raw bit error rate: wrong symbol bits before error correction, over all
  sends, rejected ones included; with parity or SECDED this counts the code
  bits too.
- Erasure rate: bits in blocks that were never released / payload bits.
- Delivered: correct bits in released blocks / payload bits, which equals
  (1 − erasure rate)(1 − bit error rate).
- Delivered bits per state: the same correct bits / all prepared states,
  retries included. Without error correction Bob cannot tell which bits are
  wrong, so compare coded and uncoded cases by information per state.
- Information per state: mutual information between sent and decoded symbols
  (before correction, all sends) / all prepared states, the rate an ideal code
  could reach on the channel. It is bounded by the entropy of the symbols
  sent, so it is below 3/4 for short or biased payloads, and at most 1/2 with
  parity, which only ever sends 4 of the 8 symbols.
- Rejection rate: sends rejected by the checks / all sends. It grows with the
  number of checks per send: 3 without error correction, 24 with SECDED.
- Check failure rate: failed checks / all control and decoy checks, which does
  not depend on the block size. On an honest channel it is the Gaussian tail
  probability of the tolerance, e.g. 0.27% at 3σ.

With several repetitions, rates are calculated from the counts of all
repetitions.
