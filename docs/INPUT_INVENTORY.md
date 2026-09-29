# Fixed inputs and manifests

The machine-readable index is [INPUT_LOCK.json](../design_inputs/INPUT_LOCK.json). It records the packaged protocol, reference and provenance files by SHA-256. The complete repository inventory is `MANIFEST.json`.

- `protocols/`: fixed experiment specifications, thresholds, feature groups, seeds, dataset schema, telemetry job definitions and printed supplementary targets.
- `reference/`: numerical reference tables used by strict comparisons. These are comparison inputs, not newly executed results.
- `provenance/`: recovered source lineage, recorded evidence and the latest supplementary source/PDF fingerprints.
- `input_verification/`: residential input/schema and fixed-input verification support.
- `external_rebuild/`: recovered external-validation preparation, telemetry, decoder and evaluation implementation.
- `validation/author_reference/`: supplied author execution records.
- `validation/recovery_20260927/`: earlier recovery validation records; read their dated scope rather than treating them as the latest Falcon run.

The residential Parquet is downloaded separately using `tools/residential_data.py`. Obtain raw TON_IoT inputs from their provider as explained in DATA.md. Neither raw dataset is included here. Smart* source data is not required by this chapter's workflow.

Prepared tables are generated outputs. Their immutable content hashes and copied input-check reports are verified before downstream execution; mutable progress/status files are deliberately excluded from the preparation content identity. See PREPARATION_VERIFICATION.md and PREPARED_CONTENT_VERIFICATION.md.
