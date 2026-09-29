
# ============================================================
# 12. Per-seed scenario execution
# ============================================================
def scenario_job(s,fixture_seed,seed):
    sid=s["scenario_id"]; path=checkpoint("scenario_jobs",sid,f"fixture{fixture_seed}",f"seed{seed}",suffix=".json"); upath=path.with_suffix(".utility.csv"); old=load_cp(path,PROTOCOL_HASH)
    if old is not None:
        print(f"[SCENARIO] SKIP {sid} fixture={fixture_seed} seed={seed}")
        return old
    print(f"[SCENARIO] RUN  {sid} fixture={fixture_seed} seed={seed}")
    frame,truth,times=make_fixture(fixture_seed,s["fixture_context"],float(s["core_severity"])); bind_fixture(frame,fixture_seed,s["fixture_context"],times)
    train=CANON_DF.iloc[PRIMARY_SPLIT["train"]].reset_index(drop=True); test=CANON_DF.iloc[PRIMARY_SPLIT["test"]].reset_index(drop=True)
    context=task_context(s); table,valid=ADMISSION_CACHE[(context,fixture_seed)]; cards=cards_for(s,valid)
    source,spec,meta=construct_source(s,train,int(seed)); contract=source_contract(s,spec,train,source,meta)
    if s["claim_kind"]=="utility" and cards:
        u=evaluate_utility(source,spec,PRIMARY_SPLIT,int(seed),force_all_suites=True,evaluation_axis="future",reported_fold_id="primary",task_models=cards); u["scientific_status"]="valid"; u["known_truth_diagnostic_only"]=not contract["source_valid"]; u.to_csv(upath,index=False); n_u=len(u)
    else: pd.DataFrame().to_csv(upath,index=False); n_u=0
    c2st={}
    if s["claim_kind"]=="closeness":
        cols=list(FEATURE_SCOPES["protocol_value_v3"]); anchor=role_anchor(train,s["suite"],len(source),int(seed),FEATURE_SCOPES["generator_v2"])
        c2st={"candidate":c2st_profile(test,source,cols,seed=int(seed),row_cap=CFG["row_cap_metrics"],n_splits=CFG["c2st_splits"],n_permutations=CFG["c2st_permutations"],rf_trees=CFG["c2st_trees"],null_trees=CFG["c2st_null_trees"]),"anchor":c2st_profile(test,anchor,cols,seed=int(seed)+90000,row_cap=CFG["row_cap_metrics"],n_splits=CFG["c2st_splits"],n_permutations=CFG["c2st_permutations"],rf_trees=CFG["c2st_trees"],null_trees=CFG["c2st_null_trees"])}
    payload={"scenario_id":sid,"fixture_seed":fixture_seed,"protocol_seed":seed,"fixture_truth":truth,"task_admission_rows":len(table),"admitted_scenario_cards":[c.card_id for c in cards],"source_contract":contract,"source_metadata":{k:v for k,v in meta.items() if k!="base_sample"},"utility_rows":n_u,"utility_path":str(upath),"c2st":c2st}
    save_cp(path,PROTOCOL_HASH,payload); print(f"[SCENARIO] DONE {sid} fixture={fixture_seed} seed={seed} utility_rows={n_u}"); del frame,train,test,source; gc.collect(); return {"protocol_hash":PROTOCOL_HASH,**normalise_json(payload)}
