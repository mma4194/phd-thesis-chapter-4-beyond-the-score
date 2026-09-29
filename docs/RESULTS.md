# Results and evidence boundaries

Three kinds of evidence must remain separate:

1. **Supplied author reference results:** historical runs recovered from the supplied archives. The supplement reports 144 checks / 45 headline checks, a full controlled-experiment PASS, 72 telemetry jobs / 87 checks / 8,508 loss rows, and 90 residential jobs / 3,060 metric rows / 132 quality rows / 16,291 prediction rows. These are historical counts, not a claim that this repository build reran those experiments.
2. **Recovery and repository validation:** dated reports in `validation/`. Record rechecks, unit tests and notebook execution in the `records` profile do not retrain the full experiment. See EXECUTION_STATUS.md for this build's actual checks.
3. **Your new full run:** outputs in the configured `run_root`. The final report must show completed required stages and strict comparison outcomes. A budget pause, missing stage or merely green GitHub Actions job is not a full reproduction PASS.

## Supplementary corrections

The latest supplied Overleaf supplement resolves the previously identified wording/value discrepancies. The reported 0.269 is the mean of within-seed medians over **all nine features**; it is not the median restricted to positive-IQR features. The corresponding positive-IQR summary is approximately median 0.134 and mean 2.805. The audit computes these from the supplied records.

Table S14 now prints classifier values 0.505968 in the two severity-zero entries (marginal and coupling controls), and 0.987874 for the severity-one coupling control. Earlier canonical records contained 0.505879, 0.505879 and 0.987818 respectively. Both snapshots are retained. No fitted scientific reference table has been rewritten to conceal this difference. `protocols/supplement_table_s14.json` represents the current printed supplement; `protocols/historical_supplement_table_s14.json` preserves the earlier printed targets.

Run `supplementary_audit` to regenerate the population and table checks. Its detailed output is under `run_root/supplementary_discrepancies/`. The current printed values agree with the newer controlled reference; the older canonical snapshot still differs in those three cells.

## Strict comparison

Use the original comparators, rounding conventions and tolerances supplied by the experiment. Do not loosen tolerances, update reference CSVs or change random seeds to obtain PASS. Read both `execution_status` and `comparison`: successful computation can still be numerically DIFFERENT. Preserve a difference report alongside the interpreter versions and input hashes. `python compare_runs.py --config config/local.json` regenerates the final report from available stage evidence.

The current user's latest completed Falcon master-run outputs and Python 3.11 dependency closure have not been supplied in this repository preparation. Follow FALCON_FILES_TO_SEND.md to add them before describing that run as independently verified.
