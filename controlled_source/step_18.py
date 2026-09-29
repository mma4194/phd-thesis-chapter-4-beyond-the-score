
# ============================================================
# 11. Source constructors and contracts
# ============================================================
def role_anchor(train,suite,n,seed,columns): return real_block_generator(train,n,seed,columns,{}) if suite=="temporal" else real_resample_generator(train,n,seed,columns,{})
def jitter(base,train,columns,sigma,seed):
    rng=np.random.default_rng(seed); out=base[list(columns)].copy().reset_index(drop=True)
    for c in columns:
        if c.endswith("__nonfinite_mask"): continue
        finite=train[c].to_numpy(float); finite=finite[np.isfinite(finite)]
        if len(finite)<20: continue
        sup=infer_column_support(finite); scale=robust_iqr(finite)
        if sup["binary"] or sup["integer_like"] or scale<=1e-9: continue
        out[c]=out[c].to_numpy(float)+rng.normal(0,float(sigma)*scale,len(out))
    return project_frame_to_train_support(out,train[list(columns)],columns)
def float_digest(v): return hashlib.sha256(np.sort(np.asarray(v,dtype=np.float32),axis=None).tobytes()).hexdigest()

def construct_source(s,train,seed):
    columns=list(FEATURE_SCOPES["generator_v2"]); n=min(int(CFG["generation_rows"]),len(train)); suite=s["suite"]; kind=s["source_kind"]; sev=float(s["core_severity"])
    base=role_anchor(train,suite,n,seed,columns); meta={"source_kind":kind,"severity":sev,"base_role":"real_block" if suite=="temporal" else "real_resample"}
    if kind=="identity_anchor": source=base.copy(); family="kt_real_anchor"; order=suite=="temporal"
    elif kind=="mild_jitter": source=jitter(base,train,columns,sev,seed+10000); family="kt_transparent_positive"; order=suite=="temporal"
    elif kind=="column_shuffle":
        source=column_shuffle_generator(train,n,seed,columns,{}); family="kt_column_shuffle"; order=False; meta["base_sample"]=sample_rows(train[columns],n,seed)
    elif kind=="support_violation":
        source=base.copy(); c="iot__power"; count=max(1,int(round(sev*len(source)))); high=float(train[c].max()+25*max(robust_iqr(train[c]),1)); source.loc[np.arange(count),c]=high; family="kt_transparent_invalid"; order=suite=="temporal"; meta.update({"violated_column":c,"violated_rows":count,"planted_fraction":count/len(source)})
    elif kind=="learned_collapse":
        source=base.copy(); values=list(FEATURE_SCOPES["all_value_v3"]); count=max(1,int(round(sev*len(values)))); collapsed=values[:count]
        for c in collapsed: source[c]=float(np.median(train[c]))
        family="learned_known_truth_collapse"; order=suite=="temporal"; meta["collapsed_columns"]=collapsed
    elif kind=="learned_activity":
        source=base.copy(); rng=np.random.default_rng(seed+70000)
        for c in FEATURE_SCOPES["all_value_v3"]:
            count=int(round(sev*len(source)))
            if count:
                idx=rng.choice(len(source),count,replace=False); v=source[c].to_numpy(float,copy=True); v[idx]=0; source[c]=v
        family="learned_known_truth_activity"; order=suite=="temporal"; meta["zeroed_fraction_per_feature"]=sev
    else: raise ValueError(kind)
    spec=GeneratorSpec(f"{s['scenario_id']}__{kind}",family,"known_truth",order,False,False,{"scenario_id":s["scenario_id"],"source_kind":kind,"severity":sev})
    return source,spec,meta

def source_contract(s,spec,train,source,meta):
    try: health=generator_output_health(spec,train,source)
    except ScientificInvalidFit as exc:
        d=getattr(exc,"diagnostics",{}); return {"source_valid":False,"failure_type":"FIT_INVALID","failed_predicates":d.get("failed_predicates",[]),"reason":str(exc),"health":d}
    kind=s["source_kind"]; failed=[]
    if not health.get("finite",False): failed.append("nonfinite_output")
    if float(health.get("unsupported_value_fraction",np.inf))>1e-4: failed.append("empirical_support_violation")
    if kind=="column_shuffle":
        base=meta["base_sample"]
        for c in FEATURE_SCOPES["generator_v2"]:
            if float_digest(base[c])!=float_digest(source[c]): failed.append(f"column_multiset_changed:{c}"); break
            if not np.isclose(float(np.mean(base[c].to_numpy(float)==0)),float(np.mean(source[c].to_numpy(float)==0)),rtol=0,atol=0): failed.append(f"zero_rate_changed:{c}"); break
    if kind in {"mild_jitter","support_violation"} and float(health.get("variable_feature_fraction_among_real_variable",0))<BASE_CFG["learned_min_modeled_variable_fraction"]: failed.append("variation_collapse")
    return {"source_valid":not failed,"failure_type":"SOURCE_INVALID" if failed else "","failed_predicates":failed,"reason":"; ".join(failed),"health":health}
