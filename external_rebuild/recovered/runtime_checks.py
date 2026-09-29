def run_software_checks():
    """Small constructed checks of software behaviour, not new scientific evidence."""
    global VALUE_FEATURES,feature_index,LEARNED_SCOPE,C2ST_SCOPES,CFG,RUN,PROTOCOL_HASH,EXECUTION_RECORDS
    import tempfile,copy
    names=['VALUE_FEATURES','feature_index','LEARNED_SCOPE','C2ST_SCOPES','CFG','RUN','PROTOCOL_HASH','EXECUTION_RECORDS']
    old={k:globals().get(k) for k in names};results=[]
    def check(name,condition):
        if not condition:raise AssertionError('Software check failed: '+name)
        results.append({'check':name,'passed':True})
    try:
        VALUE_FEATURES=['x','y'];feature_index={'x':0,'y':1};LEARNED_SCOPE=['x','y'];C2ST_SCOPES={'values':['x','y']}
        CFG=copy.deepcopy(CFG);CFG.update(n_jobs=1,c2st_trees=5,c2st_null_trees=3,c2st_splits=2,c2st_permutations=2,p0_bootstrap_draws=80)
        r=np.random.default_rng(100);n=1200;x=r.normal(size=n);v=np.column_stack([x,2*x+r.normal(0,.3,n)]);o=np.ones(v.shape,bool)
        c={'task_id':'check','axis':'contemporaneous','capability':'same','family':'y','model_id':'linear','target':'y','predictors':['x'],'lag_rows':0,'horizon_rows':0,'task_type':'regression','threshold':None}
        o[100,1]=False;xx,yy,ii=examples(v,o,c,(0,600));check('missing real target excluded',100 not in ii and len(ii)==599)
        tc={**c,'axis':'temporal','lag_rows':12,'horizon_rows':12}
        xx,yy,ii=examples(v,o,tc,(200,600));check('lag/target windows stay within segment',ii.min()-12>=200 and ii.max()+12<600)
        with tempfile.TemporaryDirectory() as td:
            RUN=Path(td);(RUN/'arrays').mkdir();PROTOCOL_HASH='software-check';EXECUTION_RECORDS=[]
            rr,ff=paired_task_fit(v[:600],o[:600],v[:600],c,1337,[{'name':'near','values':v[600:],'observed':o[600:]}],'identity',syn_observed=o[:600])
            check('identity has equal counts and unit ratio',rr[0]['n_real_train']==rr[0]['n_synthetic_train'] and abs(rr[0]['ratio']-1)<1e-12)
            rr,_=paired_task_fit(v[:700],o[:700],v[:400],c,1337,[{'name':'near','values':v[700:],'observed':o[700:]}],'budget')
            check('unequal input amounts produce equal training counts',rr[0]['n_real_train']==rr[0]['n_synthetic_train']==400)
            count=[0]
            def operation():count[0]+=1;return {'value':7}
            cached_job('test',{'seed':1},operation);cached_job('test',{'seed':1},operation)
            check('matching completed job resumes without recomputation',count[0]==1)
            p=next((RUN/'jobs'/'test').glob('*.json'));record=json.loads(p.read_text());record['payload']['value']=8;atomic_json(p,record)
            rejected=False
            try:cached_job('test',{'seed':1},operation)
            except RuntimeError:rejected=True
            check('changed checkpoint payload is rejected',rejected)
        cc=grouped_c2st(v,v.copy(),991,rows_cap=600)
        check('C2ST keeps complete groups separate',all(not set(f['train_groups'])&set(f['test_groups']) for f in cc['folds']))
        check('identical C2ST inputs are not falsely well separated',abs(cc['AUC']-.5)<1e-8)
        check('C2ST trims a derived time gap',all(f['minimum_gap_between_retained_adjacent_groups']>=25 for f in cc['folds']))
        # Direct stage-decision unit check. This is intentionally not labelled a data benchmark.
        row={'axis':'contemporaneous','status':'ok','source_valid':True}
        checks=[{'metric':'marginal_ks_mean','passed':True},{'metric':'coupling_corr_mae','passed':True}]
        check('failed reference check cannot admit utility',permission_for_utility(row,{'eligible':True,'identity_ok':True,'licensed':False},checks)=='Property-Unlicensed')
    finally:
        for k,vv in old.items():
            if vv is None:globals().pop(k,None)
            else:globals()[k]=vv
    progress(f'{len(results)} software checks passed. These are not research results.')
    return results
