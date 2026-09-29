# Run each fitted source once, then evaluate the same training output in both periods.
def source_job(regime,source,seed,cards,values,observed):
    a,b=regime['train'];real=values[a:b];realobs=observed[a:b];n=regime['output_rows'];files=[]
    try:
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always');syn,meta=GEN_FUNCS[source](real,n,np.random.default_rng(seed))
        notes=[{'category':w.category.__name__,'message':str(w.message)} for w in ws]
        contract=validate_contract(source,real,syn,meta)
        if source.startswith('learned') and any(w['category']=='ConvergenceWarning' for w in notes):
            contract.update(contract_valid=False,contract_state='Fit-Invalid',reason='generator_fit_did_not_converge')
        fh=feature_health(real,syn)
    except Exception as exc:
        return {'source':source,'seed':seed,'regime':regime['name'],'execution_status':'error','error':repr(exc),'traceback':traceback.format_exc(),'contract':{'contract_valid':False,'contract_state':'Execution-Error'},'utility':[],'c2st':[],'fidelity':[],'feature_health':[]}
    key=f"{regime['name']}__{source}__{seed}"
    rel='arrays/'+key+'__generated.npz';np.savez_compressed(RUN/rel,values=syn);files.append(rel)
    if not np.isfinite(syn).all():
        contract.update(contract_valid=False,contract_state='Fit-Invalid' if source.startswith('learned') else 'Mechanism-Invalid',reason='non-finite generated values')
        utility=[{'source':source,'seed':seed,'regime':regime['name'],'task_id':c['task_id'],'capability':c['capability'],'family':c['family'],'axis':c['axis'],'period':period,'status':'nonfinite_source_output','source_valid':False,'source_state':contract['contract_state']} for c in cards for period in ['near','future']]
        return {'source':source,'seed':seed,'regime':regime['name'],'execution_status':'completed','contract':contract,'generator_metadata':{k:v for k,v in meta.items() if k!='base_block'},'generator_warnings':notes,'feature_health':fh,'utility':utility,'c2st':[],'fidelity':[],'_files':files}
    tests=[]
    for period in ['near','future']:
        t0,t1=regime[period];tests.append({'name':period,'values':values[t0:t1],'observed':observed[t0:t1]})
    utility=[]
    for c in cards:
        rows,ff=paired_task_fit(real,realobs,syn,c,seed,tests,key)
        utility.extend([{**r,'source':source,'seed':seed,'regime':regime['name'],'source_valid':contract['contract_valid'],'source_state':contract['contract_state']} for r in rows]);files+=ff
    crows=[];frows=[]
    for period in ['near','future']:
        t0,t1=regime[period];target=values[t0:t1]
        for i,(scope,cols) in enumerate(C2ST_SCOPES.items()):
            js=[feature_index[c] for c in cols]
            try:
                c=grouped_c2st(target[:,js],syn[:,js],seed+100*i)
            except Exception as exc:
                c={'status':'execution_error','AUC':None,'error':repr(exc),'traceback':traceback.format_exc()}
            crows.append({'source':source,'seed':seed,'regime':regime['name'],'period':period,'scope':scope,**c})
            R=pd.DataFrame(target[:,js],columns=cols);S=pd.DataFrame(syn[:,js],columns=cols)
            m={**marginal_profile(R,S,cols),**temporal_profile(R,S,cols,lags=[1,5,30,60])}
            # All within-scope pairs avoid outcome-selected correlation screening.
            pairs=[(cols[x],cols[y]) for x in range(len(cols)) for y in range(x+1,len(cols))]
            m.update(coupling_profile_from_pairs(R,S,pairs))
            frows.append({'source':source,'seed':seed,'regime':regime['name'],'period':period,'scope':scope,**m})
    metadata={k:v for k,v in meta.items() if k!='base_block'}
    return {'source':source,'seed':seed,'regime':regime['name'],'execution_status':'completed','contract':contract,'generator_metadata':metadata,'generator_warnings':notes,'feature_health':fh,'utility':utility,'c2st':crows,'fidelity':frows,'_files':files}


