# Task construction retains the external notebook's lag and target definitions.
def make_card(template,values,observed,selection_fit):
    card={k:v for k,v in template.items() if k!='train_threshold'}
    card['historical_threshold']=template.get('train_threshold')
    a,b=selection_fit;j=feature_index[card['target']];raw=values[a:b,j];ok=observed[a:b,j]
    if not ok.any():card['threshold']=None
    elif card['task_type']=='threshold_classification':card['threshold']=float(np.quantile(raw[ok],.90))
    elif card['task_type']=='transition_classification':card['threshold']=.5
    else:card['threshold']=None
    # Same target and horizon variants are collapsed before capabilities are averaged.
    card['family']=card['capability']+'|'+card['target']
    card['model_id']='linear';return card


def examples(values,observed,card,interval):
    start,end=map(int,interval);lag=int(card['lag_rows']);h=int(card['horizon_rows'])
    idx=np.arange(start+lag,end-h,dtype=int)
    j=feature_index[card['target']];pp=[feature_index[p] for p in card['predictors']]
    if card['axis']=='temporal': pred_idx=idx-lag;target_idx=idx+h
    else:pred_idx=idx;target_idx=idx
    good=observed[target_idx,j].copy()
    if card['task_type']=='transition_classification':good &= observed[idx,j]
    if card['task_type']!='regression' and card['threshold'] is None:good &= False
    idx=idx[good];pred_idx=pred_idx[good];target_idx=target_idx[good]
    X=values[pred_idx][:,pp];raw=values[:,j]
    if card['task_type']=='threshold_classification':y=(raw[target_idx]>card['threshold']).astype(float)
    elif card['task_type']=='transition_classification':y=((raw[idx]>card['threshold'])!=(raw[target_idx]>card['threshold'])).astype(float)
    else:y=raw[target_idx]
    if not np.isfinite(X).all() or not np.isfinite(y).all():raise ValueError('Non-finite task arrays after the recorded preprocessing.')
    return X,y,idx


def evenly_spaced(n,k):
    if k>=n:return np.arange(n,dtype=int)
    return np.linspace(0,n-1,k,dtype=int)


def support_reason(X,y,card):
    if len(y)<CFG['min_rows']:return 'too_few_observed_examples'
    if card['task_type']!='regression' and len(np.unique(y))<2:return 'single_class'
    return ''


def model_fit(X,y,card,seed):
    if card['task_type']=='regression':
        model=make_pipeline(StandardScaler(),Ridge(alpha=1.,solver='lsqr',tol=1e-6,max_iter=10000))
    else:
        model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=600,solver='lbfgs',random_state=int(seed)))
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always');model.fit(X,y)
    notes=[{'category':w.category.__name__,'message':str(w.message)} for w in ws]
    return model,notes


def model_prediction(model,X,card):
    return model.predict(X) if card['task_type']=='regression' else model.predict_proba(X)[:,1]


def losses(ytrain,ytest,pred,card):
    if card['task_type']=='regression':
        raw_iqr=robust_iqr(ytest);scale=max(raw_iqr,1e-6);base=float(np.median(ytrain))
        loss=float(np.mean(np.abs(ytest-pred))/scale);naive=float(np.mean(np.abs(ytest-base))/scale)
        other={'target_IQR':raw_iqr,'loss_scale':scale,'IQR_floor_activated':raw_iqr<1e-6,'naive_prediction':base}
    else:
        base=float(np.mean(ytrain));loss=float(np.mean((ytest-pred)**2));naive=float(np.mean((ytest-base)**2))
        auc=float(roc_auc_score(ytest,pred)) if len(np.unique(ytest))==2 else np.nan
        ap=float(average_precision_score(ytest,pred)) if len(np.unique(ytest))==2 else np.nan
        other={'AUC':auc,'AP_gain':ap-float(np.mean(ytest)),'prevalence':float(np.mean(ytest)),'naive_prediction':base}
    return {'loss':loss,'naive_loss':naive,'reference_skill':(naive-loss)/max(naive,1e-12),**other}


def loss_ratio_record(ref,syn):
    result={'real_loss':ref['loss'],'synthetic_loss':syn['loss'],'naive_loss':ref['naive_loss'],'reference_skill':ref['reference_skill'],'status':'ok'}
    if ref['loss']<CFG['reference_loss_floor']:result['status']='reference_loss_below_floor'
    elif ref['naive_loss']<=0:result['status']='invalid_naive_loss'
    elif ref.get('target_IQR',np.inf)<CFG['target_IQR_floor']:result['status']='target_IQR_below_floor'
    # Zero candidate loss is retained but does not enter log-based aggregation.
    elif syn['loss']<=0:result['status']='zero_candidate_loss_log_undefined'
    if result['status']=='ok':
        ratio=syn['loss']/ref['loss'];result.update(ratio=ratio,log_ratio=float(np.log(ratio)),noninferior=ratio<=CFG['ni_ratio'])
    for k in ['target_IQR','loss_scale','IQR_floor_activated','AUC','AP_gain','prevalence','naive_prediction']:
        if k in ref:result['real_'+k]=ref[k]
    return result


