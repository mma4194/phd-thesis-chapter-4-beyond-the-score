
# ============================================================
# 7. Precedence and Stage 1
# ============================================================
def precedence(instrument_valid,estimable,property_licensed,source_valid,source_failure_type="SOURCE_INVALID"):
    failures=[]
    if not instrument_valid: failures.append("instrument_invalid")
    if not estimable: failures.append("not_estimable")
    if not property_licensed: failures.append("property_unlicensed")
    if not source_valid: failures.append("fit_invalid" if source_failure_type=="FIT_INVALID" else "source_invalid")
    if not instrument_valid: return "INSTRUMENT_INVALID",failures,1
    if not estimable: return "NOT_ESTIMABLE",failures,2
    if not property_licensed: return "PROPERTY_UNLICENSED",failures,3
    if not source_valid: return ("FIT_INVALID" if source_failure_type=="FIT_INVALID" else "SOURCE_INVALID"),failures,4
    return "ADMISSIBLE",failures,0
oracle=[]
for a in [False,True]:
 for b in [False,True]:
  for c in [False,True]:
   for d in [False,True]:
    obs,fail,stage=precedence(a,b,c,d); exp="INSTRUMENT_INVALID" if not a else "NOT_ESTIMABLE" if not b else "PROPERTY_UNLICENSED" if not c else "SOURCE_INVALID" if not d else "ADMISSIBLE"
    oracle.append({"instrument_valid":a,"estimable":b,"property_licensed":c,"source_valid":d,"observed":obs,"expected":exp,"correct":obs==exp,"failure_vector":"|".join(fail),"stage":stage})
STRUCTURAL_PRECEDENCE=pd.DataFrame(oracle); STRUCTURAL_PRECEDENCE.to_csv(PROFILE_ROOT/"tables"/"structural_precedence_exhaustive.csv",index=False)
if not STRUCTURAL_PRECEDENCE["correct"].all(): raise RuntimeError("Precedence oracle failed")

def evidence_csv(member):
    with zipfile.ZipFile(EVIDENCE_ZIP) as z: return pd.read_csv(z.open(member),low_memory=False)
def stage1_checks():
    path=checkpoint("stage1","qualification",suffix=".csv"); meta=path.with_suffix(".json")
    if load_cp(meta,PROTOCOL_HASH) is not None and path.exists(): return pd.read_csv(path)
    if RUN_STAGE1_RECOMPUTE:
        root=PROFILE_ROOT/"stage1_exact"; dirs={"tables":root/"tables","manifests":root/"manifests","figures":root/"figures"}
        for p in dirs.values(): p.mkdir(parents=True,exist_ok=True)
        old=globals().get("DIRS"); globals()["DIRS"]=dirs
        try: _,checks=qualify_metrics_on_controlled_fixture()
        finally: globals()["DIRS"]=old if old is not None else {"tables":PROFILE_ROOT/"tables","manifests":PROFILE_ROOT/"manifests","figures":PROFILE_ROOT/"figures"}
        source="exact canonical recomputation"
    else:
        checks=evidence_csv("tables/table_controlled_instrument_qualification.csv"); source="frozen canonical evidence (smoke only)"
    checks.to_csv(path,index=False); save_cp(meta,PROTOCOL_HASH,{"source":source,"rows":len(checks),"all_passed":bool(checks["passed"].astype(bool).all())}); return checks
STAGE1_CHECKS=stage1_checks()
REQUIRED={"contemporaneous":[("marginal_ks_mean","marginal"),("coupling_corr_mae","coupling"),("c2st_same_distribution_negative_control","none")],"temporal":[("acf_abs_error_mean","order"),("spectral_l1_mean","order"),("transition_rate_mae","order")],"closeness":[("c2st_max_auc","marginal"),("c2st_same_distribution_negative_control","none")]}
def instrument_result(s):
    profile="closeness" if s["claim_kind"]=="closeness" else s["suite"]; rows=[]
    for name,pert in REQUIRED[profile]:
        q=STAGE1_CHECKS[(STAGE1_CHECKS["instrument"].astype(str)==name)&(STAGE1_CHECKS["target_perturbation"].astype(str)==pert)]
        rows.append({"instrument":name,"passed":bool(len(q) and q.iloc[0]["passed"]),"reason":"canonical_check" if len(q) else "missing"})
    fault=s.get("instrument_fault","none")
    if fault=="flat_marginal": rows.append({"instrument":"planted_flat_marginal","passed":False,"reason":"known_truth_flat_response"})
    if fault=="reversed_temporal": rows.append({"instrument":"planted_reversed_temporal","passed":False,"reason":"known_truth_reversed_response"})
    return {"profile":profile,"fault":fault,"instrument_valid":all(r["passed"] for r in rows),"checks":rows}
print("Stage1 canonical pass:",bool(STAGE1_CHECKS["passed"].astype(bool).all()))
fault_curve=[]
for severity in [0.0,0.25,0.50,0.75,1.0]:
    fault_curve.append({"scenario_id":"KT03","fault":"flat_marginal","severity":severity,"response":0.0})
    fault_curve.append({"scenario_id":"KT04","fault":"reversed_temporal","severity":severity,"response":1.0-severity})
pd.DataFrame(fault_curve).to_csv(PROFILE_ROOT/"tables"/"planted_instrument_fault_response.csv",index=False)
