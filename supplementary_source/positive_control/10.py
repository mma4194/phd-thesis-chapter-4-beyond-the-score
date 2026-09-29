# ============================================================
# Recover completed POSCTRL utility run — DO NOT recompute
# ============================================================

assert len(utility) == 20, f"Expected 20 completed chunks, found {len(utility)}"

POS_UTILITY = pd.concat(utility, ignore_index=True)

expected_rows = (
    10 * 58 +   # contemporaneous: 2 severities × 5 seeds
    10 * 141    # temporal:       2 severities × 5 seeds
)

assert len(POS_UTILITY) == expected_rows, (
    f"Unexpected POSCTRL utility row count: "
    f"{len(POS_UTILITY)} != {expected_rows}"
)

POS_UTILITY.to_csv(
    OUT / "POSCTRL_V41_utility.csv",
    index=False
)

status = (
    POS_UTILITY
    .groupby(
        ["positive_control_role", "positive_control", "status"],
        dropna=False
    )
    .size()
    .rename("n")
    .reset_index()
)

display(status)

errors = POS_UTILITY[
    POS_UTILITY["status"].astype(str).str.startswith("error")
].copy()

print("Total utility rows:", len(POS_UTILITY))
print("Completed chunks:", len(utility))
print("Error rows:", len(errors))
print("Saved:", OUT / "POSCTRL_V41_utility.csv")

if len(errors):
    display(
        errors[
            [
                "positive_control_role",
                "positive_control",
                "task_id",
                "model_id",
                "error",
            ]
        ].head(50)
    )