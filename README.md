# QSDC Simulations

Independent QSDC protocol simulators organized by protocol/paper reference.

Importable code lives under `src/qsdc`, reusable utilities live under
`src/qsdc/common`, protocol implementations live under
`src/qsdc/protocols/<protocol>`, demos live next to each protocol as `demo.py`, and paper
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

  The payload can optionally be protected by a parity bit per symbol, after
  the parity bit of Cao et al.'s Gaussian-mapping QSDC, or by extended Hamming SECDED (8,4,4)
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

### Demo

`srikara-demo` sends a text message, prints one line per send and every protocol
step of one block. `--simulator` picks a configuration from the benchmark catalog,
`--noise` a noise baseline, `--block` the block to show and `--trace` adds the noise
path of its modes. `srikara-demo --help` lists all options.

```bash
srikara-demo "hello"
srikara-demo "hello" --simulator baseline --noise clean
srikara-demo "hello" --noise metro_10km --block 3 --trace
```

### Benchmarks

```bash
srikara-benchmark list
srikara-benchmark run --study theta_fixed
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
- `parity`: one symbol carrying 2 payload bits and a parity bit. Cao et al. add an
  odd parity bit to each 3-bit box but do not map it onto the quadrature; here it
  is part of the symbol. Blocks alternate between odd and even parity, so the
  sent symbols cover all eight intervals equally and the mean of m stays zero,
  which Cao et al. require. A parity bit detects an odd number of wrong bits but cannot locate
  them. With Gray-coded intervals the valid symbols are every second interval,
  so an error into a neighbouring interval is always detected.
- `secded`: 12 payload bits coded as three interleaved extended Hamming (8, 4)
  codewords, sent as 8 symbols. One wrong symbol is corrected.

Each block runs the protocol once with 4 states per symbol
(`simulator/protocol.py`). As in the paper, a failed control check aborts the
run before Alice encodes anything, so an aborted run has no decoy checks and
no message measurements. A run is accepted when all of its control and decoy
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
from qsdc.protocols.srikara.benchmark.catalog import SIMULATORS
from qsdc.protocols.srikara.benchmark.report import write_report

benchmark = Benchmark(
    "one_probability",
    tuple(Case(SIMULATORS["optimized"], Workload(payload_bits=1024, one_probability=p), at=(p,)) for p in (0.1, 0.5, 0.9)),
    axes=("Probability of one",),
)
print(write_report(run_benchmark(benchmark), Path("results")) / "report.html")
```

Every case sends a random payload of 10,000 bits (`Workload`). The presets
and the studies are YAML files in `benchmark/catalog/`:

- `simulators.yaml`: named simulator configurations, each optionally extending
  another one (`baseline` is the paper's protocol, `optimized` the best one).
- `noises.yaml`: noise baselines, each with the source of its values.
- `studies.yaml`: the studies, each run under the noise baselines it lists
  (`lab` by default), which become the series of its report. A study lists its
  cases, or has one or two axes whose
  values make one case per point. Cases change fields by dotted path, such as
  `squeeze_r.value` or `noise.forward.transmittance`.

The noise baselines:

| Baseline | Fibre per direction | Excess noise | Detectors | Memory |
| --- | --- | --- | --- | --- |
| `clean` | none | 0 | ideal | ideal |
| `lab` | 1 km spool | 0.002 SNU | η = 0.95, 0.01 SNU | 0.95 |
| `metro_5km` | 5 km | 0.005 SNU | η = 0.85, 0.05 SNU | 0.9 |
| `metro_10km` | 10 km | 0.01 SNU | η = 0.8, 0.1 SNU | 0.9 |
| `record_27km` | 27.27 km, ultralow loss | 0.0015 SNU | η = 0.613, 0.122 SNU | 0.9 |

`record_27km` is the shortest point of Zhang et al., PRL 125, 010502 (2020).
Phase noise is not modelled yet.

There are 18 built-in studies, so a full run writes 18 reports.
Most run under `lab` only, because their conclusion does not depend on the noise
level. The comparisons where it does (`noise_profiles`, `optimization_comparison`,
`axis_comparison`, `interval_comparison`, `error_correction_comparison`) run
under every baseline, so each baseline is one color in the same report.
`error_correction_comparison`
compares no coding, parity and SECDED, each with and without retries.

The optimized simulator measures along Alice's displacement (`aligned`), uses
the paper's intervals with Gray labels (`gray`), θ drawn uniformly from 3π/2 ± π/4 and
r = 0.576, which is 5 dB of squeezing; the paper specifies neither.
The optimization steps add parity error detection and then retries.

`interval_comparison` compares the three interval codes: the paper's
(`default`), the paper's with Gray labels (`gray`), and Cao et al.'s Gaussian
intervals with Gray labels (`gaussian_gray`), with m drawn from the Gaussian
inside each interval. Cao et al. give the equiprobable intervals for
V_A = 8 SNU (their Table I); here they are scaled to the paper's mean energy of
64/3 ≈ 21.3 SNU, so the comparison shows only the effect of the layout. Cao's
quadratures also have a vacuum standard deviation of 1 and this simulator's
1/2, which halves their bounds.

The squeezing sweep goes up to r = 1.5 (13 dB) as an idealized trend: the simulated squeezed states are pure,
without the anti-squeezing noise that limits real squeezers.

Run the studies with `srikara-benchmark` (in `.venv/bin`):

```bash
srikara-benchmark list
srikara-benchmark run --study optimization_comparison
srikara-benchmark run --repetitions 3
srikara-benchmark run --skip-existing
srikara-benchmark index
```

`run` defaults to every study
and one repetition. `--repetitions N` reruns every case with N independent
seeds (the first is the configured one), and rates pool all repetitions.
`--skip-existing` skips studies that already have a report,
so an interrupted run can be resumed. Reports go to
`results/<study>/run_<time>/`:

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
- Rejected by checks: sends whose control or decoy checks failed. A failed
  control check aborts the send before anything returns to Bob.
- Uncorrectable: sends that passed the checks, but where parity or SECDED
  detected an error it could not correct.
- Bit error rate: wrong bits / bits in released blocks (undefined when nothing
  was released).
- Raw bit error rate: wrong symbol bits before error correction, over every
  symbol Bob measured (sends rejected by the decoy check included, aborted ones
  have none); with parity or SECDED this counts the code bits too.
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
  number of checks per send: up to 3 without error correction, 24 with SECDED.
- Check failure rate: failed checks / control and decoy checks made, which does
  not depend on the block size. On an honest channel it is the Gaussian tail
  probability of the tolerance, e.g. 0.27% at 3σ.

With several repetitions, rates are calculated from the counts of all
repetitions.