def seed_interval(values,seed):
    x=np.asarray(values,float);x=x[np.isfinite(x)]
    if not len(x):return {'estimate':None,'lo':None,'hi':None,'n_seeds':0}
    if len(x)<2:return {'estimate':float(np.mean(x)),'lo':None,'hi':None,'n_seeds':len(x)}
    rng=np.random.default_rng(seed);draw=rng.choice(x,(CFG['p0_bootstrap_draws'],len(x)),replace=True).mean(axis=1)
    return {'estimate':float(x.mean()),'lo':float(np.quantile(draw,.025)),'hi':float(np.quantile(draw,.975)),'n_seeds':len(x)}


def metric_gate(checks,metric):
    rows=[r for r in checks if r['metric']==metric]
    return bool(rows and all(r['passed'] for r in rows))


def utility_metric_gate(checks,axis):
    names=['marginal_ks_mean','coupling_corr_mae'] if axis=='contemporaneous' else ['acf_abs_error_mean','spectral_l1_mean','transition_rate_mae']
    return all(metric_gate(checks,n) for n in names)


def permission_for_utility(row,decision,checks):
    if not utility_metric_gate(checks,row['axis']):return 'Instrument-Invalid'
    if decision is None or not decision.get('eligible',False):return 'Not-Estimable'
    if not decision.get('identity_ok',False):return 'Instrument-Invalid'
    if not decision.get('licensed',False):return 'Property-Unlicensed'
    if not row.get('source_valid',False):return row.get('source_state','Source-Invalid')
    if row.get('status')!='ok':return 'Not-Estimable'
    return 'Admissible'


