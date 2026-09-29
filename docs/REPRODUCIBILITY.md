# Reproduce Chapter 4

## 1. Choose the level of review

| Profile | What executes | Data needed | What a PASS means |
|---|---|---|---|
| `records` | Software/integrity tests, historical report inventory, 144 arithmetic checks, numerical plots, current supplement comparison, threshold crosswalk and fresh small Wasserstein fixture | Included files only; both pinned interpreters | Packaged arithmetic and software pass. No full raw-data reproduction. |
| `full` | All records stages plus canonical instruments, complete constructed benchmark, residential input audit and new fits, classifier/temporal/positive controls, raw telemetry/packet preparation, decoder cross-check and external fits | Shared residential Parquet, raw normal TON_IoT files, TShark | Only complete current stages and strict comparisons can produce full PASS. |

The full profile preserves all stages; do not use a successful records review to claim that missing raw-data runs completed.

## 2. Obtain the repository

Clone the published repository or extract the provided repository ZIP. The directory containing `README.md`, `run.py`, `master_workflow.py`, `config/` and `notebooks/` is the repository root. Do not place the whole extracted folder inside another identically named folder when publishing.

On Falcon, place this directory in Home. Use an allocated Jupyter/compute session with sufficient RAM. The exact allocation command depends on your Falcon access; this repository does not invent queue names or scheduler options.

## 3. Check the package

From the repository root, using any available Python 3.11/3.12:

```bash
python verify_package.py
```

Expect `passed: true` and no changed/missing files. This uses the standard library only and does not load a dataset. After deliberately editing tracked methods or references, regenerate a release manifest through `tools/build_manifest.py`, review the changes, commit them as a new version and validate again. Never refresh hashes just to hide an unexplained integrity failure.

## 4. Set up or reuse the interpreters

Follow `ENVIRONMENT.md`. The master can run in an existing Jupyter kernel; it launches each scientific stage with the configured interpreter. A matching residential environment does not also match the public versions.

For your existing Falcon setup, `~/venvs/tiot-v5/bin/python` was checked in the conversation and matched the residential package versions. Verify it again on the actual machine. The separate public environment may be `~/venvs/thesis-public/bin/python` after installation. Those are examples, not assumptions about a reviewer's machine.

## 5. Obtain and verify data

Follow `DATA.md`. A records-profile run does not open raw data. A full run requires the exact Parquet, the raw telemetry ZIP and all 15 captures. The public and private/generated model tables are not interchangeable. Reuse the Chapter 3 Parquet; do not upload it again.

## 6. Create a local configuration

Copy `config/example.json` to `config/local.json`. The latter is ignored by Git. For the author's existing Falcon interpreters you can instead copy `config/falcon-existing-environments.example.json`.

The configuration contains eight fields:

| Field | Meaning |
|---|---|
| `profile` | `records` or `full` |
| `public_python` | Full executable path for public/controlled stages |
| `residential_python` | Full executable path for residential/canonical supplementary stages |
| `residential_parquet` | Existing shared Parquet path |
| `toniot_data_root` | Directory containing the telemetry ZIP and `pcap_files/` |
| `run_root` | Persistent-for-the-run output directory, normally scratch on Falcon |
| `workers` | Operational worker count; default 4 |
| `budget_hours` | Per budget-aware fitting invocation; default 6 hours |

Use `/shared/scratch/SCWF00162/Beyond_the_Score_runs/records_01` for an initial records review and a distinct `.../full_01` for full execution. Do not put a space between `/` and `scratch`. Tilde paths are expanded; relative paths resolve from the repository root. Use forward slashes or escaped backslashes in Windows JSON. Linux is the demonstrated platform for package validation.

## 7. Preflight and bounded review

```bash
python preflight.py --config config/local.json
python run.py --config config/local.json
```

For the first review, set `profile` to `records` before the second command. Check `final_report/status.json`, then review `records/checks.csv`, `records/paper_headline_comparison.csv` and `supplementary_discrepancies/`. The final report will correctly say `new_full_raw_reproduction_complete: false` for this profile.

## 8. Full execution

Set `profile` to `full` and select a new `run_root`. Open `notebooks/Beyond_the_Score_Chapter4.ipynb` from inside the repository, restart the kernel and run all cells. Section 1 reads the JSON configuration. Keep the browser/kernel session alive according to Falcon's allocation rules.

Or run `python run.py --config config/local.json` in the allocated terminal. Do not start both entry points in the same output directory. A stage writes live logs under `logs/` and a current status under `master_status/`.

The recovered residential working matrix is about 4.81 GiB before copies and models. Plan at least 32 GiB for that stage and preferably 64–96 GiB for original canonical positive controls. These are planning estimates, not a measured peak-memory guarantee. Raw external captures occupy roughly 15 GB, and preparation/predictions need additional space. The constructed and full fitted workflows can take hours; do not extrapolate a records-profile runtime.

## 9. Resume and diagnose

Read `RECOVERY.md`. A time-budget pause is not a failed scientific result and is not a PASS. Rerun the paused notebook cell, or `python run.py --config config/local.json --stage residential` (use the actual stage name). Keep the same configuration and source files. External fitting can similarly resume with `--stage external` after its valid preparation stage. Operational time budgets do not limit every supplementary or constructed stage.

## 10. Verify and preserve

At completion, inspect the final report fields listed in README and each stage comparison. A `DIFFERENT` result is retained; do not loosen tolerances or change references. Expected source-health failures can coexist with a successful computational comparison.

```bash
python compare_runs.py --config config/local.json
python collect_run.py --config config/local.json --output /shared/scratch/SCWF00162/FALCON_RESULTS_TO_RETURN.zip
```

Save the executed notebook and full output directory as well. The compact collection excludes raw data and large arrays; it is not a complete checkpoint backup. Scratch is not an archival record: copy the required execution evidence and full checkpoints to your institution's permitted durable storage. Record the repository commit/tag alongside the final report.
