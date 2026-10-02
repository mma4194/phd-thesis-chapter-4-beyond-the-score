
# ============================================================
# 1. Read frozen truth and completed KT10 outcomes
# ============================================================
truth_path=KT_OUTPUT/"truth"/"known_truth_registry.csv"
if not truth_path.exists():
    # Some archives place truth at the top-level exactly as expected; fail if absent.
    raise FileNotFoundError(truth_path)

TRUTH=pd.read_csv(truth_path)
KT10_TRUTH=TRUTH[TRUTH["scenario_id"].eq("KT10")].copy()
assert len(KT10_TRUTH)==1
assert KT10_TRUTH.iloc[0]["capability"]==EXPECTED_KT10_CAPABILITY

RESULTS=pd.read_csv(FULL/"tables"/"full_protocol_results.csv",low_memory=False)
KT10_RESULTS=RESULTS[RESULTS["scenario_id"].eq("KT10")].copy()
assert len(KT10_RESULTS)==4, f"Expected four aggregate KT10 fixture units, found {len(KT10_RESULTS)}"

display(KT10_TRUTH.T)
display(KT10_RESULTS[[
    "scenario_id","fixture_seed","expected_permission","observed_permission",
    "expected_failure_stage","observed_failure_stage",
    "stage2_estimable","stage3_property_licensed","source_valid"
]])

KT10_TRUTH.to_csv(FORENSIC_ROOT/"tables"/"KT10_frozen_truth.csv",index=False)
KT10_RESULTS.to_csv(FORENSIC_ROOT/"tables"/"KT10_completed_results.csv",index=False)
