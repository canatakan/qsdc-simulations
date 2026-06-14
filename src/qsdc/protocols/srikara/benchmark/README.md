# Srikara Benchmark

This benchmark runs every JSON config in `configs/` and writes all outputs under
a local `results/` directory.

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
srikara-benchmark --config r_sweep
srikara-benchmark --config configs/r_sweep.json
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
srikara-benchmark --config r_sweep --skip-existing --keep-going
```

## Inputs

Configs live in:

```text
configs/
```

By default, the runner executes every `*.json` file in that directory, sorted by
filename. Use `--config` to run one or more selected configs. Each config's
`name` controls its output folder under `results/`.

Current case configs:

```text
alpha_high.json
alpha_low.json
large.json
r_fixed.json
r_sweep.json
theta_fixed.json
```

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
