# All classifier grouping is assigned before row sampling.
def grouped_c2st(real,syn,seed,permutations=None,rows_cap=None,trees=None):
    block=CFG['c2st_block_rows'];trim=math.ceil(25/2)
    ng=min(len(real)//block,len(syn)//block)
    if ng<4:return {'status':'too_few_complete_temporal_groups','AUC':None,'groups':ng,'closeness_resolved':False}
    rng=np.random.default_rng(int(seed));positions=np.arange(ng*block)
    positions=positions[(positions%block>=trim)&(positions%block<block-trim)]
    limit=CFG['c2st_rows_per_class'] if rows_cap is None else rows_cap
    # Sample within each complete group, retaining equal class/group counts.
    per_group=min(block-2*trim,max(1,limit//ng))
    positions=np.concatenate([np.sort(rng.choice(positions[positions//block==g],per_group,replace=False)) for g in range(ng)])
    X=np.vstack([real[positions],syn[positions]]).astype(np.float64)
    y=np.r_[np.zeros(len(positions),int),np.ones(len(positions),int)]
    groups=np.r_[positions//block,positions//block]
    perm_count=CFG['c2st_permutations'] if permutations is None else permutations
    folds=[];rf_values=[];linear_values=[];null_values=[];notes=[]
    for fold in range(CFG['c2st_splits']):
        rr=np.random.default_rng(int(seed)+17*fold);order=rr.permutation(ng);nt=max(1,int(math.ceil(ng*.35)));testgroups=order[:nt]
        test=np.flatnonzero(np.isin(groups,testgroups));train=np.flatnonzero(~np.isin(groups,testgroups))
        assert not set(groups[train])&set(groups[test])
        fold_record={'fold':fold,'train_groups':sorted(set(groups[train].tolist())),'test_groups':sorted(set(groups[test].tolist())),'n_train':len(train),'n_test':len(test),'trim_per_group_edge':trim,'minimum_gap_between_retained_adjacent_groups':2*trim,'train_rows_in_each_class':positions[~np.isin(positions//block,testgroups)].tolist(),'test_rows_in_each_class':positions[np.isin(positions//block,testgroups)].tolist()}
        folds.append(fold_record)
        rf=RandomForestClassifier(n_estimators=trees or CFG['c2st_trees'],max_depth=CFG['c2st_depth'],min_samples_leaf=CFG['c2st_leaf'],class_weight='balanced_subsample',random_state=int(seed)+17*fold,n_jobs=CFG['n_jobs'])
        linear=make_pipeline(StandardScaler(),LogisticRegression(max_iter=300,class_weight='balanced',random_state=int(seed)+101+17*fold))
        for name,m,values in [('RF',rf,rf_values),('linear',linear,linear_values)]:
            with warnings.catch_warnings(record=True) as ws:
                warnings.simplefilter('always');m.fit(X[train],y[train])
            notes.extend([{'model':name,'category':w.category.__name__,'message':str(w.message)} for w in ws])
            auc=float(roc_auc_score(y[test],m.predict_proba(X[test])[:,1]));values.append(max(auc,1-auc))
    # Same conditional label-randomisation diagnostic as the earlier procedure.
    # It is not a calibrated p-value for the maximum of RF and linear statistics.
    for k in range(perm_count):
        rr=np.random.default_rng(int(seed)+1000+k);yp=y.copy()
        for g in range(ng):
            ids=np.flatnonzero(groups==g);yp[ids]=rr.permutation(yp[ids])
        fd=folds[k%len(folds)];tr=np.flatnonzero(np.isin(groups,fd['train_groups']));te=np.flatnonzero(np.isin(groups,fd['test_groups']))
        m=RandomForestClassifier(n_estimators=CFG['c2st_null_trees'],max_depth=CFG['c2st_depth'],min_samples_leaf=CFG['c2st_leaf'],class_weight='balanced_subsample',random_state=int(seed)+1000+k,n_jobs=CFG['n_jobs']).fit(X[tr],yp[tr])
        auc=float(roc_auc_score(yp[te],m.predict_proba(X[te])[:,1]));null_values.append(max(auc,1-auc))
    auc=max(float(np.mean(rf_values)),float(np.mean(linear_values)))
    failed_linear=any(w['category']=='ConvergenceWarning' for w in notes)
    null95=float(np.quantile(null_values,.95)) if null_values else np.nan
    return {'status':'discriminator_did_not_converge' if failed_linear else 'ok','AUC':auc,'RF_AUC':float(np.mean(rf_values)),'linear_AUC':float(np.mean(linear_values)),'RF_fold_AUC':rf_values,'linear_fold_AUC':linear_values,'n_per_class':len(positions),'groups':ng,'folds':folds,'null_AUC':null_values,'null_p95':null95,'excess_over_null_p95':max(0.,auc-null95) if finite(null95) else None,'warnings':notes,'closeness_resolved':not failed_linear and auc<CFG['c2st_ceiling']}


METRIC_TARGETS={'marginal':['marginal_ks_mean','wasserstein_iqr_mean','zero_rate_mae','c2st_max_auc'],'order':['acf_abs_error_mean','spectral_l1_mean','transition_rate_mae'],'coupling':['coupling_corr_mae','coupling_coactivation_mae','c2st_max_auc']}
ENDPOINT_MIN={'marginal_ks_mean':.02,'wasserstein_iqr_mean':.05,'zero_rate_mae':.002,'c2st_max_auc':.02,'acf_abs_error_mean':.01,'spectral_l1_mean':.03,'transition_rate_mae':.0005,'coupling_corr_mae':.02,'coupling_coactivation_mae':.0005}


def instrument_job(fixture_seed,kind,severity):
    base=build_controlled_iot_fixture(CFG['instrument_rows'],fixture_seed)
    cols=[c for c in base if not c.endswith('__nonfinite_mask')]
    other=perturb_fixture(base,kind,severity,fixture_seed+int(100*severity)+len(kind))
    row={'fixture_seed':fixture_seed,'perturbation':kind,'severity':severity}
    row.update(marginal_profile(base,other,cols));row.update(temporal_profile(base,other,cols,lags=[1,5,30,60],max_len=len(base)))
    pairs=[('router__packets','ota24__frames'),('router__packets','iot__power'),('ota24__frames','zigbee__packets'),('iot__state','zigbee__events')]
    row.update(coupling_profile_from_pairs(base,other,pairs))
    if kind in ['marginal','coupling']:
        c=grouped_c2st(base[cols].to_numpy(float),other[cols].to_numpy(float),fixture_seed+int(1000*severity)+len(kind),permutations=9 if severity==0 else 3,rows_cap=6000)
        row.update(c2st_max_auc=c['AUC'],c2st_excess_over_null_p95=c.get('excess_over_null_p95'),c2st_status=c['status'])
    else:c=None
    return {'row':row,'c2st':c}


def run_instruments():
    rows=[]
    for seed in CFG['instrument_seeds']:
        for kind in METRIC_TARGETS:
            for severity in [0.,.25,.5,.75,1.]:
                key={'seed':seed,'kind':kind,'severity':severity}
                r=cached_job('instrument',key,lambda:instrument_job(seed,kind,severity));rows.append(r['row'])
                progress(f'Metric response: fixture {seed}, {kind}, severity {severity:g}.')
    df=pd.DataFrame(rows);agg=df.groupby(['perturbation','severity']).mean(numeric_only=True).reset_index();checks=[]
    for kind,metrics in METRIC_TARGETS.items():
        for name in metrics:
            g=agg[agg.perturbation==kind].sort_values('severity');v=g[name].to_numpy(float)
            rho=float(stats.spearmanr(g.severity,v).statistic);effect=float(v[-1]-v[0])
            complete=bool(np.isfinite(v).all())
            if name=='c2st_max_auc':complete &= bool((df[df.perturbation==kind].c2st_status=='ok').all())
            checks.append({'metric':name,'target':kind,'rho':rho,'endpoint':effect,'rho_min':CFG['instrument_rho'],'endpoint_min':ENDPOINT_MIN[name],'passed':bool(complete and rho>=CFG['instrument_rho'] and effect>ENDPOINT_MIN[name])})
    null=df[(df.severity==0)&df.perturbation.isin(['marginal','coupling'])]
    excess=float(null.c2st_excess_over_null_p95.mean());checks.append({'metric':'c2st_null','target':'same_distribution','endpoint':excess,'passed':bool(np.isfinite(excess) and excess<=CFG['instrument_null_excess'] and (null.c2st_status=='ok').all())})
    table(RUN/'tables'/'instrument_rows.csv',df);table(RUN/'tables'/'instrument_checks.csv',checks)
    return checks
