def qualify(df,arm,clipped=True):
    # Retain the original family-median then capability-mean hierarchy. Report support explicitly.
    df=df.copy()
    for name in ['log_loss_ratio','noninferior','reference_skill']:
        if name not in df:df[name]=np.nan
    good=df[(df.status=='ok')&df.log_loss_ratio.notna()].copy()
    # Every within-cell comparison uses the same cards and all four controls.
    if len(good):
        keys=['phase','pair_id','seed','card_id']
        counts=good.groupby(keys).p0_anchor.nunique().rename('anchors').reset_index()
        good=good.merge(counts[counts.anchors==4][keys],on=keys,how='inner')
    rows=[]
    for suite,cap in sorted({(c.task.suite,c.task.capability) for c in CARDS}):
        sub=good[(good.suite==suite)&(good.capability==cap)]
        family=sub.groupby(['phase','pair_id','seed','p0_anchor','task_family']).agg(log=('log_loss_ratio','median'),ni=('noninferior','mean'),skill=('reference_skill','median')).reset_index()
        cells=family.groupby(['phase','pair_id','seed','p0_anchor']).agg(log=('log','mean'),ni=('ni','mean'),skill=('skill','mean')).reset_index()
        def pivot(phase,value):
            x=cells[cells.phase==phase]
            if x.empty:return pd.DataFrame()
            return x.pivot(index=['pair_id','seed'],columns='p0_anchor',values=value)
        def complete(p,required):
            if not set(required)<=set(p.columns):return pd.DataFrame()
            return p.dropna(subset=required)
        def frame(series):
            if len(series)==0:return pd.DataFrame(columns=['pair_id','seed','value'])
            return series.rename('value').reset_index()
        def crossed(series,seed):return crossed_pair_seed_ci(frame(series),seed=seed)
        cal=complete(pivot('calibration','log'),['real_block_a','real_block_b'])
        calvalue=(cal.real_block_a-cal.real_block_b).abs() if len(cal) and suite=='contemporaneous' else ((cal.real_block_a+cal.real_block_b)/2 if len(cal) else pd.Series(dtype=float))
        q,ncal,_,_=_hierarchical_calibration_quantile(frame(calvalue),CFG['p0_margin_quantile'])
        raw=q if suite=='contemporaneous' else (math.exp(q) if np.isfinite(q) else np.nan)
        floor=CFG['p0_contemporaneous_margin_floor'] if suite=='contemporaneous' else CFG['p0_temporal_ratio_floor'];ceiling=CFG['p0_contemporaneous_margin_ceiling'] if suite=='contemporaneous' else CFG['p0_temporal_ratio_ceiling']
        bound=float(np.clip(raw if np.isfinite(raw) else floor,floor,ceiling)) if clipped else raw
        qlog=pivot('qualification','log')
        v=complete(qlog,['real_block_a','real_block_b','real_resample']);ni=complete(pivot('qualification','ni'),['real_block_a','real_block_b']);sk=complete(pivot('qualification','skill'),['real_identity'])
        identity=qlog.real_identity.dropna() if 'real_identity' in qlog else pd.Series(dtype=float)
        # Same bootstrap seeds as the original capability loop, including its absent-suite rows.
        capabilities=sorted(good.capability.unique());offset=5*capabilities.index(cap) if cap in capabilities else 0
        cid=crossed(identity,1337+offset+(0 if suite=='contemporaneous' else 2))
        cb=crossed((v.real_block_a+v.real_block_b)/2 if len(v) else pd.Series(dtype=float),3337+offset+3)
        cd=crossed(v.real_resample-(v.real_block_a+v.real_block_b)/2 if len(v) else pd.Series(dtype=float),(2337+offset+1) if suite=='contemporaneous' else (4337+offset+3))
        cs=crossed(sk.real_identity if len(sk) else pd.Series(dtype=float),7337+offset)
        nn=float(((ni.real_block_a+ni.real_block_b)/2).mean()) if len(ni) else np.nan
        old_eligible=bool(cid['n_pairs']>=CFG['p0_min_qualification_pairs'] and cd['n_pairs']>=CFG['p0_min_qualification_pairs'])
        idok=cid['n_pairs']>=CFG['p0_min_qualification_pairs'] and cid['ci_lo']>=-CFG['p0_identity_equivalence_log_margin'] and cid['ci_hi']<=CFG['p0_identity_equivalence_log_margin']
        relative=old_eligible and ((cd['ci_lo']>=-bound and cd['ci_hi']<=bound) if suite=='contemporaneous' else (cb['n_pairs']>=CFG['p0_min_qualification_pairs'] and math.exp(cb['ci_hi'])<=bound and nn>=CFG['p0_min_noninferiority_rate']))
        order=True if suite=='contemporaneous' else bool(old_eligible and cd['ci_lo']>=CFG['p0_temporal_order_effect_min'])
        historic=bool(old_eligible and idok and relative and order)
        eligible=bool(old_eligible and ncal>=CFG['p0_min_qualification_pairs'] and cs['n_pairs']>=CFG['p0_min_qualification_pairs'] and np.isfinite(raw))
        refok=bool(eligible and cs['ci_lo']>0)
        final=bool(eligible and historic and refok)
        rows.append({'arm':arm,'suite':suite,'capability':cap,'clipped':clipped,'eligible':eligible,'historical_rule_licensed':historic,'final_rule_licensed':final,'state':'Not-Estimable' if not eligible else ('Implementation-check-failed' if not idok else ('Admissible' if final else 'Property-Unlicensed')),'calibration_pairs':ncal,'qualification_pairs':cid['n_pairs'],'raw_bound':raw,'applied_bound':bound,'identity_ok':idok,'relative_ok':relative,'order_ok':order,'reference_viable':refok,'reference_skill':cs['estimate'],'reference_skill_lo':cs['ci_lo'],'reference_skill_hi':cs['ci_hi'],'block_ratio':math.exp(cb['estimate']) if np.isfinite(cb['estimate']) else None,'block_ratio_hi':math.exp(cb['ci_hi']) if np.isfinite(cb['ci_hi']) else None,'resample_minus_block_log':cd['estimate'],'resample_minus_block_log_lo':cd['ci_lo'],'noninferiority_rate':nn,'valid_card_rows':len(sub),'unobserved_target_contexts_in_valid_rows':int(sub.unobserved_contexts_used.sum()) if len(sub) else 0})
    return rows