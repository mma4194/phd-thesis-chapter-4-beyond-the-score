# ============================================================
# POSCTRL v4.1 — capability-level utility decomposition
# ============================================================

ok = POS_UTILITY[
    POS_UTILITY["status"].eq("ok")
    & POS_UTILITY["p0_licensed"].fillna(False).astype(bool)
    & POS_UTILITY["loss_ratio"].notna()
].copy()

cap_summary = (
    ok.groupby(
        [
            "positive_control_role",
            "positive_control",
            "capability"
        ]
    )
    .agg(
        n=("loss_ratio", "size"),
        median_loss_ratio=("loss_ratio", "median"),
        mean_loss_ratio=("loss_ratio", "mean"),
        noninferior_rate=("noninferior", "mean"),
        n_task_families=("task_family", "nunique"),
    )
    .reset_index()
)

display(cap_summary)

cap_summary.to_csv(
    OUT / "POSCTRL_V41_capability_summary.csv",
    index=False
)