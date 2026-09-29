GENERATOR_FUNCTIONS={'real_resample':real_resample_generator,'real_block':real_block_generator,'independent_marginal':independent_marginal_generator,'column_shuffle':column_shuffle_generator,'hurdle_iid':hurdle_rank_stitch_generator,'hurdle_independent_stitch':hurdle_rank_stitch_generator,'hurdle_shared_stitch':hurdle_rank_stitch_generator,'learned_gmm_overlay':learned_gmm_overlay_generator,'learned_latent_var_overlay':learned_latent_var_overlay_generator}

def source_health(train_raw,train_finite,out,source,fit_notes):
    rows=[];scope=LEARNED_MODEL_COLS if source.startswith('learned_') else VALUE_COLS
    for c in scope:
        if c not in out:continue
        a=train_raw[c].to_numpy(float);b=out[c].to_numpy(float);oa=observed(train_raw,c);ob=observed(out,c);a=a[oa];b=b[ob]
        if not len(a) or not len(b):rows.append({'feature':c,'observed_comparison':False,'train_observed':len(a),'generated_observed':len(b)});continue
        info=infer_column_support(a);bad=(b<a.min())|(b>a.max())
        unique=np.unique(a)
        if len(unique)<=32:bad |= ~np.isin(b,unique)
        rows.append({'feature':c,'observed_comparison':True,'train_observed':len(a),'generated_observed':len(b),'real_variable':bool(np.ptp(a)>0),'generated_variable':bool(np.ptp(b)>0),'support_violation_fraction':float(bad.mean()),'activity_error':abs(float((a!=0).mean())-float((b!=0).mean())),'missing_fraction_error':abs(float(oa.mean())-float(ob.mean())),'observed_KS':float(ks_2samp(a[deterministic_subsample_indices(len(a),50000)],b[deterministic_subsample_indices(len(b),50000)]).statistic)})
    good=[r for r in rows if r['observed_comparison']];variable=[r for r in good if r['real_variable']]
    frac=sum(r['generated_variable'] for r in variable)/len(variable) if variable else None
    errors=np.array([r['activity_error'] for r in good]);support=max((r['support_violation_fraction'] for r in good),default=1.)
    finite_output=bool(np.isfinite(out.to_numpy()).all())
    mask_valid=all(np.isin(out[c].to_numpy(),[0.,1.]).all() for c in REVERSE_MASK if c in out)
    warning_invalid=any(x['category']=='ConvergenceWarning' for x in fit_notes)
    valid=finite_output and mask_valid and support<=1e-4 and not warning_invalid
    if source.startswith('learned_'):
        valid=bool(valid and len(good)==len(scope) and frac is not None and frac>=CFG['learned_min_modeled_variable_fraction'] and len(errors) and errors.mean()<=CFG['learned_max_zero_rate_mae'] and np.quantile(errors,.95)<=CFG['learned_zero_rate_p95_max'] and errors.max()<=CFG['learned_zero_rate_feature_max'])
    return {'source_valid':bool(valid),'finite_output':finite_output,'binary_masks':bool(mask_valid),'scope':scope,'variable_fraction':frac,'max_support_violation':support,'activity_mean':float(errors.mean()) if len(errors) else None,'activity_p95':float(np.quantile(errors,.95)) if len(errors) else None,'activity_max':float(errors.max()) if len(errors) else None,'observed_scope_coverage':len(good),'scope_size':len(scope),'fit_warnings':fit_notes,'generator_metadata':out.attrs.get('health',{}),'features':rows,'interpretation':'Checks concern the corrected preparation. Retained source settings do not make these the original fitted outputs.'}

def generation_inputs(train):
    cols=list(COLS);values={};rows=[]
    for c in cols:
        x=train[c].to_numpy(float);ok=observed(train,c);med=float(np.median(x[ok])) if ok.any() else 0.
        # Existing observation masks retain their binary meaning. Missing sensor values remain represented by them.
        values[c]=np.where(ok,x,med).astype(np.float32)
        rows.append({'feature':c,'replacement':med,'missing':int((~ok).sum()),'all_missing':bool(not ok.any()),'rule':'fit-prefix median with separate observation mask'})
    return pd.DataFrame(values),rows

def frame_digest(frame):
    h=hashlib.sha256()
    h.update(json.dumps({'shape':frame.shape,'columns':list(frame.columns)},sort_keys=True).encode())
    for c in frame.columns:
        h.update(np.ascontiguousarray(frame[c].to_numpy(dtype=np.float32)).tobytes())
    return h.hexdigest()