def summaries(regime,records,qualification,checks,cards):
    name=regime['name'];seeds=regime['evaluation_seeds'];dec={(r['axis'],r['capability']):r for r in qualification['decisions']}
    utility=[r for x in records for r in x['utility']]
    for r in utility:r['permission']=permission_for_utility(r,dec.get((r['axis'],r['capability'])),checks)
    u=pd.DataFrame(utility);summ=[];transfer=[];breadth=[]
    for axis in ['contemporaneous','temporal']:
        qs=[q for q in qualification['decisions'] if q['axis']==axis and q['eligible']];passed=sum(q['licensed'] for q in qs)
        breadth.append({'regime':name,'axis':axis,'eligible':len(qs),'licensed':passed,'fraction':passed/len(qs) if qs else None,'suite_claim':bool(passed>=CFG['min_suite_capabilities'] and qs and passed/len(qs)>=CFG['min_suite_fraction'])})
    if not u.empty:
        for (src,axis,cap),g in u.groupby(['source','axis','capability'],sort=True):
            # Keep the same tasks across both periods and every planned seed.
            complete=[]
            for tid,tg in g.groupby('task_id'):
                cells=tg[['seed','period','permission']].drop_duplicates()
                if len(cells)==2*len(seeds) and set(cells.seed)==set(seeds) and set(cells.period)=={'near','future'} and (cells.permission=='Admissible').all():complete.append(tid)
            good=g[g.task_id.isin(complete)]
            for period in ['near','future']:
                gg=good[good.period==period]
                base={'regime':name,'source':src,'axis':axis,'capability':cap,'period':period,'admitted_tasks':g.task_id.nunique(),'common_reportable_tasks':len(complete),'conditional_on_fixed_tasks':True}
                if gg.empty:
                    reasons='|'.join(sorted(set(g.permission)));summ.append({**base,'permission':'Not-Estimable' if reasons=='Admissible' else reasons,'outcome':'not_reportable'});continue
                family=gg.groupby(['seed','family']).log_ratio.median().reset_index();perseed=family.groupby('seed').log_ratio.mean().reindex(seeds)
                skills=gg.groupby(['seed','family']).reference_skill.median().reset_index().groupby('seed').reference_skill.mean().reindex(seeds)
                skill_ci=seed_interval(skills,814)
                base.update(period_reference_skill=skill_ci['estimate'],period_reference_skill_lo=skill_ci['lo'],period_reference_skill_hi=skill_ci['hi'],period_reference_warning=bool(finite(skill_ci['lo']) and skill_ci['lo']<=0))
                ci=seed_interval(perseed,811);ratio=math.exp(ci['estimate']);lo=math.exp(ci['lo']) if finite(ci['lo']) else None;hi=math.exp(ci['hi']) if finite(ci['hi']) else None
                if name!='primary':outcome='descriptive_origin_only'
                elif hi is None:outcome='inconclusive'
                elif hi<=CFG['ni_ratio']:outcome='noninferior'
                elif lo>CFG['ni_ratio']:outcome='inferior'
                else:outcome='inconclusive'
                summ.append({**base,'permission':'Admissible','outcome':outcome,'loss_ratio':ratio,'lo':lo,'hi':hi,'seed_ratios':[float(np.exp(v)) for v in perseed],'n_seeds':ci['n_seeds']})
            if not good.empty:
                pv=good.pivot_table(index=['seed','family','task_id'],columns='period',values='log_ratio',aggfunc='first').dropna();pv['gap']=pv.future-pv.near
                family=pv.reset_index().groupby(['seed','family']).gap.median().reset_index();perseed=family.groupby('seed').gap.mean().reindex(seeds);ci=seed_interval(perseed,812)
                outcome='descriptive_origin_only' if name!='primary' else ('future_worse' if finite(ci['lo']) and ci['lo']>0 else ('future_better' if finite(ci['hi']) and ci['hi']<0 else 'inconclusive'))
                transfer.append({'regime':name,'source':src,'axis':axis,'capability':cap,'common_tasks':len(complete),'permission':'Admissible','outcome':outcome,**ci,'interpretation':'Change in synthetic/real loss ratio. Not a causal estimate of drift.'})
    # Anchor-relative C2ST. Both the scope's P0 and candidate/anchor must resolve.
    crows=[];allc=[{**r,'source_valid':x['contract'].get('contract_valid',False)} for x in records for r in x['c2st']]
    cf=pd.DataFrame(allc);p0=pd.DataFrame(qualification['c2st'])
    if not cf.empty:
        for (src,period,scope),g in cf.groupby(['source','period','scope'],sort=True):
            anchor=cf[(cf.source=='real_row_resample')&(cf.period==period)&(cf.scope==scope)]
            paired=g.merge(anchor[['seed','AUC','status','source_valid']],on='seed',suffixes=('','_anchor'))
            pp=p0[p0.scope==scope] if not p0.empty else pd.DataFrame()
            p0ok=len(pp)==10 and (pp.status=='ok').all() and pd.to_numeric(pp.AUC,errors='coerce').notna().all()
            measured=len(paired)==len(seeds) and (paired.status=='ok').all() and (paired.status_anchor=='ok').all()
            sourceok=measured and paired.source_valid.all() and paired.source_valid_anchor.all()
            metricok=metric_gate(checks,'c2st_max_auc') and metric_gate(checks,'c2st_null')
            ci=seed_interval(paired.AUC-paired.AUC_anchor,813) if measured else {'estimate':None,'lo':None,'hi':None,'n_seeds':0}
            primary_resolution=bool(sourceok and metricok and p0ok and pp.AUC.max()<CFG['c2st_ceiling'] and max(paired.AUC.max(),paired.AUC_anchor.max())<CFG['c2st_ceiling'])
            secondary=bool(primary_resolution and pp.AUC.max()<.9945 and max(paired.AUC.max(),paired.AUC_anchor.max())<.9945)
            direction='diagnostic_only'
            if sourceok and metricok:
                if name!='primary':direction='descriptive_origin_only'
                elif finite(ci['lo']) and ci['lo']>0:direction='more_distinguishable_than_anchor'
                elif finite(ci['hi']) and ci['hi']<0:direction='less_distinguishable_than_anchor'
                else:direction='direction_inconclusive'
            crows.append({'regime':name,'source':src,'period':period,'scope':scope,'direction':direction,'resolution_available':primary_resolution,'secondary_resolution_available':secondary,'closeness_outcome':'not_tested_as_equivalence' if primary_resolution else 'Not-Estimable','P0_max_AUC':float(pp.AUC.max()) if p0ok else None,'candidate_max_AUC':float(paired.AUC.max()) if measured else None,'anchor_max_AUC':float(paired.AUC_anchor.max()) if measured else None,'excess_AUC':ci['estimate'],'excess_lo':ci['lo'],'excess_hi':ci['hi'],'n_seeds':ci['n_seeds']})
    for tag,rows in [('utility_rows',utility),('utility_summary',summ),('transfer_summary',transfer),('suite_breadth',breadth),('C2ST_summary',crows)]:table(RUN/'tables'/f'{name}_{tag}.csv',rows)
    return {'utility':utility,'summary':summ,'transfer':transfer,'breadth':breadth,'c2st':crows}


