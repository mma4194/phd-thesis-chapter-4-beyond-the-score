
# ============================================================
# 3. Load completed v4.1 utility and frozen utility ledger
# ============================================================
POS_UTILITY=pd.read_csv(V41_UTILITY,low_memory=False)

with zipfile.ZipFile(EVIDENCE_ZIP) as z:
    FROZEN_UTILITY=pd.read_csv(z.open("tables/table_all_utility_current_plan.csv"),low_memory=False)

assert len(POS_UTILITY)==1990, f"Expected 1990 v4.1 utility rows, got {len(POS_UTILITY)}"
assert not POS_UTILITY["status"].astype(str).str.startswith("error").any(), "v4.1 still contains execution errors"

print("v4.1 utility rows:",len(POS_UTILITY))
print("Frozen utility rows:",len(FROZEN_UTILITY))
print("v4.1 roles:",sorted(POS_UTILITY["positive_control_role"].dropna().unique()))