def ensure_source(source,seed,arm,train,prepared,params):
    key={'source':source,'seed':seed,'period':arm,'params':params,'columns':COLS}
    root=RUN/'_local_cache'/'sources';root.mkdir(parents=True,exist_ok=True);mp=root/(dh(key)+'.json')
    previous=None
    if mp.exists():
        previous=json.loads(mp.read_text())
        if previous['protocol']!=PROTOCOL_HASH or previous['key']!=clean(key):raise RuntimeError('Source checkpoint identity differs.')
        if previous['status']!='ok':
            save_json(RUN/'source_checks'/f'{arm}_{source}_{seed}.json',previous)
            return None,previous
    try:
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always');out=GENERATOR_FUNCTIONS[source](prepared,CFG['generation_rows'],seed,COLS,params)
        notes=[{'category':w.category.__name__,'message':str(w.message)} for w in ws]
        if list(out.columns)!=list(COLS) or len(out)!=CFG['generation_rows']:raise RuntimeError('Unexpected generated shape or column order.')
        digest=frame_digest(out)
        if previous is not None and previous['sha256']!=digest:raise RuntimeError('Regenerated source differs from its saved value hash. Do not combine its checkpoints.')
        health=source_health(train,prepared,out,source,notes)
        result={'protocol':PROTOCOL_HASH,'key':key,'status':'ok','sha256':digest,'hash_kind':'float32 numerical values in column order','storage':'RAM only','health':health}
    except ScientificInvalidFit as e:
        result={'protocol':PROTOCOL_HASH,'key':key,'status':'Fit-Invalid','message':str(e),'diagnostics':e.diagnostics,'health':{'source_valid':False}};out=None
    save_json(mp,result);save_json(RUN/'source_checks'/f'{arm}_{source}_{seed}.json',result);return out,result


def utility_card(train,synthetic,test,card,seed,source,arm,source_valid):
    segments=None
    if source in {'real_block','hurdle_independent_stitch','hurdle_shared_stitch','learned_latent_var_overlay'}:
        segments=np.arange(len(synthetic))//block_length_for_output(len(synthetic))
    X,y,a=task_arrays(train,card.task,CFG['row_cap_task_train'])
    S,z,b=task_arrays(synthetic,card.task,CFG['row_cap_task_train'],segments)
    T,w,c=task_arrays(test,card.task,CFG['row_cap_task_test'])
    n=min(len(y),len(z));base={'source':source,'period':arm,'seed':seed,'card_id':card.card_id,'model_id':card.model_id,'suite':card.task.suite,'capability':card.task.capability,'task_family':card.task.family,'target':card.task.target,'n_train':n,'n_reference_train':n,'n_test':len(w),'source_valid':source_valid,'train_audit':a,'synthetic_audit':b,'test_audit':c,'unobserved_target_contexts_used':0}
    if n<300:return {**base,'status':'too_few_observed_training_contexts'}
    ix=deterministic_subsample_indices(len(y),n);iz=deterministic_subsample_indices(len(z),n);X=X.iloc[ix];y=y.iloc[ix];S=S.iloc[iz];z=z.iloc[iz]
    def reference_result():
        ref,hr=fit_model_checked(X,y,card,seed)
        return {'fit':hr,'score':score_model(ref,y,T,w,card) if ref is not None else hr}
    reference=cache('utility_real_reference',{'period':arm,'seed':seed,'card':card.key(),'n_train':n},reference_result)
    hr=reference['fit'];dr=reference['score'];syn,hs=fit_model_checked(S,z,card,seed)
    if hr['status']!='ok' or syn is None:return {**base,'status':'model_unavailable','reference_health':hr,'synthetic_health':hs}
    ds=score_model(syn,z,T,w,card)
    if dr['status']!='ok' or ds['status']!='ok':return {**base,'status':'loss_unavailable','reference_result':dr,'synthetic_result':ds}
    L=dr['loss'];N=dr['naive_loss'];V=ds['loss'];out={**base,'reference_loss':L,'synthetic_loss':V,'naive_loss':N,'reference_skill':(N-L)/max(N,1e-12),'reference_fit':hr,'synthetic_fit':hs}
    if card.task.task_type=='regression':
        scale=dr['target_iqr_test'];out.update(target_IQR=scale,reference_MAE=L*scale,synthetic_MAE=V*scale,naive_MAE=N*scale)
    if L<CFG['min_reference_loss'] or N<=0:return {**out,'status':'unusable_reference'}
    return {**out,'status':'ok','loss_ratio':V/L,'log_loss_ratio':float(np.log(max(V/L,1e-12))),'perfect_synthetic_loss':V==0}