def run_external(values_df,observed,seconds,data_hashes):
    global VALUE_FEATURES,feature_index,LEARNED_SCOPE,C2ST_SCOPES
    VALUE_FEATURES=list(values_df);feature_index={c:i for i,c in enumerate(VALUE_FEATURES)}
    LEARNED_SCOPE=ASSETS['external']['generators']['learned_scope'];C2ST_SCOPES=ASSETS['external']['c2st']['scopes']
    values=values_df.to_numpy(float);regimes=plan_regimes(len(values),ASSETS['external']);initialise_run(data_hashes,regimes)
    table(RUN/'tables'/'observed_input_fraction.csv',[{'feature':c,'observed_fraction':float(observed[:,i].mean()),'training_observed_fraction':float(observed[:regimes[0]['train'][1],i].mean())} for i,c in enumerate(VALUE_FEATURES)])
    checks=run_instruments();all_results={};all_sources=[]
    for regime in regimes:
        ad=cached_job('task_admission',{'regime':regime},lambda:admission(regime,values,observed))
        freeze_json(RUN/'selection'/f"{regime['name']}_tasks.json",ad)
        table(RUN/'tables'/f"{regime['name']}_task_admission.csv",ad['rows'])
        cards=ad['cards'];progress(f"{regime['name']}: {len(cards)}/{ad['prior_template_count']} prior templates pass current TRAIN-only admission.")
        qual=run_qualification(regime,cards,values,observed,seconds)
        records=[]
        for source in SOURCES:
            for seed in regime['evaluation_seeds']:
                key={'regime':regime,'source':source,'seed':seed,'cards_hash':digest(cards)}
                result=cached_job('sources',key,lambda:source_job(regime,source,seed,cards,values,observed));records.append(result)
                progress(f"{regime['name']} / {source} / {seed}: {result['contract']['contract_state']}.")
        summary=summaries(regime,records,qual,checks,cards)
        all_results[regime['name']]={'qualification':qual,'results':summary,'admitted_tasks':len(cards)};all_sources+=records
        atomic_json(RUN/'progress.json',{'completed_regimes':list(all_results),'source_jobs_completed':len(all_sources),'publication_claims_not_automatically_updated':True})
    source_rows=[];health=[];fidelity=[]
    for x in all_sources:
        source_rows.append({'regime':x['regime'],'source':x['source'],'seed':x['seed'],'execution_status':x['execution_status'],**x['contract'],'warnings':x.get('generator_warnings',[]),'error':x.get('error')})
        health.extend([{'regime':x['regime'],'source':x['source'],'seed':x['seed'],**r} for r in x['feature_health']])
        for r in x['fidelity']:
            for metric in ENDPOINT_MIN:
                if metric=='c2st_max_auc' or metric not in r:continue
                fidelity.append({**{k:r[k] for k in ['regime','source','seed','period','scope']},'metric':metric,'value':r[metric],'metric_qualified':metric_gate(checks,metric),'source_valid':x['contract'].get('contract_valid',False),'interpretation':'Property-specific diagnostic. A favourable value alone does not establish overall similarity.'})
    table(RUN/'tables'/'source_checks.csv',source_rows);table(RUN/'tables'/'feature_checks.csv',health);table(RUN/'tables'/'fidelity.csv',fidelity);table(RUN/'tables'/'execution.csv',EXECUTION_RECORDS)
    errors=[x for x in source_rows if x['execution_status']=='error']
    task_errors=sum(r.get('status')=='execution_error' for x in all_sources for r in x['utility'])+sum(r.get('status')=='execution_error' for x in all_results.values() for r in x['qualification']['rows'])
    classifier_errors=sum(r.get('status')=='execution_error' for x in all_sources for r in x['c2st'])
    report={'status':'COMPLETED_WITH_EXECUTION_ERRORS' if errors or task_errors or classifier_errors else 'PLANNED_JOBS_COMPLETED','planned_source_jobs':len(SOURCES)*(len(CFG['seeds'])+3),'source_jobs_completed':len(source_rows),'source_execution_errors':len(errors),'task_execution_errors':task_errors,'classifier_execution_errors':classifier_errors,'primary_task_count':all_results['primary']['admitted_tasks'],'metric_checks_passed':sum(x['passed'] for x in checks),'metric_checks_total':len(checks),'final_procedure_applied':True,'independent_confirmation':False,'conditional_seed_intervals':'Fixed task registry. Five seeds do not establish population-level coverage.','limitations_remaining':['Earlier TON_IoT and task-template exposure','One residential home','No independently designed new benchmark','Simple generators on different bases','No privacy or generated-observability qualification','Historical date-repair rule remains outside these supplied inputs']}
    atomic_json(RUN/'run_status.json',report)
    make_plots(all_results)
    return all_results,report


