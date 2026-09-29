
TASK_AUDIT = {
    "candidate_cards":int(len(TASKS)),
    "admitted_cards":int(TASKS["admissible"].fillna(False).astype(bool).sum()),
    "rejected_cards":int((~TASKS["admissible"].fillna(False).astype(bool)).sum()),
    "leakage_rows":int(len(TASK_LEAK)),
    "leakage_passes":int(TASK_LEAK["passed"].fillna(False).astype(bool).sum()),
    "test_used_for_selection":int(TASK_LEAK["test_used_for_selection"].fillna(False).astype(bool).sum()),
    "failed_leakage_checks":int((~TASK_LEAK["passed"].fillna(False).astype(bool)).sum()),
    "valid_capabilities":int(TASK_BREADTH.iloc[0]["valid_capabilities"]),
    "valid_families":int(TASK_BREADTH.iloc[0]["valid_families"]),
    "valid_tiers":int(TASK_BREADTH.iloc[0]["valid_tiers"]),
}
print(json.dumps(TASK_AUDIT,indent=2))
display(TASK_LEAK[~TASK_LEAK["passed"].fillna(False).astype(bool)].head(50))
