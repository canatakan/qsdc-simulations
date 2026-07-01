# Srikara Benchmark

This benchmark runs every JSON config under `configs/` and writes all outputs
under a local `results/` directory.

## Run

From this directory:

```bash
srikara-benchmark
```

Equivalent explicit form:

```bash
srikara-benchmark --config-dir configs --output-root results
```

Run one config by name or path:

```bash
srikara-benchmark --config r_fixed
srikara-benchmark --config base/r_fixed
srikara-benchmark --config configs/base/r_fixed.json
srikara-benchmark --config base
```

Resume without rerunning configs that already have completed output:

```bash
srikara-benchmark --skip-existing
```

Keep going after a failed config:

```bash
srikara-benchmark --keep-going
```

These flags can be combined:

```bash
srikara-benchmark --config r_uniform_sweep --skip-existing --keep-going
```

## Inputs

Configs live in:

```text
configs/
  base/
  axis_policy/
```

By default, the runner executes every `*.json` file under that directory,
including grouped subdirectories, sorted by path. Use `--config` to run one or
more selected config files, grouped directories, or unambiguous config names.
Each config's `name` controls its output folder under `results/`.

Current base configs:

```text
base/alpha_high.json
base/alpha_low.json
base/large.json
base/r_fixed.json
base/r_uniform_sweep.json
base/theta_fixed.json
base/theta_uniform.json
```

All base configs use the same `base_seed` so comparable cases share derived
message and simulation seeds. `r_fixed.json` sweeps the fixed squeezing values
from \(-0.5\) dB through \(-20\) dB. `r_uniform_sweep.json` uses interval bands
around the main squeezing checkpoints, including a wide \(-0.5\) dB to
\(-10\) dB band. Non-r-focused base configs use the fixed \(-1\), \(-3\),
\(-5\), and \(-10\) dB checkpoints.

Current axis-policy configs:

```text
axis_policy/alpha_high.json
axis_policy/alpha_low.json
axis_policy/large.json
axis_policy/r_fixed.json
axis_policy/r_uniform_sweep.json
axis_policy/theta_fixed.json
axis_policy/theta_uniform.json
```

The axis-policy configs mirror the base configs with `message_axis_policy` set
to `optimized` and `check_axis_policy` set to `optimized`.

## Outputs

Each config writes one timestamped run directory:

```text
results/<config-name>/run_<unix_seconds>/
```

Each run directory contains:

```text
benchmark.json
combos.csv
trials.csv
report.html
report.css
plots/
```

`benchmark.json` is the run summary and metadata.

`combos.csv` contains one aggregate row per parameter combo.

`trials.csv` contains one row per protocol trial.

`report.html` is the main per-run report to open.

`plots/` contains:

```text
bit_error_by_r.png
symbol_error_by_r.png
value_error_by_r.png
derived_acceptance_tolerance_sigmas_curve.png
```

After all selected configs finish, the runner also writes a comparison UI:

```text
results/index.html
results/index.css
```

`--skip-existing` treats a config as complete when this pattern exists:

```text
results/<config-name>/run_*/benchmark.json
```

## Config Shape

Configs are strict JSON. Important fields are:

- `name`: case name and output folder name
- `backend`: `analytic`, `sf`, or `sf-sampled`
- `random_source`: `classical` or `sf-bs-qrng`
- `payload_bit_count`: payload bits per trial before padding
- `trials_per_combo`: repeated trials per parameter combo
- `base_seed`: root seed for derived message/simulation seeds
- `tolerance_sigmas`: control/decoy threshold in measurement-noise sigmas
- `check_axis_policy`: control/decoy measurement axis policy, `random` by
  default or `optimized` to choose the larger absolute coherent
  displacement component
- `message_axis_policy`: message decoding axis policy, `random` by default or
  `optimized` to choose the larger absolute response factor known to Bob
- `one_probabilities`: message bit-bias sweep
- `r_distributions`: squeezing-`r` sweep
- `alpha_distribution`: Bob alpha sampling
- `theta_distribution`: squeeze angle sampling

The benchmark expands combos as:

```text
one_probability x r_distribution
```

Generated benchmark outputs are runtime artifacts and should stay under
`results/`.
