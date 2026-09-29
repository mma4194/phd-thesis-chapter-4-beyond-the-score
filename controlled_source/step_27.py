
# ============================================================
# 17. Operating statistics, crossed bootstrap and confusion matrix
# ============================================================
STATES=["INSTRUMENT_INVALID","NOT_ESTIMABLE","PROPERTY_UNLICENSED","SOURCE_INVALID","FIT_INVALID","ADMISSIBLE"]
def crossed_ci(frame,column,draws,seed=24001):
    p=frame.pivot_table(index="scenario_id",columns="fixture_seed",values=column,aggfunc="mean").to_numpy(float)
    if not p.size:return np.nan,np.nan,np.nan
    est=float(np.nanmean(p)); rng=np.random.default_rng(seed); vals=[]; ns,nf=p.shape
    for _ in range(int(draws)):
        x=p[rng.integers(0,ns,ns)[:,None],rng.integers(0,nf,nf)[None,:]]
        if np.isfinite(x).any(): vals.append(float(np.nanmean(x)))
    return est,float(np.quantile(vals,.025)) if vals else np.nan,float(np.quantile(vals,.975)) if vals else np.nan

def add_metric_values(g,metric):
    x=g.copy(); exp=x.expected_permission.eq("ADMISSIBLE")
    if metric=="exact_permission_accuracy": x["_v"]=x.permission_correct.astype(float)
    elif metric=="full_label_accuracy": x["_v"]=x.full_label_correct.astype(float)
    elif metric=="false_admission_rate": x=x[~exp].copy(); x["_v"]=x.observed_permission.eq("ADMISSIBLE").astype(float)
    elif metric=="false_rejection_rate": x=x[exp].copy(); x["_v"]=(~x.observed_permission.eq("ADMISSIBLE")).astype(float)
    elif metric=="stage_localisation_accuracy": x=x[~exp].copy(); x["_v"]=x.failure_stage_correct.astype(float)
    elif metric=="mixed_failure_precedence_accuracy": x=x[x.mixed_failure.astype(bool)].copy(); x["_v"]=x.permission_correct.astype(float)
    else: raise ValueError(metric)
    return x
metrics=["exact_permission_accuracy","full_label_accuracy","false_admission_rate","false_rejection_rate","stage_localisation_accuracy","mixed_failure_precedence_accuracy"]
summary=[]
for ablation,g in ABLATION_RESULTS.groupby("ablation",sort=False):
    row={"ablation":ablation,"n_units":len(g),"n_scenarios":g.scenario_id.nunique(),"n_fixture_replicates":g.fixture_seed.nunique()}
    for m in metrics:
        x=add_metric_values(g,m); est,lo,hi=crossed_ci(x,"_v",BOOTSTRAP_DRAWS) if len(x) else (np.nan,np.nan,np.nan); row[m+"_estimate"]=est; row[m+"_ci_lo"]=lo; row[m+"_ci_hi"]=hi
    summary.append(row)
ABLATION_SUMMARY=pd.DataFrame(summary); ABLATION_SUMMARY.to_csv(PROFILE_ROOT/"tables"/"stage_ablation_summary.csv",index=False); display(ABLATION_SUMMARY)
full=ABLATION_RESULTS[ABLATION_RESULTS.ablation=="FULL"].copy()
CONFUSION=pd.crosstab(pd.Categorical(full.expected_permission,categories=STATES),pd.Categorical(full.observed_permission,categories=STATES),dropna=False).reindex(index=STATES,columns=STATES,fill_value=0); CONFUSION.index.name="expected_permission"; CONFUSION.columns.name="observed_permission"; CONFUSION.to_csv(PROFILE_ROOT/"tables"/"terminal_state_confusion.csv"); display(CONFUSION)
FAILURES=full[~full.full_label_correct.astype(bool)].copy(); FAILURES.to_csv(PROFILE_ROOT/"tables"/"failure_case_audit.csv",index=False); display(FAILURES)
