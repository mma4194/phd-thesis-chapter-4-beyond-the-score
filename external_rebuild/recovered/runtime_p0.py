# P0: matched TRAIN blocks, calibration, reference skill and order checks.
def select_p0_pairs(regime,values,observed,seconds):
    start,end=regime['train'];records=[]
    if regime['name']=='primary':
        width=360
        for i,p in enumerate(ASSETS['external']['p0']['pairs']):
            a=int(p['a_start']);b=int(p['b_start']);fa=float(observed[a:a+width].mean());fb=float(observed[b:b+width].mean())
            ca=float(p.get('a_coverage',1.));cb=float(p.get('b_coverage',1.))
            records.append({'pair_id':f'p{i}','a_start':a,'b_start':b,'width':width,'phase':p['role'],'distance':p['profile_distance'],'a_coverage':ca,'b_coverage':cb,'finite_value_fraction_a':fa,'finite_value_fraction_b':fb,'coverage_basis':'recorded acquisition coverage, bound to unchanged input hashes','usable':bool(a>=start and b>=start and a+width<=end and b+width<=end and min(ca,cb)>=CFG['block_coverage_min']),'selection':'recorded_primary_pair'})
        return {'pairs':records,'candidate_blocks':[],'duration_minutes':30,'method':'Recorded pairs and recorded acquisition coverage retained. Actual finite-value fractions are reported separately and missing real targets are excluded. Finite-value availability is not acquisition coverage.'}
    candidates=[];best=[]
    # New origin-local matching is specified before running. It does not rewrite primary matches.
    for minutes in [30,60,90,120,150,180]:
        width=minutes*12;blocks=[];profiles=[]
        tr=values[start:end];center=np.median(tr,axis=0);scale=np.median(np.abs(tr-center),axis=0)*1.4826
        scale[scale<1e-8]=1.
        for a in range(start,end-width+1,width):
            coverage=float(observed[a:a+width].mean());ok=coverage>=CFG['block_coverage_min']
            candidates.append({'minutes':minutes,'start':a,'end':a+width,'coverage':coverage,'passes_value_availability':ok,'quantity':'fraction of finite pre-imputation values, not acquisition coverage'})
            if not ok:continue
            v=values[a:a+width];theta=seconds[a:a+width]%86400/86400*(2*np.pi)
            profiles.append(np.r_[(v.mean(axis=0)-center)/scale,np.mean(v==0,axis=0),np.sin(theta).mean(),np.cos(theta).mean()]);blocks.append(a)
        if len(blocks)<20:continue
        profiles=np.asarray(profiles);m=np.median(profiles,axis=0);s=np.median(abs(profiles-m),axis=0)*1.4826;s[s<1e-8]=1;z=(profiles-m)/s
        midpoint=len(blocks)//2;available=set(range(midpoint,len(blocks)));pairs=[]
        for ai in range(midpoint):
            if not available:break
            bi=min(available,key=lambda j:(np.linalg.norm(z[ai]-z[j]),j));available.remove(bi)
            pairs.append({'a_start':blocks[ai],'b_start':blocks[bi],'width':width,'distance':float(np.linalg.norm(z[ai]-z[bi])),'a_coverage':float(observed[blocks[ai]:blocks[ai]+width].mean()),'b_coverage':float(observed[blocks[bi]:blocks[bi]+width].mean())})
        dd=np.asarray([p['distance'] for p in pairs]);threshold=float(np.median(dd)+3*1.4826*np.median(abs(dd-np.median(dd))))
        screened=[p for p in pairs if p['distance']<=threshold]
        if len(screened)<10:continue
        chosen=sorted(screened,key=lambda p:(p['distance'],p['a_start'],p['b_start']))[:10]
        for i,p in enumerate(chosen):p.update(pair_id=f'p{i}',phase='calibration' if i%2==0 else 'qualification',usable=True,selection='origin_TRAIN_only',distance_screen=threshold)
        best=chosen;break
    return {'pairs':best,'candidate_blocks':candidates,'duration_minutes':best[0]['width']/12 if best else None,'method':'First duration with ten value-availability- and distance-screened disjoint pairs. The 0.95 availability screen is an explicit new origin rule, not a reconstruction of the historical acquisition-coverage calculation. TRAIN MAD-scaled means, zero rates, and 24-hour cycle position in the recorded experiment clock (not local time of day). Exact profiles and rules are code-bound.'}


