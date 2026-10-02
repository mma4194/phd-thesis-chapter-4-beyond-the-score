# Implementation and experimental scope

## Execution flow

The root notebook orchestrates `chapter_support/reviewer.py`. Scientific stages execute in subprocesses using the public or residential interpreter, with numerical thread environment variables set to one. Four configured workers are separate from the numerical thread limit. Each stage records its environment, code binding, configuration and outputs. The controller checks completion and comparison status before admitting tables into the final report.

| Stage | Interpreter | Implementation and output |
|---|---|---|
| records | public | `artifact/recalculate.py`: recomputes archived primitive-record arithmetic; no model fits |
| canonical_metrics | residential | `artifact/supplementary.py`, retained canonical metric sources |
| input_verification | residential | Raw Parquet identity, chronology and missingness contracts |
| residential | residential | `artifact/residential.py`, `residential_source/`: qualification, calibration and 3,060 utility rows |
| controlled | public | `controlled_source/`: 18 constructed scenarios, four seeds, 72 cases and ablations |
| telemetry | public | `external_rebuild/telemetry_recovery.py`: 42 input member identities and timestamp recovery |
| prepare | public | `artifact/toniot.py`, `external_rebuild/project.py`: 15 captures and five-second prepared tables |
| external | public | `external_rebuild/evaluation.py`: primary and additional-origin experiments, 72 source jobs |

The notebook invokes these in the narrative order shown in its cells. Stage names are fixed; the controller does not select numerical rows by whether they agree.

## Methods and comparisons

`protocols/` holds the fixed task registry, split definitions, field contracts, seeds, expected environments and 45 printed headline targets. `reference/` retains historical numerical comparison records. `residential_source/`, `controlled_source/` and `supplementary_source/` retain recovered scientific definitions. `provenance/` and `SOURCE_ARCHIVES.json` retain lineage.

TRAIN-only choices, observed-target handling, matching plans, fitted models, seeds and original tolerances remain in the scientific source. The later stability solvers are not substituted. The headline comparison rounds to the publication’s registered precision; selected stage comparisons separately apply their original stricter rules. Inspect the comparison CSVs for per-quantity tolerances and keys.

`artifact/preparation_integrity.py` freezes immutable prepared tables and copied input-check reports. Thirteen immutable files are checked before and after external evaluation. Mutable progress files are excluded. Preparation must not be validated by hashing files that evaluation subsequently updates.

Saved-prediction receipts verify losses calculated from targets and predictions. The repository contains those verification records; the large prediction arrays remain in the original Falcon output and are generated again by fresh execution.

## Evidence layout

- `evidence/author_run/`: October 2026 Falcon reports and comparison tables, preserved from the supplied result archive.
- `evidence/index.json`: portable paths selecting the completed run plus input archive hashes.
- `evidence/local_decoder_receipt.json`: separately executed local decoder check.
- `results/falcon_20261002/`: final chapter report, 45-value comparison, archive audit and original HTML.
- `reference/`: historical scientific reference tables, distinct from new execution evidence.

Absolute author paths inside archived receipts are historical metadata. Evidence-mode lookup uses relative paths in the index. Keep the fixed historical registry dependency explicit: exploratory task discovery is not repeated.