def make_plots(all_results):
    primary=all_results['primary']['results'];u=pd.DataFrame(primary['summary'])
    if u.empty or 'loss_ratio' not in u:return
    show=u[(u.period=='future')&(u.permission=='Admissible')].copy()
    if show.empty:return
    labels=[r.source+' / '+r.capability for r in show.itertuples()]
    fig,ax=plt.subplots(figsize=(8,max(3,.30*len(show))));y=np.arange(len(show));v=show.loss_ratio.to_numpy(float)
    lo=pd.to_numeric(show.lo,errors='coerce').to_numpy();hi=pd.to_numeric(show.hi,errors='coerce').to_numpy()
    ax.errorbar(v,y,xerr=np.vstack([np.maximum(0,v-lo),np.maximum(0,hi-v)]),fmt='o',color='.20',ecolor='.50',capsize=2)
    ax.axvline(1,color='.5',linestyle='--');ax.axvline(1.1,color='.5',linestyle=':');ax.set_xscale('log');ax.set_yticks(y,labels,fontsize=8);ax.invert_yaxis();ax.set_xlabel('Future-period synthetic / real loss. Conditional 95% seed intervals.');fig.tight_layout()
    fig.savefig(RUN/'figures'/'future_utility.pdf');fig.savefig(RUN/'figures'/'future_utility.png',dpi=180);plt.close(fig)


def export_results(report=None,error=None):
    # The review ZIP contains all scalar/check records and code/protocol identifiers.
    # Large prediction arrays stay local and have a separate manifest.
    if 'RUN' in globals():
        atomic_json(RUN/'delivery_status.json',{'report':report,'error':error,'raw_recordings_included':False,'prediction_arrays_included_in_review_zip':False})
        table(RUN/'tables'/'execution.csv',globals().get('EXECUTION_RECORDS',[]))
        files=[]
        for p in sorted(RUN.rglob('*')):
            if p.is_file():files.append({'path':str(p.relative_to(RUN)),'bytes':p.stat().st_size,'sha256':file_hash(p)})
        table(RUN/'result_file_manifest.csv',files)
    dest=OUTPUT_ROOT/'TIOT_ADDITIONAL_RESULTS_TO_SHARE.zip'
    temporary=dest.with_suffix('.tmp.zip')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
        res=OUTPUT_ROOT/'residential_matching'
        if res.exists():
            for p in sorted(res.rglob('*')):
                if p.is_file():z.write(p,str(p.relative_to(OUTPUT_ROOT)))
        if 'RUN' in globals():
            for p in sorted(RUN.rglob('*')):
                if p.is_file() and 'arrays' not in p.relative_to(RUN).parts:z.write(p,str(p.relative_to(OUTPUT_ROOT)))
        guide='This ZIP contains the residential matching audit, fixed protocol, all saved scalar results, job records, C2ST split indices, selection records, plots, and file hashes. Predictions and synthetic arrays remain in the local arrays directory. No raw input recording is included. This is a corrected evaluation on previously examined data, not independent confirmation. Scientific failures are valid results. Do not change thresholds to obtain passes.'
        z.writestr('READ_ME.txt',guide)
    temporary.replace(dest);progress('Share this file: '+str(dest));return dest
