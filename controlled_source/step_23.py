
# ============================================================
# 15. Stage ablations
# ============================================================
def no_ceiling(ci_lo,ci_hi):
    if not np.isfinite(ci_lo) or not np.isfinite(ci_hi): return "NOT_ESTIMABLE"
    if ci_lo>BASE_CFG["c2st_excess_practical_margin"]: return "LICENSED_INFERIOR"
    if ci_hi<=BASE_CFG["c2st_excess_practical_margin"]: return "LICENSED_NONINFERIOR"
    return "LICENSED_INCONCLUSIVE"
def ablate(row,name,settings):
    a=bool(row["instrument_valid"]); b=bool(row["stage2_estimable"]); c=bool(row["stage3_property_licensed"]); d=bool(row["source_valid"]); ft=row["source_failure_type"]
    if settings.get("skip_stage1"): a=True
    if settings.get("skip_stage2"): b=True
    if settings.get("skip_stage3"): c=True
    if settings.get("skip_stage3a_reference_viability"): c=bool(row.get("stage3_relative_property_licensed",c))
    if settings.get("skip_stage4"): d=True
    outcome=row["observed_outcome"]
    if row["claim_kind"]=="closeness":
        cl=row.get("closeness_summary",{})
        if settings.get("skip_resolution_gate"): b=True; outcome=no_ceiling(float(cl.get("ci_lo",np.nan)),float(cl.get("ci_hi",np.nan)))
        else: b=b and bool(row["resolution_available"])
    elif settings.get("no_matched_reference"): outcome=row.get("absolute_skill_outcome","NOT_ESTIMABLE")
    perm,fail,stage=precedence(a,b,c,d,ft)
    if perm!="ADMISSIBLE": outcome="NOT_ESTIMABLE" if row["claim_kind"]=="closeness" and perm=="NOT_ESTIMABLE" else "NOT_APPLICABLE"
    pc=perm==row["expected_permission"]; oc=row["expected_outcome"]=="NOT_APPLICABLE" or outcome==row["expected_outcome"]
    return {"ablation":name,"scenario_id":row["scenario_id"],"fixture_seed":row["fixture_seed"],"expected_permission":row["expected_permission"],"observed_permission":perm,"expected_outcome":row["expected_outcome"],"observed_outcome":outcome,"permission_correct":pc,"outcome_correct":oc,"full_label_correct":pc and oc,"observed_failure_stage":stage,"expected_failure_stage":row["expected_failure_stage"],"failure_stage_correct":stage==row["expected_failure_stage"],"mixed_failure":row["mixed_failure"],"failure_vector":"|".join(fail)}
ABLATION_RESULTS=pd.DataFrame([ablate(row,name,settings) for row in CORE_RESULTS for name,settings in ABLATIONS.items()]); ABLATION_RESULTS.to_csv(PROFILE_ROOT/"tables"/"stage_ablation_results.csv",index=False); display(ABLATION_RESULTS)
