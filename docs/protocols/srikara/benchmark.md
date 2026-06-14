# Srikara Benchmark

The Srikara benchmark runner executes every config in the benchmark package and
writes results beside those configs.

Run it from the benchmark directory:

```bash
cd src/qsdc/protocols/srikara/benchmark
srikara-benchmark
```

By default, the runner reads every `configs/*.json` file. Run one config with
`srikara-benchmark --config r_sweep`.

It writes:

```text
results/<config-name>/run_<unix_seconds>/
results/index.html
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

Use `--skip-existing` to leave configs with an existing
`results/<config-name>/run_*/benchmark.json` alone.

Operational details are maintained in
`src/qsdc/protocols/srikara/benchmark/README.md`.
