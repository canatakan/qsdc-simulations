# Srikara Benchmark

The Srikara benchmark sweeps payload bit bias and squeezing-`r` distributions
over repeated protocol trials. Configs are strict JSON and live with the
benchmark package:

```text
src/qsdc/protocols/srikara/benchmark/configs/
  test.json
  sf.json
```

Run the analytic smoke config with:

```bash
srikara-benchmark src/qsdc/protocols/srikara/benchmark/configs/test.json
```

Each invocation writes a child `run_<unix_seconds>/` directory under the
configured `output_dir`. The generated run directory contains:

```text
benchmark.json
config.json
combos.json
trials.jsonl
benchmark.xlsx
plots/
```

The source modules that write those files are grouped under:

```text
src/qsdc/protocols/srikara/benchmark/artifacts/
  output.py
  plots.py
  workbook.py
```

The full config field reference is maintained in
`src/qsdc/protocols/srikara/benchmark/README.md`.
