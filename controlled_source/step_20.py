
# ============================================================
# 13. Aggregate exact canonical outcomes
# ============================================================
def cap_payload(p0,cap,suite): return p0.get("licences",{}).get(cap,{}).get(suite,{}) if p0 else {}
def aggregate_closeness(jobs):
    rows=[]
    for j in jobs:
        if not j.get("c2st"): continue
        rows+=[{"generator_id":"candidate","seed":j["protocol_seed"],"scientific_status":"valid","c2st_max_auc":j["c2st"]["candidate"]["c2st_max_auc"]},{"generator_id":"anchor","seed":j["protocol_seed"],"scientific_status":"valid","c2st_max_auc":j["c2st"]["anchor"]["c2st_max_auc"]}]
    f=pd.DataFrame(rows)
    if f.empty: return {"permission":"NOT_ESTIMABLE"}
    paired=paired_seed_ci(f,"c2st_max_auc","candidate","anchor",seed=7771,draws=BOOTSTRAP_DRAWS); ca=f[f.generator_id=="candidate"]; an=f[f.generator_id=="anchor"]; cp=float(ca.c2st_max_auc.max()); ap=float(an.c2st_max_auc.max())
    return {"permission":fidelity_permission(float(paired["ci_lo"]),float(paired["ci_hi"]),cp,ap),"estimate":paired["delta"],"ci_lo":paired["ci_lo"],"ci_hi":paired["ci_hi"],"candidate_peak_auc":cp,"anchor_peak_auc":ap,"candidate_mean_auc":float(ca.c2st_max_auc.mean()),"anchor_mean_auc":float(an.c2st_max_auc.mean())}
def aggregate_utility(jobs):
    frames=[]
    for j in jobs:
        p=Path(j["utility_path"])
        if p.exists() and p.stat().st_size>1:
            try:
                x=pd.read_csv(p,low_memory=False)
                if len(x): frames.append(x)
            except pd.errors.EmptyDataError: pass
    u=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    if u.empty: return u,{},"NOT_ESTIMABLE"
    summary=hierarchical_utility_bootstrap(u,seed=9191,draws=BOOTSTRAP_DRAWS); return u,summary,utility_permission(float(summary["loss_ratio_ci_lo"]),float(summary["loss_ratio_ci_hi"]))
def absolute_outcome(u):
    if u.empty or "synthetic_skill_gain" not in u: return "NOT_ESTIMABLE"
    x=u[(u.status.astype(str)=="ok")]["synthetic_skill_gain"]; x=pd.to_numeric(x,errors="coerce").dropna()
    return "LICENSED_NONINFERIOR" if len(x) and float(x.median())>=BASE_CFG["min_reference_skill_gain"] else "LICENSED_INFERIOR" if len(x) else "NOT_ESTIMABLE"
def classify(s,instrument,admission,p0,jobs):
    cap=s["capability"]; suite=s["suite"]; pp=cap_payload(p0,cap,suite); admitted=int(admission["admissible"].astype(bool).sum()) if len(admission) else 0
    if s["claim_kind"]=="closeness":
        stage2=True; stage3_reference_viability=True; stage3_relative=True; stage3=True
    elif s["p0_context"]=="none":
        stage2=admitted>0; stage3_reference_viability=stage2; stage3_relative=stage2; stage3=stage2
    else:
        stage2=bool(admitted>0 and pp.get("eligible",False) and pp.get("identity_ok",False))
        stage3_reference_viability=bool(pp.get("reference_viability_ok",False))
        stage3_relative=bool(pp.get("relative_licensed",pp.get("licensed",False)))
        stage3=bool(stage2 and stage3_reference_viability and stage3_relative)
    source_valid=bool(jobs and all(j["source_contract"].get("source_valid",False) for j in jobs)); failures=[j["source_contract"].get("failure_type","") for j in jobs if not j["source_contract"].get("source_valid",False)]; failure_type="" if source_valid else ("FIT_INVALID" if "FIT_INVALID" in failures else "SOURCE_INVALID")
    if s["claim_kind"]=="utility": u,us,outcome=aggregate_utility(jobs); close={}; resolution=True
    else: close=aggregate_closeness(jobs); outcome=close.get("permission","NOT_ESTIMABLE"); resolution=outcome!="NOT_ESTIMABLE"; u=pd.DataFrame(); us={}
    estimable=bool(stage2 and (resolution if s["claim_kind"]=="closeness" else True)); perm,diag,stage=precedence(instrument["instrument_valid"],estimable,stage3,source_valid,failure_type)
    promoted=outcome if perm=="ADMISSIBLE" else ("NOT_ESTIMABLE" if s["claim_kind"]=="closeness" and perm=="NOT_ESTIMABLE" else "NOT_APPLICABLE")
    for j in jobs: diag.extend(str(x) for x in j["source_contract"].get("failed_predicates",[]))
    return {"instrument_valid":instrument["instrument_valid"],"task_admitted_count":admitted,"stage2_estimable":stage2,"stage3_reference_viability_ok":stage3_reference_viability,"stage3_relative_property_licensed":stage3_relative,"stage3_property_licensed":stage3,"source_valid":source_valid,"source_failure_type":failure_type,"resolution_available":resolution,"observed_permission":perm,"observed_outcome":promoted,"observed_failure_stage":stage,"diagnostic_failures":list(dict.fromkeys(diag)),"utility_summary":us,"absolute_skill_outcome":absolute_outcome(u),"closeness_summary":close}