def admission(regime,values,observed):
    cards=[];rows=[]
    for t in ASSETS['task_templates']:
        c=make_card(t,values,observed,regime['selection_fit'])
        X,y,idx=examples(values,observed,c,regime['selection_fit']);V,v,vidx=examples(values,observed,c,regime['selection_validation'])
        row={**c,'regime':regime['name'],'n_train':len(y),'n_validation':len(v),'admitted':False}
        reason=support_reason(X,y,c) or support_reason(V,v,c)
        if not reason and c['task_type']!='regression' and not (CFG['prevalence_range'][0]<=np.mean(v)<=CFG['prevalence_range'][1]):reason='prevalence_outside_range'
        if not reason:
            try:
                m,w=model_fit(X,y,c,CFG['seeds'][0]);d=losses(y,v,model_prediction(m,V,c),c);row.update(d,warnings=w)
                passed=d['reference_skill']>=CFG['reference_skill_gain']
                if c['task_type']!='regression':passed=passed and d['AUC']>=CFG['auc_min'] and d['AP_gain']>=CFG['ap_gain_min']
                if any(x['category']=='ConvergenceWarning' for x in w):passed=False;reason='task_model_did_not_converge'
                if passed:row['admitted']=True;cards.append(c)
                elif not reason:reason='reference_did_not_clear_admission_rules'
            except Exception as exc:reason='execution_error';row['error']=repr(exc)
        row['reason']=reason;rows.append(row)
    return {'cards':cards,'rows':rows,'prior_template_count':len(ASSETS['task_templates']),'full_historical_candidate_count':155,'scope':'Re-admission of prior templates, not a fresh feature/task search.'}


def feature_health(reference,syn):
    if reference.shape[1]!=syn.shape[1]:raise RuntimeError('Generated width differs from the frozen value scope.')
    rows=[]
    for j,name in enumerate(VALUE_FEATURES):
        a=reference[:,j];b=syn[:,j]
        rows.append({'feature':name,'learned_feature':name in LEARNED_SCOPE,'reference_variable':np.std(a)>1e-9,'output_variable':np.std(b)>1e-9,'reference_zero_rate':np.mean(a==0),'output_zero_rate':np.mean(b==0),'activity_rate_error':abs(np.mean(a==0)-np.mean(b==0)),'support_violation':np.mean((b<a.min())|(b>a.max())),'finite':bool(np.isfinite(b).all())})
    return rows


def paired_task_fit(real,real_observed,syn,card,seed,tests,array_prefix,syn_observed=None,force_n=None):
    xr,yr,ri=examples(real,real_observed,card,(0,len(real)))
    syn_observed=np.ones(syn.shape,bool) if syn_observed is None else syn_observed
    xs,ys,si=examples(syn,syn_observed,card,(0,len(syn)))
    nr_available,ns_available=len(yr),len(ys)
    n=min(len(yr),len(ys),force_n if force_n is not None else max(len(yr),len(ys)));rsel=evenly_spaced(len(yr),n);ssel=evenly_spaced(len(ys),n)
    xr,yr,ri=xr[rsel],yr[rsel],ri[rsel];xs,ys,si=xs[ssel],ys[ssel],si[ssel]
    base={'task_id':card['task_id'],'capability':card['capability'],'family':card['family'],'axis':card['axis'],'model_id':card['model_id'],'n_real_train':n,'n_synthetic_train':n,'real_available':nr_available,'synthetic_available':ns_available,'synthetic_target_observation_policy':'finite complete value output. Missingness generation is outside this run.'}
    reason=support_reason(xr,yr,card) or support_reason(xs,ys,card)
    if reason:return [{**base,'period':t['name'],'status':reason} for t in tests],[]
    try:mr,wr=model_fit(xr,yr,card,seed);ms,ws=model_fit(xs,ys,card,seed)
    except Exception as exc:return [{**base,'period':t['name'],'status':'execution_error','error':repr(exc)} for t in tests],[]
    conv=any(w['category']=='ConvergenceWarning' for w in wr+ws)
    arrays={'real_training_task_rows':ri,'synthetic_training_task_rows':si,'real_training_y':yr,'synthetic_training_y':ys}
    for model_name,model in [('real',mr),('synthetic',ms)]:
        fitted=model.steps[-1][1];scaler=model.steps[0][1]
        arrays[model_name+'_coef']=np.asarray(fitted.coef_);arrays[model_name+'_intercept']=np.asarray(fitted.intercept_)
        arrays[model_name+'_scaler_mean']=scaler.mean_;arrays[model_name+'_scaler_scale']=scaler.scale_
    rows=[]
    for t in tests:
        xt,yt,ti=examples(t['values'],t['observed'],card,(0,len(t['values'])))
        row={**base,'period':t['name'],'n_test':len(yt),'warnings':wr+ws}
        reason=support_reason(xt,yt,card)
        if reason:rows.append({**row,'status':reason});continue
        rp=model_prediction(mr,xt,card);sp=model_prediction(ms,xt,card)
        ref=losses(yr,yt,rp,card);cand=losses(ys,yt,sp,card);row.update(loss_ratio_record(ref,cand))
        if conv:row['status']='task_model_did_not_converge'
        arrays[t['name']+'_rows']=ti;arrays[t['name']+'_y']=yt;arrays[t['name']+'_real_prediction']=rp;arrays[t['name']+'_synthetic_prediction']=sp
        rows.append(row)
    rel='arrays/'+array_prefix+'__'+card['task_id']+'.npz';path=RUN/rel;path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,**arrays)
    return rows,[rel]
