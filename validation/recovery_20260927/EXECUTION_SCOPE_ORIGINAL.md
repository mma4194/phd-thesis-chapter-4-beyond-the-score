# Execution status for this recovery

**The complete notebook and supporting workflows are assembled and validated as a package. A new full raw-data reproduction has not been completed here.** The master report keeps that distinction machine-readable. Historical reports are under `previously_verified/`; newly executed evidence is under `validation_current/`.

## Newly executed during this recovery

| Component | Observed result | What it establishes |
|---|---|---|
| Master notebook, records profile | All **23 code cells** ran in order without errors; 45 total cells | End-to-end configuration, child interpreters, tests, arithmetic, figures, discrepancy reports and compact result export. Full-profile cells explicitly print that they were not executed. |
| Scientific software checks | **21 test methods passed** | Includes eight new preparation-integrity regressions, two temporal-loader tests and original scientific/decoder/content checks. |
| Saved-record arithmetic | **144 checks passed**, including **45 printed headline values** | Newly recalculated statistics, decisions and intervals from primitive records; no new raw-data fitting in this stage. |
| Original residential Parquet | **2,641 checks passed**, zero failures | Exact 238,609,923-byte input, 1,277,694 rows, 740 stored columns, 439 masks, 1,992 diagnostic rows and 136 windows. Working scope has 1,010 columns; it differs from the original supplementary canonical scope. |
| Raw TON_IoT telemetry | **42 member hashes matched**, **21 paired logs processed**, **28,200 fridge dates repaired** | Fresh original/filtered correspondence, documented date recovery and five-second aggregation. This does not include packet preparation. |
| Original threshold crosswalk | **3 checks passed** | No changed raw/applied licence states, equal training budgets and no TEST-based selection. Original canonical decisions are kept separate from corrected residential decisions. |
| Sparse-feature Wasserstein and 27 classifier rows | **9 checks passed** | Fresh feature-level Wasserstein calculations; classifier operating rows reconstructed from original seed metrics. |
| Canonical instrument curves, residential environment | **45 seed/perturbation/severity rows and 29 quantities matched** | Fresh fixture generation and instrument/classifier fitting reproduced the original canonical snapshot, including Table S14. |
| Controlled instruments, public environment | **11 instrument records**, plus **45 seed-curve rows and 29 quantities matched** | Fresh fitting reproduced the newer controlled-reference snapshot. The three printed Table S14 differences remain visible. |
| Classifier sample-size sensitivity, public environment | **12 rows and 13 quantities matched** | The recovered diagnostic reproduces in the public environment with original settings and tolerances. |
| Same classifier diagnostic, residential environment | **DIFFERENT**, retained as a diagnostic | Maximum RF-AUC deviation approximately 0.001615, null-p95 deviation approximately 0.0049. Routing to the reproducing public environment resolved the active stage; no reference or tolerance changed. This does not isolate one dependency as the cause. |
| Residential temporal controls | **20 condition/seed rows and six quantities matched** | Fresh calculation from the exact original 70,000-row TEST segment with 300-row blocks. |
| Full constructed benchmark attempt | **800 P0 jobs**, **69 scenario jobs**, **13/72 completed aggregates** | All 13 completed aggregates match their fixed reference under the original six-value comparison. The optional long validation run was stopped; **INCOMPLETE**, never a full PASS. Completed checkpoints were preserved separately. |
| Positive-control source loading | Canonical definitions and historical cards loaded successfully | Import/dependency validation only. Full role-matched positive-control fitting and diagnostics require a larger-memory run. |
| Preparation verification fix | Production evaluation-wrapper regression passed | Mutable status/progress updates preserve verification. Modified tables, copied reports, manifests, receipts, identities, or missing tables are rejected. No fresh 15-capture preparation is claimed. |

The original temporal-control loader exceeded this workspace's approximately 9.7 GiB memory limit. The final wrapper reads only the exact original TEST window column by column. Float32 conversion precedes non-finite replacement, as in the canonical loader. Unit equivalence and all 20 original output rows pass. This was a resource-loading repair, not a change to the experimental sample.

Native Jupyter kernel startup returned `Operation not permitted` while initializing local networking. Every notebook code cell was instead executed in sequence in a fresh IPython process, using the same master controller and pinned scientific subprocesses. This validates notebook code and stage integration; it is not claimed as native Jupyter transport validation. The original startup log is retained.

## Previously verified results supplied by the author

| Historical workflow | Supplied result |
|---|---|
| Full controlled benchmark | PASS: all nine comparison checks, 11 instruments, 72 scenario records and 576 ablation rows. |
| Corrected residential evaluation | PASS: 90 source jobs, 3,060 utility rows, P0 refitted, and 16,291 saved score-array losses checked. |
| Reconstructed external evaluation | PASS: 72 source jobs, 87 comparison checks and 8,508 prediction-loss checks. |
| Record recalculation | PASS: 144 checks including 45 headlines. |

These original reports are preserved unchanged. The compact author archive did not contain the large original prediction arrays. Reading a PASS report does not revalidate their absent bytes.

## Remaining execution boundaries

A new full run still requires all 15 raw normal PCAP/PCAPNG captures, a working TShark installation, sufficient memory for full residential and canonical positive controls, and time to complete every required stage. The current source does not silently replace an unfinished new stage with an old result. The missing captures were not found in the supplied archives or accessible saved files; the recovered raw telemetry ZIP cannot replace them.

All comparison tolerances and expected scientific failures are preserved. The two supplementary issues are fully documented in `DISCREPANCIES.md` and `validation_current/fresh_table_s14_comparison.csv`. Strict manuscript agreement remains false until the wording/reference-snapshot choice is addressed explicitly.

The immutable release code differs from early packaging bindings where wrappers and documentation were still being assembled. Each newly executed experiment retains its actual source/environment binding. Scientific functions used for the completed checks were not replaced with expected outputs. The final master records-profile run uses the delivered active source.