def p0_job(regime,pair,seed,cards,values,observed):
    if not pair['usable']:return {'rows':[],'reason':'pair_failed_input_coverage'}
    a=pair['a_start'];b=pair['b_start'];w=pair['width'];A=values[a:a+w];AO=observed[a:a+w];B=values[b:b+w];BO=observed[b:b+w]
    span=max([int(c['lag_rows'])+int(c['horizon_rows'])+1 for c in cards]+[25]);n=w-span
    if n<=0:return {'rows':[],'reason':'block_shorter_than_task_span'}
    rng_a=np.random.default_rng(seed+101);rng_b=np.random.default_rng(seed+202);rng_r=np.random.default_rng(seed+303)
    ia=int(rng_a.integers(0,w-n+1));ib=int(rng_b.integers(0,w-n+1));ir=rng_r.integers(0,w,size=n)
    anchors={'identity':(A,AO),'block_a':(A[ia:ia+n],AO[ia:ia+n]),'block_b':(A[ib:ib+n],AO[ib:ib+n]),'row_resample':(A[ir],AO[ir])}
    rows=[];files=[]
    for c in cards:
        counts=[len(examples(x,o,c,(0,len(x)))[1]) for x,o in anchors.values()];count=min(counts)
        for name,(x,o) in anchors.items():
            prefix=f"p0_{regime['name']}_{pair['pair_id']}_{seed}_{name}"
            rr,ff=paired_task_fit(A,AO,x,c,seed,[{'name':'matched','values':B,'observed':BO}],prefix,syn_observed=o,force_n=count)
            files+=ff
            rows.extend([{**row,'regime':regime['name'],'pair_id':pair['pair_id'],'phase':pair['phase'],'seed':seed,'anchor':name,'a_start':a,'b_start':b,'block_width':w,'sampled_block_a_start':ia,'sampled_block_b_start':ib,'requested_equal_examples':count} for row in rr])
    return {'rows':rows,'anchor_row_resample_indices':ir.tolist(),'_files':files}


def balanced_cells(frame,field):
    if frame.empty:return pd.DataFrame(columns=['pair_id','seed','value'])
    g=frame.groupby(['pair_id','seed','family'],dropna=False)[field].median().reset_index()
    return g.groupby(['pair_id','seed'],as_index=False)[field].mean().rename(columns={field:'value'})


def complete_cells(frame):
    if frame.empty:return frame
    mat=frame.pivot_table(index='pair_id',columns='seed',values='value',aggfunc='mean').reindex(columns=CFG['seeds']).dropna()
    return mat.rename_axis(columns='seed').stack().rename('value').reset_index()


def ci_cells(frame,offset=0):
    x=complete_cells(frame)
    return crossed_pair_seed_ci(x,seed=CFG['seeds'][0]+offset,draws=CFG['p0_bootstrap_draws'])


