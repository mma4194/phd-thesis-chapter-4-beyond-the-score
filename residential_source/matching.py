def profile_and_match(raw,seconds):
    profiles=[{} for _ in BLOCKS];groups={};zero_rows=[];descriptor_rows=[]
    for c in PROFILE_COLS:
        tr=raw.iloc[:SPLIT['train_end']];ok=observed(tr,c);reference=np.sort(tr[c].to_numpy(float)[ok]);variable=len(reference)>0 and reference[0]!=reference[-1]
        tier=infer_tier(c)
        for bi,b in enumerate(BLOCKS):
            f=raw.iloc[b['start']:b['end']];valid=observed(f,c);v=f[c].to_numpy(float);vals=v[valid]
            profiles[bi]['missing__'+c]=1-float(valid.mean());groups['missing__'+c]=tier+'|missing'
            if variable:
                ranks=(np.searchsorted(reference,vals,'left')+np.searchsorted(reference,vals,'right'))/(2*len(reference))
                profiles[bi]['rank__'+c]=float(ranks.mean()) if len(vals) else .5;groups['rank__'+c]=tier+'|values'
                profiles[bi]['zero__'+c]=float((vals==0).mean()) if len(vals) else .5;groups['zero__'+c]=tier+'|zeros'
            zero_rows.append({'block':bi,'feature':c,'rows':len(f),'missing_values':int((~valid).sum()),'observed_values':int(valid.sum()),'stored_zero_values':int((vals==0).sum()),'observed_mean':float(vals.mean()) if len(vals) else None,'observed_constant_in_TRAIN':not variable,'unit_verified':False})
        descriptor_rows.append({'feature':c,'TRAIN_observed':len(reference),'value_descriptors_included':variable,'reason':'bounded ranks and observed zero fraction' if variable else 'no observed variation, retain missingness descriptor only'})
    for bi,b in enumerate(BLOCKS):
        phase=seconds[b['start']:b['end']]%86400/86400*2*np.pi
        for name,v in [('sin',np.sin(phase)),('cos',np.cos(phase))]:profiles[bi]['time_'+name]=float((v.mean()+1)/2);groups['time_'+name]='time'
    cols=sorted(profiles[0]);mat=np.array([[p[c] for c in cols] for p in profiles]);group_size={g:sum(v==g for v in groups.values()) for g in set(groups.values())}
    weights=np.array([1/(len(group_size)*group_size[groups[c]]) for c in cols]);n=len(BLOCKS)//2
    D=np.array([[np.sqrt(np.sum(weights*(mat[i]-mat[j])**2)) for j in range(n,2*n)] for i in range(n)])
    ii,jj=linear_sum_assignment(D);plans={}
    # Selection uses profiles only. Pair roles are fixed by source-block parity across every arm.
    pairs=[{'source_block':int(i),'target_block':int(j+n)} for i,j in zip(ii,jj)]
    old=list(pd.read_csv(io.StringIO(ASSETS['prior_matching_results']['original_pairs.csv'])).to_dict('records'))
    prev=list(pd.read_csv(io.StringIO(ASSETS['prior_matching_results']['observed_rank_pairs.csv'])).to_dict('records'))
    for arm,pp in [('balanced_observed',pairs),('prior_observed_pairs',prev),('original_pairs',old)]:
        plans[arm]=[{'pair_id':f'pair{int(p["source_block"])}','source_block':int(p['source_block']),'target_block':int(p['target_block']),'phase':'calibration' if int(p['source_block'])%2==0 else 'qualification','distance_under_corrected_scale':float(D[int(p['source_block']),int(p['target_block'])-n])} for p in sorted(pp,key=lambda p:p['source_block'])]
        save_csv(RUN/f'matching_{arm}.csv',plans[arm])
    audit=[];parts=[]
    for arm,pp in plans.items():
        for p in pp:
            i,j=p['source_block'],p['target_block'];sq=weights*(mat[i]-mat[j])**2
            for c,w,v in zip(cols,weights,sq):parts.append({'arm':arm,'pair_id':p['pair_id'],'descriptor':c,'group':groups[c],'weight':w,'squared_contribution':v,'share':v/sq.sum() if sq.sum() else 0})
            for c in PROFILE_COLS:
                x=raw.iloc[BLOCKS[i]['start']:BLOCKS[i]['end']];y=raw.iloc[BLOCKS[j]['start']:BLOCKS[j]['end']];ox=observed(x,c);oy=observed(y,c);a=x[c].to_numpy(float)[ox];b=y[c].to_numpy(float)[oy]
                audit.append({'arm':arm,'pair_id':p['pair_id'],'feature':c,'observed_fraction_a':float(ox.mean()),'observed_fraction_b':float(oy.mean()),'both_have_observations':bool(len(a) and len(b)),'observed_KS':float(ks_2samp(a,b).statistic) if len(a) and len(b) else None,'observed_mean_a':float(a.mean()) if len(a) else None,'observed_mean_b':float(b.mean()) if len(b) else None})
    save_csv(RUN/'matching_profile_rules.csv',descriptor_rows);save_csv(RUN/'zero_and_missingness_by_block.csv',zero_rows);save_csv(RUN/'matching_value_checks.csv',audit);save_csv(RUN/'matching_contributions.csv',parts)
    save_csv(RUN/'matching_candidate_distances.csv',[{'source_block':i,'target_block':j+n,'distance':D[i,j]} for i in range(n) for j in range(n)])
    save_json(RUN/'matching_profiles.json',{'profiles':profiles,'weights':dict(zip(cols,weights)),'groups':groups})
    return plans

