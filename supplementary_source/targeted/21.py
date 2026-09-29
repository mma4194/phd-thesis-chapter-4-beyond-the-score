
summary = {
    "canonical_notebook":str(CANONICAL_NOTEBOOK),
    "canonical_sha256":sha256_file(CANONICAL_NOTEBOOK),
    "definition_count":int(len(DEFINITION_AUDIT)),
    "wass2": {
        "completed":"WASS_FEATURE" in globals(),
        "max_abs_reproduction_error":float(check["abs_diff"].max()) if "check" in globals() else None,
        "n_floor_active_total":int(WASS_FEATURE["floor_active"].sum()) if "WASS_FEATURE" in globals() else None,
        "severity1_max_top1_share":float(
            WASS_FEATURE[WASS_FEATURE.severity.eq(1.0)]
            .groupby("fixture_seed")["share_within_seed_severity"].max().max()
        ) if "WASS_FEATURE" in globals() else None,
    },
    "c2st2": {
        "completed":"C2ST27" in globals(),
        "rows":int(len(C2ST27)) if "C2ST27" in globals() else None,
        "resolved_0_995":int(C2ST27["resolved_0_995"].sum()) if "C2ST27" in globals() else None,
        "resolved_0_9945":int(C2ST27["resolved_0_9945"].sum()) if "C2ST27" in globals() else None,
    },
    "new_experiments_enabled":bool(RUN_NEW_EXPERIMENTS),
    "posctrl1_completed":"POS_METRICS" in globals(),
    "tempctrl1_completed":"TEMPCTRL" in globals(),
}
write_json(OUT/"targeted_v4_summary.json",summary)
print(json.dumps(summary,indent=2))
print("\nReturn this notebook plus the complete TIOT_TARGETED_V4_OUTPUTS directory.")
