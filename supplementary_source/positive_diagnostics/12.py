
# ============================================================
# D1. Machine-readable diagnostic summary
# ============================================================
def _paired_order_rate(df, col):
    x=pd.to_numeric(df[col],errors="coerce")
    return float(np.mean(x>0)) if x.notna().any() else np.nan

summary={
    "canonical_sha256":sha256_file(CANONICAL_NOTEBOOK),
    "v41_utility_rows":int(len(POS_UTILITY)),
    "v41_utility_error_rows":int(POS_UTILITY["status"].astype(str).str.startswith("error").sum()),
    "perturbation_realisation": {
        "feature_rows":int(len(REALISATION)),
        "eligible_feature_rows":int(REALISATION["eligible_for_jitter"].sum()),
        "median_strong_to_mild_realised_ratio_by_role": {
            str(k):float(v) for k,v in
            paired.groupby("role")["strong_to_mild_realised_ratio"].median().dropna().items()
        },
    },
    "direct_anchor_c2st": {
        "expected_rows":int(total_jobs),
        "observed_rows":int(len(DIRECT_C2ST)),
        "all_complete":bool(len(DIRECT_C2ST)==total_jobs),
        "strong_gt_mild_rate_by_role_scope": {
            f"{r}|{s}":float(np.mean(g["strong_minus_mild_auc"]>0))
            for (r,s),g in direct_paired.groupby(["role","scope"])
        },
    },
    "anchor_relative_utility": {
        "matched_rows":int((joined["_merge"]=="both").sum()),
        "unmatched_rows":int((joined["_merge"]!="both").sum()),
        "valid_rows":int(len(valid)),
        "strong_worse_than_mild_rate_by_role": {
            str(r):float(np.mean(g["strong_minus_mild_anchor_relative_ratio"]>0))
            for r,g in u_pair.groupby("positive_control_role")
        },
    },
    "interpretation_ready":bool(
        len(DIRECT_C2ST)==total_jobs
        and (joined["_merge"]=="both").all()
        and POS_UTILITY["status"].astype(str).str.startswith("error").sum()==0
    ),
    "note":"Diagnostic-only post-hoc close-out; do not convert to a universal threshold or claim without manuscript-level interpretation."
}

write_json(OUT/"POSCTRL_V42_summary.json",summary)
print(json.dumps(summary,indent=2))
print("\nReturn this executed notebook/HTML plus the complete TIOT_POSCTRL_V42_OUTPUTS directory.")
