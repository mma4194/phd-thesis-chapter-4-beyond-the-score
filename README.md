# Beyond the Score
### Chapter 4 · PhD examination and viva

**Beyond the Score: Validating Evaluations of Synthetic IoT Time Series** examines when metric responses, qualified prediction tasks and source checks support an evaluation of synthetic data. This repository supports examination and reproduction of Chapter 4 of Mohammed Alosaimi's PhD thesis.

**Start here:** [Reproduce the chapter](docs/REPRODUCIBILITY.md) · [Required data](docs/DATA.md) · [Understand the results](docs/RESULTS.md) · [Supplementary PDF](supplementary/Beyond_the_Score_Supplement.pdf)

## Study workflow

The workflow validates instruments on constructed data, qualifies residential tasks using matched real controls, compares synthetic sources with real-trained references, and rebuilds the external TON_IoT evaluation from raw normal telemetry and captures. It preserves training-only decisions, observation masks, equal training budgets, conditional uncertainty estimates and expected source failures.

The [master notebook](notebooks/Beyond_the_Score_Chapter4.ipynb) is the guided entry point. The terminal runner uses the same stage controller. Both read one local configuration file and invoke separately pinned scientific environments.

| Component | Included material and execution evidence |
|---|---|
| Scientific code, task cards, split/mask manifests, settings and numerical references | Included and indexed in [input inventory](docs/INPUT_INVENTORY.md) |
| Residential prepared Parquet | [Download shared Chapter 3 input](https://github.com/mma4194/phd-thesis-chapter-3-synthetic-fusion/releases/download/residential-input-v1/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet); 238,609,923 bytes. No duplicate dataset upload. |
| Raw TON_IoT files | Obtain from the provider: 42 telemetry members and 15 normal captures. Not redistributed. |
| Earlier completed author runs | Supplied reports: full controlled comparison PASS, residential 90 source jobs/3,060 rows, external 72 source jobs/87 checks and 8,508 prediction-loss checks. |
| Recovery validation | 144 record checks, 45 headline values and 21 software tests passed; exact input, telemetry and selected fresh experiments checked. Full/partial execution is labelled. |
| Full reproduction workflow | Execute the master notebook and inspect the generated stage reports, strict comparisons and prediction checks. |

The current thesis supplement correctly separates the median populations and uses the newer controlled Table S14 endpoints. Original canonical results remain intact as a separate historical experiment. See [supplement comparison](docs/SUPPLEMENT_COMPARISON.md).

## Run the study

These are CPU-based methods. The GPU requirements of Chapter 3 do not apply. Use Python 3.11 or 3.12 with the required scientific versions. Follow [environment setup](docs/ENVIRONMENT.md) before installing or selecting interpreters. The two environments intentionally contain different versions.

1. Obtain the residential input and raw TON_IoT files using [the data guide](docs/DATA.md).
2. Copy `config/example.json` to `config/local.json`. Set existing public/residential interpreter paths, both input locations and an output folder.
3. From the repository root:

```bash
python verify_package.py
python preflight.py --config config/local.json
```

4. Open [Beyond_the_Score_Chapter4.ipynb](notebooks/Beyond_the_Score_Chapter4.ipynb), select a working Jupyter kernel, restart it and run all cells. The master kernel coordinates separate scientific processes.

Alternatively, execute the same stages from a terminal:

```bash
python run.py --config config/local.json
```

Run one entry point at a time. On Falcon keep the repository and environments in Home and put `run_root` on scratch, inside an allocated compute session. Use `profile: "records"` for a short first review and a separate output directory for `profile: "full"`.

## Check the outcome

Read `final_report/status.json` in the configured output directory. A complete new reproduction requires:

```json
{
  "profile": "full",
  "selected_workflows_complete": true,
  "selected_workflow_checks_passed": true,
  "new_full_raw_reproduction_complete": true,
  "strict_manuscript_agreement": true
}
```

Inspect `final_report/workflow_comparison.csv`, stage-specific comparison tables and saved-prediction verification. Successful execution alone is not numerical agreement. Historical reports never satisfy unfinished new stages. A records-profile PASS is not a full experiment PASS.

## Documentation

| Guide | Purpose |
|---|---|
| [Reproduction walkthrough](docs/REPRODUCIBILITY.md) | Clean checkout through final comparisons |
| [Environment](docs/ENVIRONMENT.md) | Reuse matching Falcon interpreters, create only missing environments |
| [Datasets](docs/DATA.md) | Exact files, shared Parquet, checksums and folder layout |
| [Included input inventory](docs/INPUT_INVENTORY.md) | Every supplied fixed input and its role |
| [Implementation](docs/IMPLEMENTATION.md) | Stage order, code locations, preserved methods and guards |
| [Results](docs/RESULTS.md) | Expected outputs, strict comparison rules and scope |
| [Recovery](docs/RECOVERY.md) | Resume safely after a time-budget pause or interruption |
| [Repository map](docs/FILE_MAP.md) | Layout matching the Chapter 3 documentation pattern |
| [Collect run outputs](docs/FALCON_FILES_TO_SEND.md) | Archive the executed notebook, environment details and comparison reports |
| [GitHub Desktop publication](docs/GITHUB_DESKTOP_GUIDE.md) | Create, check, publish and freeze an examination release |

## Scientific scope

The residential starting point is the shared prepared Parquet. Fixed historical candidate cards and exploratory task-selection records are research inputs; the package does not claim to rediscover the original full candidate search. The constructed cases are development cases, not an independent population of deployments. Canonical exploratory positive controls retain their original task/licence scope.

The external workflow reconstructs the reported five-second normal-data preparation. It does not establish independent physical clock synchronization or restore an unavailable earlier dataset byte for byte. The preparation receipt binds immutable tables and copied input checks, so later evaluation progress cannot invalidate it.

## Third-party inputs

Raw TON_IoT data are obtained from their provider under the applicable terms. Smart* is used in Chapter 3 and is **not** an input to this Chapter 4 pipeline. Neither raw dataset is included. Attribution and distribution boundaries are in [third-party notices](public/THIRD_PARTY_NOTICES.md). No dataset licence is invented for the linked residential asset.
