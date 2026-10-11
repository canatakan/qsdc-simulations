# QSDC Simulations

Independent QSDC protocol simulators organized by protocol/paper reference.

Importable code lives under `src/qsdc`. Protocol implementations live under
`src/qsdc/protocols/<protocol>`, each with its `config.py`, its fixed values
and unit conventions in `constants.py`, its simulator and a `demo.py`. Code
shared by the protocols lives under `src/qsdc/common`:

- `config/`: the configuration base classes, parameter distributions, and the
  noise models and baselines.
- `coding/`: bit conversion, interval codes, parity and SECDED.
- `quadrature.py`, `random.py`, `transmission.py` (blocks and retries) and
  `utils.py` (the demos' console tables).

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

- `cao`: CV QSDC based on Gaussian mapping with two-mode squeezed states, with an
  analytic backend that applies the shared noise baselines.

  > Reference: Z. Cao, L. Wang, K. Liang, G. Chai, and J. Peng, Continuous-variable quantum secure direct communication based on Gaussian mapping, Phys. Rev. Appl. 16, 024012 (2021).

## Commands

`make install` installs the package with three commands, `srikara-demo`,
`srikara-benchmark` and `cao-demo`, into `.venv/bin`. Use them after
`source .venv/bin/activate`, or call them as `.venv/bin/srikara-demo`.

```bash
make test
make srikara/test
make cao/test
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

`cao-demo` does the same for the Cao simulator. `--noise` picks a noise
baseline (default `clean`), and the other options set the seed, the squeezing,
the check pairs and the sends per block.

```bash
cao-demo "hello"
cao-demo "hello" --max-attempts 3 --block 2
cao-demo "hello" --noise metro_10km --max-attempts 3
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

## Noise baselines

Both simulators use the noise baselines of `src/qsdc/common/config/noises.yaml`, each
with the source of its values. A baseline describes one fibre pass, one memory
or optical delay, and one homodyne detector; each protocol places them on its
own links.

| Baseline | Fibre per pass | Excess noise | Detectors | Memory |
| --- | --- | --- | --- | --- |
| `clean` | none | 0 | ideal | ideal |
| `lab` | 1 km spool | 0.002 SNU | η = 0.95, 0.01 SNU | 0.95 |
| `metro_5km` | 5 km | 0.005 SNU | η = 0.85, 0.05 SNU | 0.9 |
| `metro_10km` | 10 km | 0.01 SNU | η = 0.8, 0.1 SNU | 0.9 |
| `record_27km` | 27.27 km, ultralow loss | 0.0015 SNU | η = 0.613, 0.122 SNU | 0.9 |

`record_27km` is the shortest point of Zhang et al., PRL 125, 010502 (2020).
Phase noise is not modelled yet.

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

## Cao simulator

`SimulatorConfig` (`cao/config.py`) holds the settings; its defaults follow the
worked example of the paper (Fig. 3, Table I). Quadratures are in shot-noise
units with a vacuum variance of 1, as in the paper.

```python
from qsdc.protocols.cao.config import SimulatorConfig
from qsdc.protocols.cao.simulator.protocol import CaoSimulator

transmission = CaoSimulator(SimulatorConfig(max_attempts=3)).transmit("1010")
```

The payload is uniformized (0 → 01/10, 1 → 00/11, alternately) and split
into blocks of `block_bits` message bits. Each block is sent on its own EPR
pairs, `2 * check_pairs + boxes` of them (`simulator/protocol.py`):

1. Two squeezed vacua on a 50:50 beam splitter give the pair S1 (Alice) and
   S2 (Bob), Eqs. 1–4.
2. Channel detection: on `check_pairs` positions chosen by Alice, both
   heterodyne-measure x and p. A position passes when
   X_m² + P_m² < 2 with X_m = (x_A − x_B)/√2 and P_m = (p_A + p_B)/√2
   (Eq. 5). On heterodyne outcomes, this is Duan's inseparability criterion.
   The block is terminated unless the failure rate is below
   `check_failure_threshold`.
3. Authentication: the same test on positions chosen by Bob.
4. Gaussian mapping (`simulator/mapping.py`): every uniformized bit becomes
   a random code word (0 → 00/01, 1 → 10/11), the result is split into
   `boxes` boxes, and `detection_bits` random bits are inserted into each box
   at random positions. The box selects one of the equiprobable intervals of
   N(0, V_A), and G1' is drawn from the Gaussian inside it. The odd parity bit
   of the box is not mapped, as in the paper, but announced over the
   classical channel together with the detection bits.
5. Alice displaces X of S1 by G1' and P by an independent Gaussian G2.
6. Bob measures the arriving beam jointly with his S2:
   X_m = (X_info − X_2)/√2, P_m = (P_info + P_2)/√2 (Eq. 6).
7. Alice reveals G2. Bob fits P_m = t G2 to estimate his gain t, which is
   √(ηT/2) with fibre transmittance T and detector efficiency η, decodes
   X_m / t into an interval, and checks the detection and parity bits. The block is released when every box passes, and its
   two uniformizations are inverted.

A terminated block, or one with a detected error, is sent again up to
`max_attempts` times.

Default choices where the paper gives no value:

- `squeeze_r` = arcosh(9)/2 ≈ 1.444 (12.5 dB), so that the two-mode squeezed
  state has the variance V = V_A + 1 of the paper's security model.
- `check_pairs` = 4 per stage, as many as boxes.
- `check_failure_threshold` = 1/e, the failure rate of uncorrelated light: a
  position of a pure EPR pair fails with probability exp(−2/(1 + e^(−2r))),
  15% at the default squeezing, and of two vacua with exp(−1).

The modulation is taken literally: Alice displaces by G1' itself, so Bob reads
G1'/√2 on top of the squeezed noise e^(−r) of the pair. On the clean channel
about a fifth of the boxes are decoded into a wrong interval at the default
squeezing. The paper removes these errors by reverse reconciliation, which is
not simulated; here only the detection and parity bits detect them.

`AnalyticBackend` (`simulator/backends.py`) samples the vacuum quadratures and
applies the paper's linear transformations, which gives the exact statistics
of these Gaussian states and measurements. `SimulatorConfig.noise` places a
noise baseline on the links of Fig. 1:

- S1 waits in Alice's delay line OD1 while S2 travels to Bob and the checks
  run; Alice then displaces it and sends it through the fibre.
- S2 travels through the same fibre and waits in Bob's delay line OD2 until
  S_info arrives.
- Each party heterodynes with its detector, and Bob's joint measurement uses
  two of his homodyne detectors.

Loss is a thermal loss channel, and a detector adds its loss and electronic
noise to each measured quadrature. Since both beams pass the fibre and one
delay line each, the EPR noise still cancels in Bob's joint measurement, but
every loss replaces part of it with unsqueezed vacuum noise. Even the 1 km of
the `lab` baseline therefore nearly doubles the wrong boxes, and the checks
reject honest pairs more often with distance, because Eq. 5 compares Alice's
and Bob's outcomes without compensating Bob's loss. The tests check the
variances against Strawberry Fields. Strawberry Fields backends, SECDED and
benchmarks are not implemented yet.

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
- `studies.yaml`: the studies, each run under the noise baselines it lists
  (`lab` by default), which become the series of its report. A study lists its
  cases, or has one or two axes whose
  values make one case per point. Cases change fields by dotted path, such as
  `squeeze_r.value` or `noise.forward.transmittance`.

The noise baselines are the shared ones of the section above, with the fibre
used in both directions and the same detector at Alice and Bob.

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
V_A = 8 SNU (their Table I); here the equiprobable intervals are computed for
the paper's mean energy of 64/3 ≈ 21.3 SNU instead, so the comparison shows only
the effect of the layout. Cao's quadratures also have a vacuum standard
deviation of 1 and this simulator's 1/2, which halves their bounds.

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
