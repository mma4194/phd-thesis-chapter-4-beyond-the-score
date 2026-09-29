# Immutable preparation verification

The master notebook fixes a false-failure mechanism: successful evaluation is allowed to update live workflow state, so that state is not an immutable preparation dependency.

## Receipt contents

`preparation_verified.json` records the preparation identity, its own content digest, and SHA-256 hashes of:

- the six prepared CSV tables;
- `prepared_files.json`, which binds immutable prepared metadata, audit tables, and `preparation_record.json`;
- copies of `input_identity_comparison.json`, `telemetry_member_comparison.json`, `capture_audit_comparison.csv`, `software_checks.json`, `prepared_table_comparison.json`, and `prepared_content_comparison.json` under `verified_input_checks/`.

The receipt is created only after input and prepared-content checks succeed. Existing receipts are verified, never refreshed to bless changed content. Required coverage is explicit, so an empty manifest cannot pass. Paths must remain within the preparation directory.

`latest_configuration.json`, `latest_status.json`, `artifact_workflow.json`, progress reports, evaluation outputs, and mutable status views are outside this receipt. Their later modification does not change the prepared input. `load_prepared()` reads the immutable preparation record when constructing an evaluation protocol, so successful evaluation cannot change the next evaluation's input identity.

The external stage checks the receipt before evaluation and again after comparison and prediction verification. Corrupt or missing tables, altered copied checks, changed manifests/receipts, and changed preparation identities fail. Old preparations that include mutable status in their manifest require explicit re-preparation with the current engine. The notebook does not delete their evidence or silently migrate expected hashes.

## Content versus byte equality

Original raw input identities and all 42 telemetry-member bytes remain strict. Prepared-table byte equality is reported independently. The existing portable content verifier permits only documented CSV formatting differences and one adjacent float64 value in packet-length standard deviations. Other fields, order, rows, missingness and zero standard deviations remain exact. The preparation fix does not broaden that rule and does not rewrite data.

## Regression coverage

`tests/test_preparation_integrity.py` tests:

- normal status/progress changes after freezing;
- the actual production `evaluate()` wrapper updating workflow state;
- changed prepared-table bytes;
- changed copied input checks;
- missing tables;
- a changed preparation identity;
- modified manifests and receipt coverage.

These are constructed software tests, not claims that the absent 15 raw capture files were processed again during packaging.
