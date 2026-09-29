# Implementation

## Entry points and configuration

`notebooks/Beyond_the_Score_Chapter4.ipynb` and `run.py` call the same `master_workflow.Workflow`. `src/configuration.py` expands local paths, validates the operational configuration and keeps raw inputs separate from the output root. `artifact/stages.py` executes each stage in the interpreter selected by the controller. Numerical settings remain in the frozen scientific protocols, not optional notebook controls.

| Stage | Engine | Interpreter | Main evidence |
|---|---|---|---|
| preflight | `artifact/preflight.py`, `tests/` | Public | Integrity and software contracts |
| history | `artifact/stages.py` | Public | Supplied author reports, explicitly historical |
| records | `artifact/recalculate.py`, `record_methods.py`, `plots.py` | Public | Primitive losses to decisions, intervals, figures and 45 headlines |
| supplementary_audit | `artifact/supplementary_audit.py` | Public | Latest supplement targets and historical snapshot differences |
| thresholds, fixture_audit | `artifact/supplementary.py` | Residential | Original threshold ledger, fresh Wasserstein fixtures, recorded classifier arithmetic |
| canonical_metrics | Same, original canonical definitions | Residential | Original instrument seed curves |
| controlled | `artifact/controlled.py`, `controlled_source/` | Public | Full fixed constructed benchmark, P0, 72 cases, 576 ablations |
| input_verification | `input_verification/verify_residential_input.py` | Residential | Exact Parquet, missingness, chronology and 136 task windows |
| residential | `artifact/residential.py`, `residential_source/` | Residential | Fresh admission, matching, P0, 90 sources/jobs and new prediction checks |
| classifier_capacity | Recovered supplementary classifier diagnostic | Public | Twelve sample-size rows; this reproducing environment was checked |
| temporal_controls | Exact TEST-window loader and original temporal functions | Residential | Twenty condition/seed rows |
| positive_controls, positive_diagnostics | Repaired canonical v4.1 and v4.2 source cells | Residential | Role-matched controls and anchor-relative diagnostics |
| telemetry, prepare | `external_rebuild/`, `artifact/toniot.py` | Public | Raw member identities, packet parsing, time grid, masks and six tables |
| decoder | `external_rebuild/crosscheck.py` | Public + TShark | First 10,000 complete packets in each of 15 captures |
| external | `external_rebuild/evaluation.py`, recovered modules | Public | Four origins, 72 source jobs, 87 comparisons and 8,508 loss checks |
| report | `artifact/stages.py` | Public | Current configuration/source-bound stage statuses and compact export |

## Preserved scientific rules

The repository retains source-specific chronological splits, embargoes, seeds, task/model cards, train-only fitting and imputation, observation masks, join exclusions, equal training counts, source-health checks, group splits for classifiers, bootstrap seeds and aggregation order. The residential family/capability hierarchy intentionally differs from the external hierarchy. Expected failed source-health outcomes remain scientific outcomes; they are not replaced with successful values.

The original 640-card discovery ledger, 199 retained task/model configurations and selected P0 cards are fixed historical inputs. The corrected pipeline repeats admission on that declared set and does not restart exploratory discovery. The 25 same-time plus nine temporal scored configurations are retained, while the primary supported scope uses the three qualified same-time groups. Supplementary canonical controls retain their earlier licence scope and do not replace corrected primary findings.

`residential_source/support.py` preserves field-definition review and full prepared-input range checks for the five affected methods, including separation of out-of-range and unseen-in-range values. Full-support binary detection inspects the supplied values rather than a prefix. Its generated per-source health reports should be included when collecting the latest full Falcon run.

## Preparation completion fix

`artifact/preparation_integrity.py` hashes six immutable prepared tables, `prepared_files.json` and copies of six input-check reports under `verified_input_checks/`. The immutable `preparation_record.json` is covered by the prepared manifest. Mutable progress, current pointers and evaluation-status views are excluded. The receipt is checked before fitting and after evaluation; an existing changed receipt is not reblessed by recalculating its expected hash.

Raw file identity, parsed prepared content and fitted-result agreement are separate checks. The original portable rule permits at most the documented one-ULP difference for packet-length standard deviations; it does not loosen model-result comparison tolerances.

## Repository-only adaptations

The notebook now reads `config/local.json`, the environment setup separates Python-version-specific locks, and documentation follows the Chapter 3 layout. Scientific engine directories remain in their established locations to avoid changing import or file-resolution contracts just for cosmetic uniformity. Current printed supplement targets were updated from the supplied latest Overleaf source, while historical targets and fitted references remain separately preserved.

The temporal-only wrapper reads the same first 70,000 TEST rows column by column, preserving original column order, float32 conversion and nonfinite replacement. It avoids allocating the full canonical matrix solely for this diagnostic; original output comparisons and equivalence tests passed.

## What is not reconstructed from raw data

Upstream residential acquisition/Parquet assembly, original full exploratory task discovery, independent sensor calibration and independently established physical clock alignment are outside this pipeline. No claim is made that historical compact reports contain absent raw prediction arrays. These boundaries are explicit research inputs and evidence limits, not hidden substitutes for fresh computation.
