# Interruptions, budgets and safe recovery

Keep source, notebook and environments in home. Keep `run_root` on scratch. Never recreate an environment inside scratch on this Falcon setup.

1. Retain the same source checkout, input files, interpreter paths and configuration when resuming a budget-limited run.
2. Inspect `run_root/logs/<stage>.log` and `run_root/master_status/<stage>.json`.
3. Rerun the interrupted notebook cell, or `python run.py --config config/local.json --stage <stage>`. The stage's own checkpoint logic decides what can resume. Do not delete progress or falsify completed status.
4. If code, experiment configuration or dataset content changes, use a new run directory. Preserve the prior run for comparison. Do not bypass a source/configuration/input binding failure.
5. Preparation verification hashes immutable prepared tables and copied input-check reports. Evaluation may update progress files without invalidating those immutable products. If an immutable hash fails, regenerate preparation from the original inputs and investigate the changed file.
6. Generate the final report only after the required stages have completed. A completed report file alone is not evidence that all experiments passed.

Scratch can be purged. Copy the final reports, executed notebook, exact source snapshot, environment freezes and manifests to durable institutional storage. `collect_run.py` produces a compact review archive, not a complete backup of all predictions/prepared arrays. Back up those separately if you need to resume without recomputation. Exclude raw provider data from public GitHub uploads.

Moving a run directory changes the configuration binding. Keep an untouched original; use a new configuration/run root for a fresh validation instead of manually editing signed status records.