def p0_decisions(rows,cards,unclipped=False):
    u=pd.DataFrame(rows);outputs=[]
    for j,(axis,cap) in enumerate(sorted(set((c['axis'],c['capability']) for c in cards))):
        base={'axis':axis,'capability':cap,'unclipped':unclipped,'eligible':False,'licensed':False,'state':'Not-Estimable'}
        if u.empty:outputs.append({**base,'reason':'no_P0_rows'});continue
        q=u[(u.axis==axis)&(u.capability==cap)&(u.status=='ok')].copy()
        if q.empty:outputs.append({**base,'reason':'no_usable_P0_rows'});continue
        # Compare anchors using exactly the same task/pair/seed cells.
        keys=['phase','pair_id','seed','family','task_id']
        pivot=q.pivot_table(index=keys,columns='anchor',values='log_ratio',aggfunc='first')
        if not set(['identity','block_a','block_b','row_resample']).issubset(pivot.columns):outputs.append({**base,'reason':'missing_control'});continue
        pivot=pivot.dropna(subset=['identity','block_a','block_b','row_resample']).reset_index()
        pivot['blocks']=.5*(pivot.block_a+pivot.block_b);pivot['difference']=pivot.row_resample-pivot.blocks
        pivot['cal_noise']=abs(pivot.block_a-pivot.block_b)
        pivot['ni_rate']=.5*((pivot.block_a<=math.log(CFG['ni_ratio'])).astype(float)+(pivot.block_b<=math.log(CFG['ni_ratio'])).astype(float))
        cal=pivot[pivot.phase=='calibration'];held=pivot[pivot.phase=='qualification']
        cal_values=complete_cells(balanced_cells(cal,'cal_noise' if axis=='contemporaneous' else 'blocks'))
        raw,ncal,_,_=_hierarchical_calibration_quantile(cal_values,CFG['margin_quantile'])
        if ncal<CFG['min_pairs'] or not finite(raw):outputs.append({**base,'reason':'insufficient_calibration_pairs','calibration_pairs':ncal});continue
        raw_margin=raw if axis=='contemporaneous' else math.exp(raw)
        applied=raw_margin if unclipped else float(np.clip(raw_margin,CFG['xs_floor'] if axis=='contemporaneous' else CFG['temporal_floor'],CFG['xs_cap'] if axis=='contemporaneous' else CFG['temporal_cap']))
        ids=ci_cells(balanced_cells(held,'identity'),100+j)
        difference=ci_cells(balanced_cells(held,'difference'),200+j)
        blocks=ci_cells(balanced_cells(held,'blocks'),300+j)
        ni=ci_cells(balanced_cells(held,'ni_rate'),400+j)
        # Stage 3A uses identity losses on the same common qualification cells.
        identity=q[(q.anchor=='identity')&(q.phase=='qualification')].merge(held[keys],on=keys,how='inner')
        ref=ci_cells(balanced_cells(identity,'reference_skill'),500+j)
        n=min(ids['n_pairs'],difference['n_pairs'],blocks['n_pairs'],ref['n_pairs'])
        eligible=n>=CFG['min_pairs']
        idok=eligible and ids['ci_lo']>=-CFG['id_margin'] and ids['ci_hi']<=CFG['id_margin']
        refok=eligible and ref['ci_lo']>0
        if axis=='contemporaneous':relative=eligible and difference['ci_lo']>=-applied and difference['ci_hi']<=applied;order=True
        else:relative=eligible and math.exp(blocks['ci_hi'])<=applied and ni['estimate']>=CFG['ni_rate_min'];order=eligible and difference['ci_lo']>=CFG['order_min']
        state='Not-Estimable' if not eligible else ('Instrument-Invalid' if not idok else ('Admissible' if refok and relative and order else 'Property-Unlicensed'))
        outputs.append({**base,'state':state,'eligible':eligible,'licensed':bool(eligible and idok and refok and relative and order),'qualification_pairs':n,'calibration_pairs':ncal,'identity_ok':bool(idok),'reference_viable':bool(refok),'relative_ok':bool(relative),'order_ok':bool(order),'raw_margin':raw_margin,'applied_margin':applied,'reference_skill':ref['estimate'],'reference_skill_lo':ref['ci_lo'],'reference_skill_hi':ref['ci_hi'],'relative_log_difference':difference['estimate'],'relative_log_difference_lo':difference['ci_lo'],'relative_log_difference_hi':difference['ci_hi'],'block_ratio':math.exp(blocks['estimate']) if finite(blocks['estimate']) else None,'block_ratio_hi':math.exp(blocks['ci_hi']) if finite(blocks['ci_hi']) else None,'noninferiority_rate':ni['estimate'],'identity_log_lo':ids['ci_lo'],'identity_log_hi':ids['ci_hi']})
    return outputs


def p0_c2st_job(pair,values,scope,seed):
    if not pair['usable']:return {'status':'pair_failed_input_coverage','AUC':None}
    js=[feature_index[c] for c in C2ST_SCOPES[scope]];a=pair['a_start'];b=pair['b_start'];w=pair['width']
    return grouped_c2st(values[a:a+w][:,js],values[b:b+w][:,js],seed)


def run_qualification(regime,cards,values,observed,seconds):
    design=select_p0_pairs(regime,values,observed,seconds)
    freeze_json(RUN/'selection'/f"{regime['name']}_P0_plan.json",design)
    rows=[];crows=[]
    for i,pair in enumerate(design['pairs']):
        for seed in CFG['seeds']:
            key={'regime':regime['name'],'pair':pair,'seed':seed,'cards_hash':digest(cards)}
            record=cached_job('P0_tasks',key,lambda:p0_job(regime,pair,seed,cards,values,observed));rows+=record['rows']
        for scope in C2ST_SCOPES:
            key={'regime':regime['name'],'pair':pair,'scope':scope,'seed':1000+i}
            r=cached_job('P0_C2ST',key,lambda:p0_c2st_job(pair,values,scope,1000+i))
            crows.append({'regime':regime['name'],'pair_id':pair['pair_id'],'phase':pair['phase'],'scope':scope,'status':r['status'],'AUC':r.get('AUC'),'n_per_class':r.get('n_per_class'),'groups':r.get('groups')})
        progress(f"{regime['name']}: completed P0 pair {i+1}/{len(design['pairs'])}.")
    decisions=p0_decisions(rows,cards);raw=p0_decisions(rows,cards,unclipped=True)
    for name,x in [('P0_losses',rows),('P0_C2ST',crows),('qualification',decisions),('qualification_unclipped',raw)]:table(RUN/'tables'/f"{regime['name']}_{name}.csv",x)
    return {'design':design,'rows':rows,'decisions':decisions,'raw_decisions':raw,'c2st':crows}
