# ============================================================
# POSCTRL v4.1 — role-matched C2ST scientific summary
# ============================================================

c2st_summary = (
    POS_C2ST
    .groupby(["role", "control", "scope"])
    .agg(
        n=("delta_auc", "size"),
        candidate_auc_mean=("candidate_c2st_max_auc", "mean"),
        candidate_auc_sd=("candidate_c2st_max_auc", "std"),
        anchor_auc_mean=("anchor_c2st_max_auc", "mean"),
        anchor_auc_sd=("anchor_c2st_max_auc", "std"),
        delta_auc_mean=("delta_auc", "mean"),
        delta_auc_sd=("delta_auc", "std"),
        delta_auc_median=("delta_auc", "median"),
        delta_auc_min=("delta_auc", "min"),
        delta_auc_max=("delta_auc", "max"),
    )
    .reset_index()
)

display(c2st_summary)

c2st_summary.to_csv(
    OUT / "POSCTRL_V41_C2ST_summary.csv",
    index=False
)

# Paired mild-vs-strong comparison within role/scope/seed
paired = (
    POS_C2ST
    .pivot_table(
        index=["role", "scope", "seed"],
        columns="control",
        values="delta_auc",
        aggfunc="first"
    )
    .reset_index()
)

paired["strong_minus_mild_delta_auc"] = (
    paired["strong"] - paired["mild"]
)

display(
    paired.groupby(["role", "scope"])
    ["strong_minus_mild_delta_auc"]
    .agg(["count", "mean", "median", "min", "max"])
    .reset_index()
)

paired.to_csv(
    OUT / "POSCTRL_V41_C2ST_mild_vs_strong_paired.csv",
    index=False
)