def corrected_controls(frame,seed):
    n=len(frame);length=min(n,max(4*CFG['max_window_span'],min(n//5,3600)));out={'real_identity':(frame,None)}
    for name,off in [('real_block_a',101),('real_block_b',202)]:
        rng=np.random.default_rng(seed+off);starts=rng.integers(0,n-length+1,math.ceil(n/length));ix=np.concatenate([np.arange(s,s+length) for s in starts])[:n];segments=np.repeat(np.arange(len(starts)),length)[:n];out[name]=(frame.iloc[ix].reset_index(drop=True),segments)
    ix=np.random.default_rng(seed+303).choice(n,n,replace=True);out['real_resample']=(frame.iloc[ix].reset_index(drop=True),None)
    return out

def p0_card(source_id,targets,seed,card,raw):
    b=BLOCKS[source_id];src=raw.iloc[b['start']:b['end']];controls=corrected_controls(src,seed);arrays={};audits={}
    for name,(f,segments) in controls.items():
        X,y,a=task_arrays(f,card.task,CFG['row_cap_task_train'],segments);arrays[name]=(X,y);audits[name]=a
    n=min(len(y) for X,y in arrays.values());models={};ys={};health={}
    for name,(X,y) in arrays.items():
        take=deterministic_subsample_indices(len(y),n) if n else np.array([],dtype=int);X=X.iloc[take];y=y.iloc[take];ys[name]=y;models[name],health[name]=fit_model_checked(X,y,card,seed)
    rows=[]
    for target_id in targets:
        b=BLOCKS[target_id];X,y,a=task_arrays(raw.iloc[b['start']:b['end']],card.task,CFG['row_cap_task_test']);sc={name:score_model(m,ys[name],X,y,card) if m is not None else health[name] for name,m in models.items()};ref=sc['real_identity']
        for name,d in sc.items():
            row={'source_block':source_id,'target_block':target_id,'seed':seed,'card_id':card.card_id,'suite':card.task.suite,'capability':card.task.capability,'task_family':card.task.family,'target':card.task.target,'p0_anchor':name,'n_train':n,'n_reference_train':n,'n_test':len(y),'target_missing_removed_train':audits[name]['missing_target_contexts'],'target_missing_removed_test':a['missing_target_contexts'],'unobserved_contexts_used':0,'fit_health':health[name],**d}
            if ref['status']!='ok':row['status']='reference_'+ref['status']
            elif d['status']=='ok':
                L=ref['loss'];N=ref['naive_loss'];S=d['loss']
                if not np.isfinite(L) or L<CFG['min_reference_loss'] or not np.isfinite(N) or N<=0:row['status']='unusable_reference_loss'
                else:row.update(loss_ratio=S/L,log_loss_ratio=float(np.log(max(S/L,1e-12))),noninferior=S/L<=CFG['utility_noninferiority_ratio'],reference_skill=(N-L)/N,reference_loss=L,naive_loss=N,perfect_candidate_loss=S==0)
            rows.append(row)
    return {'rows':rows}

def corrected_qualification(raw,plans,admitted):
    global CARDS
    fixed_cards=list(CARDS);CARDS=[c for c in CARDS if c.card_id in admitted]
    save_json(RUN/'P0_card_support.json',{'requested':[c.card_id for c in fixed_cards],'retained':[c.card_id for c in CARDS],'excluded_by_corrected_VAL':[c.card_id for c in fixed_cards if c.card_id not in admitted]})
    target_map=defaultdict(set)
    for pp in plans.values():
        for p in pp:target_map[p['source_block']].add(p['target_block'])
    rows=[];total=len(target_map)*len(CFG['seeds'])*len(CARDS);done=0
    for s,tt in sorted(target_map.items()):
        for seed in CFG['seeds']:
            for c in CARDS:
                rows+=cache('corrected_P0',{'source':s,'targets':sorted(tt),'seed':seed,'card':c.key()},lambda:p0_card(s,sorted(tt),seed,c,raw))['rows'];done+=1
                if done%10==0:msg(f'Corrected P0 jobs {done}/{total}.')
    base=pd.DataFrame(rows);save_csv(RUN/'P0_losses.csv',base)
    # Include every original capability in the decision table, even if all its cards were excluded.
    CARDS=fixed_cards;decisions=[]
    for arm,pp in plans.items():
        frames=[]
        for p in pp:
            x=base[(base.source_block==p['source_block'])&(base.target_block==p['target_block'])].copy() if len(base) else pd.DataFrame()
            x['phase']=p['phase'];x['pair_id']=p['pair_id'];frames.append(x)
        df=pd.concat(frames,ignore_index=True)
        for clip in [True,False]:
            if not len(df):
                for suite,cap in sorted({(c.task.suite,c.task.capability) for c in CARDS}):decisions.append({'arm':arm,'suite':suite,'capability':cap,'clipped':clip,'eligible':False,'final_rule_licensed':False,'state':'Not-Estimable','reason':'No P0 card passed corrected admission'})
            else:decisions+=qualify(df,arm,clip)
    out=pd.DataFrame(decisions);out=out.rename(columns={'historical_rule_licensed':'without_reference_skill_check'})
    save_csv(RUN/'corrected_qualification.csv',out)
    return out
