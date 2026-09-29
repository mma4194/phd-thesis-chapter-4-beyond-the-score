# Repository map

| Location | Purpose |
|---|---|
| `notebooks/` | Main Chapter 4 reproduction notebook |
| `config/` | Portable and Falcon configuration examples; local config is ignored |
| `environment/` | Exact direct scientific requirements and recorded Python 3.12 dependency locks |
| `src/`, `master_workflow.py`, `run.py` | Shared configuration and stage controller |
| `artifact/` | Stage execution, strict comparisons and evidence reporting |
| `controlled_source/`, `residential_source/`, `supplementary_source/` | Recovered scientific implementations |
| `external_rebuild/` | Recovered TON_IoT external-validation workflow |
| `protocols/`, `reference/`, `input_verification/` | Fixed experiment inputs and comparison targets |
| `design_inputs/` | Hash-indexed fixed-input inventory |
| `datasets/residential/` | Shared Chapter 3 release metadata; no duplicate Parquet |
| `provenance/` | Source lineage and supplementary source fingerprints |
| `validation/` | Dated historical and current package-validation evidence |
| `supplementary/` | Only `Beyond_the_Score_Supplement.pdf` |
| `docs/` | Reviewer, implementation, environment, recovery and publishing guides |
| `tools/`, `tests/`, `.github/workflows/` | Setup, collection, integrity and automated checks |
| `public/` | Third-party input notices |

The top-level layout follows the Chapter 3 repository. Scientific module directories retain their original names so imports and recovered code remain traceable.
