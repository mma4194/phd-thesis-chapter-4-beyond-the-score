# Beyond the Score — Chapter 4 reproducibility

Reproducibility materials for **Beyond the Score: Validating Evaluations of Synthetic IoT Time Series**, Chapter 4 of Mohammed Alosaimi’s PhD thesis.

**Release 1.0.1 — 2 October 2026.** The completed Falcon raw-input run passed all eight stage reports, 252 checks in the five selected numerical comparison files, and all **45 registered headline values**. Residential and external saved-prediction verification passed. The independent packet-decoder receipt records a separate local execution. [Recorded results and scope](docs/RESULTS.md).

## Start here

1. Download or clone this repository. Keep its directory structure intact.
2. Read [data and environments](docs/REPRODUCIBILITY.md). Existing matching Falcon environments can be reused; no installation in scratch is required.
3. From the repository root, run `python verify_package.py` to verify package bytes.
4. Open **[Chapter4_Reported_Results.ipynb](Chapter4_Reported_Results.ipynb)** with the working directory set to this repository root.
5. For a short review, keep `MODE = "evidence"` and Run All. This checks the bundled completed run and recalculates headline arithmetic without new fits.
6. For fresh reproduction, set `MODE = "fresh"`, both interpreter paths, the raw-input locations and an output folder. Restart the kernel and Run All in an allocated compute session.
7. The final `CHAPTER_RESULTS_TO_RETURN.zip` contains your execution reports and comparisons. A numerical difference stops execution and remains visible.

For existing Falcon paths, the notebook defaults match the author’s working configuration. Other reviewers must set their own paths. The code and environments can stay in Home; scratch stores results. `budget_hours = None` disables the application deadline. Scheduler wall-time limits still apply.

## Documentation

| Guide | Contents |
|---|---|
| [Reproducibility](docs/REPRODUCIBILITY.md) | Environment setup, dataset layout, execution and local decoder command |
| [Implementation](docs/IMPLEMENTATION.md) | Stage order, scientific code and fixed inputs |
| [Results](docs/RESULTS.md) | Completed run, strict comparisons and measured timings |
| [Recovery](docs/RECOVERY.md) | Resume instructions and the permanent preparation fix |
| [GitHub Desktop](docs/GITHUB_DESKTOP_GUIDE.md) | Replace the earlier repository package and publish a stable release |
| [Release notes](CHANGELOG.md) | Version 1.0.1 changes and source provenance |

## Data and supplementary material

The residential Parquet is shared with [Chapter 3](https://github.com/mma4194/phd-thesis-chapter-3-synthetic-fusion/releases/tag/residential-input-v1); it is not uploaded twice. [Direct Parquet download](https://github.com/mma4194/phd-thesis-chapter-3-synthetic-fusion/releases/download/residential-input-v1/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet).

Obtain raw TON_IoT files separately from their provider. Neither raw TON_IoT nor Smart* data are included. Smart* is not used by this Chapter 4 workflow. Identity manifests, fixed task records, code, comparison tables and execution receipts are included.

The [supplementary folder](supplementary/) contains **only the corrected supplementary PDF**. Supporting code and reports are stored elsewhere.

## What PASS means

The scope is fixed by the chapter experiments in [CHAPTER_COVERAGE.csv](CHAPTER_COVERAGE.csv). It includes expected withheld, invalid-source and insufficient-resolution outcomes. Those are scientific outcomes, not failed reproduction checks. All selected comparison rows are retained; results are never filtered for agreement.

Fresh mode executes the declared raw-input stages, while recorded arithmetic and the fixed historical task registry retain their documented roles. The decoder receipt is a separately recorded local check. The later exploratory positive-control and solver investigations are outside this notebook; their discrepancies are not claimed to be resolved by this release.

Cite the thesis chapter and the repository release/commit used; see [CITATION.cff](CITATION.cff). Software and dataset rights are described in [NOTICE.md](NOTICE.md).