def run_utility(raw,admitted,qualification):
    eligible=qualification[qualification.clipped & qualification.final_rule_licensed]
    scopes={(r.suite,r.capability) for r in eligible.itertuples()}
    # Include every passing scope from every matching arm. Selection uses corrected VAL and TRAIN P0, never utility outcomes.
    selected=[c for c in ALL_CARDS if c.card_id in admitted and (c.task.suite,c.task.capability) in scopes]
    save_json(RUN/'utility_scope_frozen_before_TEST.json',{'card_ids':[c.card_id for c in selected],'scopes':sorted(scopes),'rule':'Union of corrected TRAIN-P0 passing scopes, restricted to corrected VAL-admitted historical cards','primary_matching':'balanced_observed'})
    if not selected:
        save_json(RUN/'utility_status.json',{'status':'no_qualified_scope','message':'No qualified prediction scope. No generator performance claim is made.'});return pd.DataFrame()
    sources=ASSETS['generator_registry']['generators'];rows=[];source_rows=[]
    for arm,fitlo,fithi,testlo,testhi in [('same_period',SPLIT['inner_fit_start'],SPLIT['inner_fit_end'],SPLIT['inner_calib_start'],SPLIT['inner_calib_end']),('future',SPLIT['train_start'],SPLIT['train_end'],SPLIT['test_start'],SPLIT['test_end'])]:
        train=raw.iloc[fitlo:fithi];test=raw.iloc[testlo:testhi];prepared,imputation=generation_inputs(train);save_csv(RUN/f'{arm}_generator_imputation.csv',imputation)
        for spec in sources:
            source=spec['generator_id']
            for seed in CFG['seeds']:
                msg(f'Prediction check: {arm}, {source}, seed {seed}.')
                source_key={'source':source,'seed':seed,'period':arm,'params':spec['params'],'columns':COLS}
                local_meta=RUN/'_local_cache'/'sources'/(dh(source_key)+'.json')
                cached_rows=None
                if local_meta.exists():
                    meta=json.loads(local_meta.read_text())
                    if meta['status']=='ok' and meta.get('protocol')==PROTOCOL_HASH:
                        kk=[{'source':source,'seed':seed,'period':arm,'card':c.key(),'source_hash':meta['sha256']} for c in selected]
                        if all((RUN/'jobs'/'corrected_utility'/(dh(k)+'.json')).exists() for k in kk):
                            cached_rows=[cache('corrected_utility',k,lambda:(_ for _ in ()).throw(RuntimeError('Missing completed result'))) for k in kk]
                            rows+=cached_rows;source_rows.append({'source':source,'period':arm,'seed':seed,'status':meta['status'],'source_valid':meta['health']['source_valid']})
                            save_json(RUN/'source_checks'/f'{arm}_{source}_{seed}.json',meta)
                            continue
                syn,status=ensure_source(source,seed,arm,train,prepared,spec['params']);valid=status['health']['source_valid'];source_rows.append({'source':source,'period':arm,'seed':seed,'status':status['status'],'source_valid':valid})
                if syn is None:
                    rows += [{'source':source,'period':arm,'seed':seed,'card_id':c.card_id,'model_id':c.model_id,'suite':c.task.suite,'capability':c.task.capability,'task_family':c.task.family,'target':c.task.target,'status':'source_fit_unavailable','source_valid':False} for c in selected];continue
                for j,c in enumerate(selected):
                    key={'source':source,'seed':seed,'period':arm,'card':c.key(),'source_hash':status['sha256']}
                    rows.append(cache('corrected_utility',key,lambda:utility_card(train,syn,test,c,seed,source,arm,valid)))
                    if (j+1)%10==0:msg(f'  Task models {j+1}/{len(selected)}.')
                del syn;gc.collect()
                # Only compact loss and source-health checkpoints are written to disk.
        del prepared;gc.collect()
    save_csv(RUN/'utility_losses.csv',rows);save_json(RUN/'utility_losses.json',rows);save_csv(RUN/'source_status.csv',source_rows)
    return pd.DataFrame(rows)

def paired_seed_interval(values,seed=901):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    if not len(a):return {'estimate':None,'lo':None,'hi':None,'n_seeds':0}
    rng=np.random.default_rng(seed);means=np.mean(a[rng.integers(0,len(a),size=(CFG['p0_bootstrap_draws'],len(a)))],axis=1)
    return {'estimate':float(a.mean()),'lo':float(np.quantile(means,.025)),'hi':float(np.quantile(means,.975)),'n_seeds':len(a)}

