
state_changes = int(RAW_DECISIONS.changed.sum())
submission = {
    "p0_raw_vs_applied": "PASS_NO_STATE_CHANGE" if state_changes==0 else f"FAIL_{state_changes}_STATE_CHANGES",
    "training_budget_parity": "PASS" if SAMPLE_PARITY["rows_nonparity"]==0 and SAMPLE_PARITY["rows_ntrain_reference_difference"]==0 else "FAIL",
    "task_leakage": "PASS" if TASK_AUDIT["failed_leakage_checks"]==0 and TASK_AUDIT["test_used_for_selection"]==0 else "FAIL",
    "wasserstein_aggregate": "PASS" if WASS_STATUS["aggregate_reproduced"] else "FAIL",
    "wasserstein_feature_denominator_audit": "REQUIRES_TARGETED_RERUN",
    "note": "This gate covers only checks executable from the frozen residential evidence package."
}
print(json.dumps(submission,indent=2))
(OUTPUT/"closeout_v3.json").write_text(json.dumps(submission,indent=2),encoding="utf-8")
