
# ============================================================
# 14. Run and checkpoint all active core scenarios
# ============================================================
CORE_RESULTS=[]
for fixture_seed in ACTIVE_FIXTURE_REPLICATES:
    for s in ACTIVE_SCENARIOS:
        sid=s["scenario_id"]; apath=checkpoint("scenario_aggregate",sid,f"fixture{fixture_seed}",suffix=".json"); old=load_cp(apath,PROTOCOL_HASH)
        if old is not None: CORE_RESULTS.append(old); continue
        jobs=[scenario_job(s,int(fixture_seed),int(seed)) for seed in ACTIVE_PROTOCOL_SEEDS]
        context=task_context(s); admission,_=ADMISSION_CACHE[(context,fixture_seed)]; p0=P0_CACHE.get((s["p0_context"],fixture_seed)) if s["p0_context"]!="none" else None
        observed=classify(s,instrument_result(s),admission,p0,jobs)
        result={"scenario_id":sid,"fixture_seed":fixture_seed,"expected_permission":s["expected_permission"],"expected_outcome":s["expected_outcome"],"expected_failure_stage":s["expected_failure_stage"],"mixed_failure":s["mixed_failure"],"claim_kind":s["claim_kind"],"suite":s["suite"],"capability":s["capability"],**observed}
        result["permission_correct"]=result["observed_permission"]==result["expected_permission"]; result["outcome_correct"]=s["expected_outcome"]=="NOT_APPLICABLE" or result["observed_outcome"]==s["expected_outcome"]; result["full_label_correct"]=result["permission_correct"] and result["outcome_correct"]; result["failure_stage_correct"]=int(result["observed_failure_stage"])==int(s["expected_failure_stage"])
        save_cp(apath,PROTOCOL_HASH,result); CORE_RESULTS.append({"protocol_hash":PROTOCOL_HASH,**normalise_json(result)})
        print(sid,"fixture",fixture_seed,"expected",s["expected_permission"],s["expected_outcome"],"observed",result["observed_permission"],result["observed_outcome"])

def flatten_result(row):
    return {k:v for k,v in row.items() if k not in {"utility_summary","closeness_summary","diagnostic_failures"}}|{"diagnostic_failures":"|".join(row.get("diagnostic_failures",[])),"utility_geometric_mean_loss_ratio":row.get("utility_summary",{}).get("geometric_mean_loss_ratio"),"utility_ci_lo":row.get("utility_summary",{}).get("loss_ratio_ci_lo"),"utility_ci_hi":row.get("utility_summary",{}).get("loss_ratio_ci_hi"),"c2st_excess_estimate":row.get("closeness_summary",{}).get("estimate"),"c2st_excess_ci_lo":row.get("closeness_summary",{}).get("ci_lo"),"c2st_excess_ci_hi":row.get("closeness_summary",{}).get("ci_hi"),"candidate_peak_auc":row.get("closeness_summary",{}).get("candidate_peak_auc"),"anchor_peak_auc":row.get("closeness_summary",{}).get("anchor_peak_auc")}
CORE_RESULTS_FRAME=pd.DataFrame([flatten_result(x) for x in CORE_RESULTS]); CORE_RESULTS_FRAME.to_csv(PROFILE_ROOT/"tables"/"full_protocol_results.csv",index=False); display(CORE_RESULTS_FRAME)
expected_units=len(ACTIVE_SCENARIOS)*len(ACTIVE_FIXTURE_REPLICATES)
if len(CORE_RESULTS_FRAME)!=expected_units: raise RuntimeError(f"Expected {expected_units} aggregate units, found {len(CORE_RESULTS_FRAME)}")
error_frames=[]
for utility_file in (PROFILE_ROOT/"checkpoints").rglob("*.utility.csv"):
    try:
        uf=pd.read_csv(utility_file,low_memory=False)
    except pd.errors.EmptyDataError:
        continue
    if "status" in uf:
        bad=uf[uf["status"].astype(str).str.startswith("error:")].copy()
        if len(bad): bad["source_file"]=str(utility_file); error_frames.append(bad)
UTILITY_EXECUTION_ERRORS=pd.concat(error_frames,ignore_index=True) if error_frames else pd.DataFrame()
UTILITY_EXECUTION_ERRORS.to_csv(PROFILE_ROOT/"tables"/"utility_execution_errors.csv",index=False)
if len(UTILITY_EXECUTION_ERRORS): raise RuntimeError(f"Canonical utility evaluator produced {len(UTILITY_EXECUTION_ERRORS)} error rows; inspect utility_execution_errors.csv")
print("Execution-integrity audit passed: aggregate units=",expected_units,"utility error rows=0")