def balanced_seed_values(rows,value):
    fam=rows.groupby(['seed','capability','task_family'])[value].mean();cap=fam.groupby(['seed','capability']).mean();return cap.groupby('seed').mean()

def summarise_utility(losses,q,admitted):
    if losses.empty:return pd.DataFrame(),pd.DataFrame()
    expected=set(CFG['seeds']);summ=[];gaps=[];complete_cards=[]
    for arm in sorted(q.arm.unique()):
        passed={(r.suite,r.capability) for r in q[(q.arm==arm)&q.clipped&q.final_rule_licensed].itertuples()}
        for source in [s['generator_id'] for s in ASSETS['generator_registry']['generators']]:
            for suite in ['contemporaneous','temporal']:
                caps={c for s,c in passed if s==suite};desired=[c for c in ALL_CARDS if c.card_id in admitted and c.task.suite==suite and c.task.capability in caps]
                if not desired:continue
                sub=losses[(losses.source==source)&(losses.suite==suite)&losses.card_id.isin([c.card_id for c in desired])]
                # Same cards across all seeds and periods. Missing cards remain a reported coverage loss.
                keep=[]
                for cid,cc in sub.groupby('card_id'):
                    good=cc[(cc.status=='ok') & cc.source_valid.fillna(False)]
                    if len(good)==2*len(expected) and set(good.seed)==expected and set(good.period)=={'same_period','future'}:keep.append(cid)
                supported=sub[sub.card_id.isin(keep)&(sub.status=='ok')&sub.source_valid.fillna(False)]
                covered=set(supported.capability) if len(supported) else set();full=covered==caps and len(keep)==len(desired)
                complete_cards.append({'matching':arm,'source':source,'suite':suite,'expected_cards':len(desired),'complete_cards':len(keep),'expected_capabilities':len(caps),'covered_capabilities':len(covered),'complete_support':full})
                for period in ['same_period','future']:
                    x=supported[supported.period==period];v=balanced_seed_values(x,'log_loss_ratio') if len(x) else pd.Series(dtype=float);ci=paired_seed_interval(v)
                    lo=math.exp(ci['lo']) if ci['lo'] is not None else None;hi=math.exp(ci['hi']) if ci['hi'] is not None else None
                    skill_ci=paired_seed_interval(balanced_seed_values(x,'reference_skill')) if len(x) else paired_seed_interval([])
                    reference_usable=bool(skill_ci['lo'] is not None and skill_ci['lo']>0)
                    state=('Noninferior' if hi<=CFG['utility_noninferiority_ratio'] else 'Inferior' if lo>CFG['utility_noninferiority_ratio'] else 'Inconclusive') if full and reference_usable and lo is not None else ('Reference-not-useful' if full and not reference_usable else 'Not-Estimable')
                    summ.append({'matching':arm,'source':source,'suite':suite,'period':period,'capabilities':sorted(caps),'complete_cards':len(keep),'expected_cards':len(desired),'complete_support':full,'n_seeds':ci['n_seeds'],'real_reference_skill':skill_ci['estimate'],'real_reference_skill_lo':skill_ci['lo'],'real_reference_skill_hi':skill_ci['hi'],'reference_usable_in_period':reference_usable,'loss_ratio':math.exp(ci['estimate']) if ci['estimate'] is not None else None,'ci_lo':lo,'ci_hi':hi,'outcome':state,'scope_status':'primary corrected scope' if arm=='balanced_observed' else 'matching sensitivity','uncertainty':'seed bootstrap with fixed family/capability-balanced card collection'})
                if len(supported):
                    piv=supported.pivot(index=['seed','capability','task_family','card_id'],columns='period',values='log_loss_ratio').dropna();piv['gap']=piv.future-piv.same_period;v=balanced_seed_values(piv.reset_index(),'gap');ci=paired_seed_interval(v)
                    state=('Future-Worse' if ci['lo']>0 else 'Future-Better' if ci['hi']<0 else 'Inconclusive') if full else 'Not-Estimable'
                    gaps.append({'matching':arm,'source':source,'suite':suite,'complete_support':full,'gap':ci['estimate'],'ci_lo':ci['lo'],'ci_hi':ci['hi'],'n_seeds':ci['n_seeds'],'outcome':state,'interpretation':'change in relative loss, not a causal estimate of drift'})
    save_csv(RUN/'utility_complete_support.csv',complete_cards);save_csv(RUN/'corrected_utility_summary.csv',summ);save_csv(RUN/'corrected_transfer_summary.csv',gaps)
    return pd.DataFrame(summ),pd.DataFrame(gaps)
