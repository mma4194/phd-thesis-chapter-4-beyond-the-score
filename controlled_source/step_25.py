
# ============================================================
# 16. Checkpointed severity sweeps
# ============================================================
def run_sweeps():
    if not RUN_SEVERITY_SWEEPS: print("Severity sweeps skipped in smoke mode"); return pd.DataFrame()
    rows=[]
    for fixture_seed in ACTIVE_FIXTURE_REPLICATES:
        stable,_,times=make_fixture(fixture_seed,"stable")
        for intervention,severities in SEVERITY_SWEEPS.items():
            seeds=[FULL_PROTOCOL_SEEDS[0]] if intervention in {"session_shift","jitter_iqr"} else ACTIVE_PROTOCOL_SEEDS
            for sev in severities:
                for seed in seeds:
                    path=checkpoint("severity",intervention,f"fixture{fixture_seed}",f"severity{sev}__seed{seed}",suffix=".json"); old=load_cp(path,PROTOCOL_HASH)
                    if old is not None: rows.append(old); continue
                    context="session_shift" if intervention=="session_shift" else "stable"; frame,_,times=make_fixture(fixture_seed,context,float(sev)); bind_fixture(frame,fixture_seed,context,times); train=CANON_DF.iloc[PRIMARY_SPLIT["train"]].reset_index(drop=True); test=CANON_DF.iloc[PRIMARY_SPLIT["test"]].reset_index(drop=True); cols=FEATURE_SCOPES["generator_v2"]; n=min(CFG["generation_rows"],len(train)); base=real_resample_generator(train,n,int(seed),cols,{})
                    if intervention=="jitter_iqr": source=jitter(base,train,cols,float(sev),int(seed)+10000); spec=GeneratorSpec(f"sweep_jitter_{sev}","kt_transparent_positive","known_truth",False,False,False,{}); stub={"source_kind":"mild_jitter"}
                    elif intervention=="support_violation":
                        source=base.copy(); count=int(round(float(sev)*len(source)))
                        if count: source.loc[np.arange(count),"iot__power"]=float(train["iot__power"].max()+25*max(robust_iqr(train["iot__power"]),1))
                        spec=GeneratorSpec(f"sweep_support_{sev}","kt_transparent_invalid","known_truth",False,False,False,{}); stub={"source_kind":"support_violation"}
                    elif intervention=="learned_collapse":
                        source=base.copy(); vc=list(FEATURE_SCOPES["all_value_v3"]); count=int(round(float(sev)*len(vc)))
                        for c in vc[:count]: source[c]=float(train[c].median())
                        spec=GeneratorSpec(f"sweep_collapse_{sev}","learned_known_truth_collapse","known_truth",False,False,False,{}); stub={"source_kind":"learned_collapse"}
                    elif intervention=="learned_activity":
                        source=base.copy(); rng=np.random.default_rng(int(seed)+70000)
                        for c in FEATURE_SCOPES["all_value_v3"]:
                            count=int(round(float(sev)*len(source)))
                            if count:
                                idx=rng.choice(len(source),count,replace=False); v=source[c].to_numpy(float,copy=True); v[idx]=0; source[c]=v
                        spec=GeneratorSpec(f"sweep_activity_{sev}","learned_known_truth_activity","known_truth",False,False,False,{}); stub={"source_kind":"learned_activity"}
                    elif intervention=="session_shift": source=base.copy(); spec=GeneratorSpec(f"sweep_session_{sev}","kt_transparent_positive","known_truth",False,False,False,{}); stub={"source_kind":"mild_jitter"}
                    else: raise ValueError(intervention)
                    if intervention in {"support_violation","learned_collapse","learned_activity"}:
                        con=source_contract(stub,spec,train,source,{}); payload={"intervention":intervention,"severity":float(sev),"fixture_seed":fixture_seed,"protocol_seed":seed,"source_valid":con["source_valid"],"failure_type":con["failure_type"],"failed_predicates":con["failed_predicates"],"response":float(not con["source_valid"])}
                    else:
                        profile=c2st_profile(test if intervention=="session_shift" else train,source,FEATURE_SCOPES["protocol_value_v3"],seed=int(seed),row_cap=CFG["row_cap_metrics"],n_splits=CFG["c2st_splits"],n_permutations=CFG["c2st_permutations"],rf_trees=CFG["c2st_trees"],null_trees=CFG["c2st_null_trees"])
                        payload={"intervention":intervention,"severity":float(sev),"fixture_seed":fixture_seed,"protocol_seed":seed,"c2st_max_auc":float(profile["c2st_max_auc"]),"c2st_null_p95":float(profile["c2st_null_p95"]),"response":float(profile["c2st_max_auc"]),"resolution_limited":bool(profile["c2st_max_auc"]>=BASE_CFG["degenerate_c2st_threshold"])}
                    save_cp(path,PROTOCOL_HASH,payload); rows.append({"protocol_hash":PROTOCOL_HASH,**normalise_json(payload)}); del frame,train,test,source; gc.collect()
    return pd.DataFrame(rows)
SEVERITY_RESULTS=run_sweeps()
if len(SEVERITY_RESULTS): SEVERITY_RESULTS.to_csv(PROFILE_ROOT/"tables"/"severity_response.csv",index=False); display(SEVERITY_RESULTS)
