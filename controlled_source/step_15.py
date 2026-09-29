
# ============================================================
# 9. Exact P0 pair-seed jobs and decision block
# ============================================================
def p0_pair_job(context,fixture_seed,frame,times,blocks,pair,seed,cards):
    stem=f"{pair['pair_id']}__seed{seed}"; path=checkpoint("p0",context,f"fixture{fixture_seed}",stem,suffix=".json"); upath=path.with_suffix(".utility.csv")
    old=load_cp(path,PROTOCOL_HASH)
    if old is not None and upath.exists():
        print(f"[P0] SKIP {context} fixture={fixture_seed} {stem}")
        return old
    print(f"[P0] RUN  {context} fixture={fixture_seed} {stem}")
    bind_fixture(frame,fixture_seed,context,times); columns=FEATURE_SCOPES["generator_v2"]
    source_idx=blocks[int(pair["source_block"])]; target_idx=blocks[int(pair["target_block"])]; source=CANON_DF.iloc[source_idx][columns].reset_index(drop=True); n=len(source)
    split={"fold_id":f"p0_{pair['pair_id']}","train":np.asarray(source_idx,dtype=np.int64),"val":np.array([],dtype=np.int64),"test":np.asarray(target_idx,dtype=np.int64),"inner_fit":np.array([],dtype=np.int64),"inner_calib":np.array([],dtype=np.int64)}
    bl=max(4*int(CFG["max_window_span"]),min(n//5,3600))
    anchors=[
      (GeneratorSpec("real_identity","p0_anchor","p0",True,False,False,{}),source.copy()),
      (GeneratorSpec("real_block_a","p0_anchor","p0",True,False,False,{}),real_block_generator(source,n,seed+101,columns,{"block_length":bl})),
      (GeneratorSpec("real_block_b","p0_anchor","p0",True,False,False,{}),real_block_generator(source,n,seed+202,columns,{"block_length":bl})),
      (GeneratorSpec("real_resample","real_anchor","p0",False,False,False,{}),real_resample_generator(source,n,seed+303,columns,{})),
    ]
    frames=[]; summaries=[]
    for spec,anchor in anchors:
        u=evaluate_utility(anchor,spec,split,int(seed),force_all_suites=True,evaluation_axis="p0_matched_block",reported_fold_id=pair["pair_id"],task_models=cards)
        u["scientific_status"]="valid"; u["p0_anchor"]=spec.generator_id; u["p0_pair_id"]=pair["pair_id"]; u["p0_phase"]=pair["phase"]; u["p0_seed"]=int(seed); frames.append(u)
        for row in p0_capability_summary(u): summaries.append({**row,"pair_id":pair["pair_id"],"phase":pair["phase"],"seed":int(seed),"profile_distance":float(pair["profile_distance"]),"source_rows":len(source_idx),"target_rows":len(target_idx)})
    pd.concat(frames,ignore_index=True).to_csv(upath,index=False)
    payload={"context":context,"fixture_seed":fixture_seed,"pair":pair,"protocol_seed":seed,"utility_rows":sum(len(x) for x in frames),"summary_rows":summaries,"utility_path":str(upath)}
    save_cp(path,PROTOCOL_HASH,payload); print(f"[P0] DONE {context} fixture={fixture_seed} {stem} rows={payload['utility_rows']}"); return {"protocol_hash":PROTOCOL_HASH,**normalise_json(payload)}


def absolute_reference_viability(context,fixture_seed):
    """KT-v2 Stage 3A: absolute matched-real reference viability.

    Uses only qualification-phase real_identity rows. Task/model rows are collapsed
    task-family first, then capability-wise within each pair×seed. The independent
    pair and stochastic-seed axes are then resampled by the exact canonical
    crossed_pair_seed_ci implementation.
    """
    cpdir=PROFILE_ROOT/"checkpoints"/"p0"/context/f"fixture{fixture_seed}"
    frames=[]
    for p in sorted(cpdir.glob("*.utility.csv")):
        try: x=pd.read_csv(p,low_memory=False)
        except pd.errors.EmptyDataError: continue
        if len(x): frames.append(x)
    if not frames: return pd.DataFrame()
    u=pd.concat(frames,ignore_index=True)
    q=u[
        (u["p0_phase"].astype(str)=="qualification") &
        (u["p0_anchor"].astype(str)=="real_identity") &
        (u["status"].astype(str)=="ok")
    ].copy()
    if q.empty: return pd.DataFrame()
    q["reference_skill_gain"]=pd.to_numeric(q["reference_skill_gain"],errors="coerce")
    q["pair_id"]=q["p0_pair_id"].astype(str)
    q["seed"]=pd.to_numeric(q["p0_seed"],errors="coerce")
    family=(q.groupby(["suite","capability","pair_id","seed","task_family"],dropna=False)
              .agg(reference_skill_gain=("reference_skill_gain","median")).reset_index())
    cap=(family.groupby(["suite","capability","pair_id","seed"],dropna=False)
               .agg(value=("reference_skill_gain","mean")).reset_index())
    rows=[]
    for j,((suite,capability),g) in enumerate(cap.groupby(["suite","capability"],dropna=False)):
        st=crossed_pair_seed_ci(g[["pair_id","seed","value"]],seed=SEED0+7000+j)
        estimable=bool(st["n_pairs"]>=CFG["p0_min_qualification_pairs"])
        viable=bool(estimable and np.isfinite(st["ci_lo"]) and st["ci_lo"]>0.0)
        rows.append({
            "capability":str(capability),"suite":str(suite),
            "criterion":"absolute_matched_real_reference_viability",
            "estimate":st["estimate"],"ci_lo":st["ci_lo"],"ci_hi":st["ci_hi"],
            "n_pairs":st["n_pairs"],"n_seeds":st["n_seeds"],"n_units":st["n_cells"],
            "threshold":"crossed pair-seed 95% CI lower bound of reference_skill_gain > 0",
            "passed":viable,"estimable":estimable,
        })
    return pd.DataFrame(rows)

def p0_decision(context,fixture_seed,summary,pairs):
    path=checkpoint("p0_decisions",context,f"fixture{fixture_seed}",suffix=".json"); old=load_cp(path,PROTOCOL_HASH)
    if old is not None: return old
    root=PROFILE_ROOT/"tables"/"p0"/context/f"fixture{fixture_seed}"; root.mkdir(parents=True,exist_ok=True)
    global DIRS,P0_SEED_SUMMARY,P0_MATCHED_PAIRS,P0_DECISIONS,P0_LICENSE_BY_CAPABILITY,P0_GLOBAL_BY_SUITE,P0_LICENSE,P0_LICENSE_TABLE
    DIRS={"tables":root,"manifests":root,"figures":root}; P0_SEED_SUMMARY=summary.copy(); P0_MATCHED_PAIRS=copy.deepcopy(pairs)
    exec(CANONICAL_P0_DECISION_SOURCE,globals(),globals())

    # KT-v2 Stage 3A: require absolute matched-real predictive viability before
    # the unchanged canonical relative Stage-3 property criteria can license.
    REFERENCE_VIABILITY=absolute_reference_viability(context,fixture_seed)
    REFERENCE_VIABILITY.to_csv(root/"table_p0_absolute_reference_viability.csv",index=False)
    if len(REFERENCE_VIABILITY):
        P0_DECISIONS=pd.concat([P0_DECISIONS,REFERENCE_VIABILITY.drop(columns=["estimable"],errors="ignore")],ignore_index=True)
    for _,rv in REFERENCE_VIABILITY.iterrows():
        cap=str(rv["capability"]); suite=str(rv["suite"])
        if cap in P0_LICENSE_BY_CAPABILITY and suite in P0_LICENSE_BY_CAPABILITY[cap]:
            payload=P0_LICENSE_BY_CAPABILITY[cap][suite]
            payload["relative_licensed"]=bool(payload.get("licensed",False))
            payload["reference_viability_estimable"]=bool(rv["estimable"])
            payload["reference_viability_ok"]=bool(rv["passed"])
            payload["reference_skill_gain_estimate"]=float(rv["estimate"]) if np.isfinite(rv["estimate"]) else np.nan
            payload["reference_skill_gain_ci_lo"]=float(rv["ci_lo"]) if np.isfinite(rv["ci_lo"]) else np.nan
            payload["reference_skill_gain_ci_hi"]=float(rv["ci_hi"]) if np.isfinite(rv["ci_hi"]) else np.nan
            payload["licensed"]=bool(payload["relative_licensed"] and payload["reference_viability_ok"])

    # Recompute global suite licences after the Stage-3A modification.
    P0_GLOBAL_BY_SUITE={suite:_global_p0_suite(suite) for suite in ("contemporaneous","temporal")}
    P0_LICENSE={
        "contemporaneous":bool(P0_GLOBAL_BY_SUITE["contemporaneous"]["passed"]),
        "temporal":bool(P0_GLOBAL_BY_SUITE["temporal"]["passed"]),
        "temporal_requires_order_preservation":True,
        "global_by_suite":P0_GLOBAL_BY_SUITE,
    }
    P0_LICENSE_TABLE=pd.DataFrame([
        {"capability":capability,"suite":suite,**payload[suite]}
        for capability,payload in P0_LICENSE_BY_CAPABILITY.items()
        for suite in ("contemporaneous","temporal") if suite in payload
    ])
    P0_LICENSE_TABLE.to_csv(root/"table_p0_capability_licences.csv",index=False)
    P0_DECISIONS.to_csv(root/"table_p0_harness_qualification.csv",index=False)

    result={"context":context,"fixture_seed":fixture_seed,"p0_seed_summary_rows":len(P0_SEED_SUMMARY),"margins":copy.deepcopy(P0_CALIBRATED_MARGINS),"licences":copy.deepcopy(P0_LICENSE_BY_CAPABILITY),"global_licences":copy.deepcopy(P0_LICENSE),"temporal_property":TEMPORAL_PROPERTY_CLASSIFICATION.to_dict("records"),"identity_failures":list(identity_failures),"p0_decisions":P0_DECISIONS.to_dict("records"),"reference_viability":REFERENCE_VIABILITY.to_dict("records"),"matched_pairs":copy.deepcopy(pairs)}
    save_cp(path,PROTOCOL_HASH,result); return {"protocol_hash":PROTOCOL_HASH,**normalise_json(result)}

def run_p0(context,fixture_seed,frame,times,cards):
    bind_fixture(frame,fixture_seed,context,times); global P0_PROFILE_COLS; P0_PROFILE_COLS=list(FEATURE_SCOPES["all_value_v3"])
    blocks=make_p0_blocks(); _,pairs=match_p0_blocks(blocks); root=PROFILE_ROOT/"tables"/"p0"/context/f"fixture{fixture_seed}"; root.mkdir(parents=True,exist_ok=True); pd.DataFrame(pairs).to_csv(root/"matched_pairs.csv",index=False)
    rows=[]
    for pair in pairs:
        for seed in ACTIVE_PROTOCOL_SEEDS: rows.extend(p0_pair_job(context,fixture_seed,frame,times,blocks,pair,int(seed),cards)["summary_rows"])
    summary=pd.DataFrame(rows); summary.to_csv(root/"p0_seed_summary.csv",index=False); return p0_decision(context,fixture_seed,summary,pairs)
