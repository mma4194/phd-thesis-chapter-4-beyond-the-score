import numpy as np
import pandas as pd
import math
class RecordMethods:
    def compare(self,name,replayed,saved,keys,columns=None,atol=1e-10,rtol=1e-9):
        a=replayed.copy();b=saved.copy()
        if not self.check(name+'_unique_keys',not a.duplicated(keys).any() and not b.duplicated(keys).any()):return pd.DataFrame()
        common=columns or sorted((set(a)&set(b))-set(keys))
        m=a[keys+common].merge(b[keys+common],on=keys,how='outer',suffixes=('_replay','_saved'),indicator=True,validate='one_to_one')
        self.check(name+'_same_keys',(m._merge=='both').all(),f'{len(m)} joined records')
        dif=[]
        for c in common:
            x=m[c+'_replay'];y=m[c+'_saved'];missing=x.isna()&y.isna()
            if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
                good=np.isclose(x.to_numpy(float),y.to_numpy(float),atol=atol,rtol=rtol,equal_nan=True)
                finite=np.isfinite(x.to_numpy(float))&np.isfinite(y.to_numpy(float));mx=float(np.max(abs(x.to_numpy(float)[finite]-y.to_numpy(float)[finite]))) if finite.any() else 0.
            else:good=(missing|(x.astype(str)==y.astype(str))).to_numpy();mx=None
            dif.append({'quantity':c,'rows':len(m),'mismatches':int((~good).sum()),'max_absolute_error':mx,'atol':atol,'rtol':rtol})
        d=self.save(name+'_comparison',dif);self.check(name+'_values',not d.mismatches.any(),f'{len(d)} quantities compared')
        return d
    def skills_and_summary(self,u,q,label,admission,latest=False):
        expected=set(self.cfg['seeds']);u=u.copy()
        for c in ['reference_loss','synthetic_loss','naive_loss','loss_ratio','log_loss_ratio']:u[c]=pd.to_numeric(u[c],errors='coerce')
        use=np.isfinite(u.naive_loss)&(u.naive_loss>0)&np.isfinite(u.reference_loss)&np.isfinite(u.synthetic_loss)
        u['direct_real_skill']=np.where(use,1-u.reference_loss/u.naive_loss,np.nan)
        u['direct_synthetic_skill']=np.where(use,1-u.synthetic_loss/u.naive_loss,np.nan)
        u['skill_identity_error']=u.direct_synthetic_skill-(1-u.loss_ratio*(1-u.direct_real_skill))
        self.check(label+'_skill_identity',np.nanmax(abs(u.skill_identity_error))<1e-8,'Checked per task with its actual common baseline; not on aggregated scores.')
        self.check(label+'_equal_train_counts',(u.n_train==u.n_reference_train).all())
        self.check(label+'_unique_utility_rows',not u.duplicated(['source','period','seed','card_id']).any())
        self.save(label+'_atomic_loss_and_skill',u)
        summary=[];newskills=[];gaps=[];coverage=[];weights=[]
        admitted=set(admission.loc[admission.admitted,'card_id'])
        for arm in sorted(q.arm.unique()):
            for suite in ['contemporaneous','temporal']:
                caps=set(q.loc[(q.arm==arm)&q.clipped&q.final_rule_licensed&(q.suite==suite),'capability'])
                desired=set(admission.loc[admission.card_id.isin(admitted)&admission.capability.isin(caps)&(admission.suite==suite),'card_id'])
                if not desired:continue
                for source in sorted(u.source.unique()):
                    sub=u[(u.source==source)&u.card_id.isin(desired)];keep=[]
                    for cid,g in sub.groupby('card_id'):
                        ok=g[(g.status=='ok')&g.source_valid.fillna(False)]
                        if len(ok)==2*len(expected) and set(ok.seed)==expected and set(ok.period)=={'same_period','future'}:keep.append(cid)
                    good=sub[sub.card_id.isin(keep)&(sub.status=='ok')&sub.source_valid.fillna(False)]
                    full=len(keep)==len(desired) and set(good.capability)==caps
                    coverage.append({'matching':arm,'source':source,'suite':suite,'expected_cards':len(desired),'complete_cards':len(keep),'complete_support':full,'excluded_card_ids':sorted(desired-set(keep))})
                    for period in ['same_period','future']:
                        x=good[good.period==period]
                        logs=self.rns['balanced_seed_values'](x,'log_loss_ratio') if len(x) else []
                        ci=self.rns['paired_seed_interval'](logs)
                        sr=self.rns['paired_seed_interval'](self.rns['balanced_seed_values'](x,'reference_skill') if len(x) else [])
                        ss=self.rns['paired_seed_interval'](self.rns['balanced_seed_values'](x,'direct_synthetic_skill') if len(x) else [])
                        lo=math.exp(ci['lo']) if ci['lo'] is not None else np.nan;hi=math.exp(ci['hi']) if ci['hi'] is not None else np.nan
                        viable=sr['lo'] is not None and sr['lo']>0
                        outcome=('Noninferior' if hi<=self.cfg['utility_noninferiority_ratio'] else 'Inferior' if lo>self.cfg['utility_noninferiority_ratio'] else 'Inconclusive') if full and viable and np.isfinite(lo) else ('Reference-not-useful' if full and not viable else 'Not-Estimable')
                        key={'matching':arm,'source':source,'suite':suite,'period':period}
                        summary.append({**key,'complete_cards':len(keep),'expected_cards':len(desired),'complete_support':full,'n_seeds':ci['n_seeds'],'real_reference_skill':sr['estimate'],'real_reference_skill_lo':sr['lo'],'real_reference_skill_hi':sr['hi'],'reference_usable_in_period':viable,'loss_ratio':math.exp(ci['estimate']) if ci['estimate'] is not None else np.nan,'ci_lo':lo,'ci_hi':hi,'outcome':outcome})
                        newskills.append({**key,'direct_synthetic_skill':ss['estimate'],'skill_lo':ss['lo'],'skill_hi':ss['hi'],'direct_real_skill':sr['estimate'],'complete_scope':full,'result_version':label,'interpretation':'fixed admitted scope; seed-only conditional interval','baseline':'actual real-training median or class prevalence'})
                        if arm=='balanced_observed':
                            for seed,sg in x.groupby('seed'):
                                nc=sg.capability.nunique()
                                for cap,cg in sg.groupby('capability'):
                                    nf=cg.task_family.nunique()
                                    for fam,fg in cg.groupby('task_family'):
                                        for row in fg.itertuples():weights.append({**key,'seed':seed,'card_id':row.card_id,'capability':cap,'task_family':fam,'weight':1/(nc*nf*len(fg)),'log_ratio_contribution':row.log_loss_ratio/(nc*nf*len(fg))})
                    if len(good):
                        v=good.pivot(index=['seed','capability','task_family','card_id'],columns='period',values=['log_loss_ratio','synthetic_loss','reference_loss'])
                        v=v.dropna();z=v['log_loss_ratio'].copy();z['gap']=z.future-z.same_period
                        ci=self.rns['paired_seed_interval'](self.rns['balanced_seed_values'](z.reset_index(),'gap'))
                        gaps.append({'matching':arm,'source':source,'suite':suite,'gap':ci['estimate'],'ci_lo':ci['lo'],'ci_hi':ci['hi'],'n_seeds':ci['n_seeds']})
        primary_caps=set(q.loc[(q.arm=='balanced_observed')&q.clipped&q.final_rule_licensed,'capability'])
        primary=u[u.card_id.isin(admitted)&u.capability.isin(primary_caps)&u.source_valid.fillna(False)&u.status.eq('ok')]
        if len(primary):
            groups=primary.groupby(['source','period','seed','capability','task_family']).agg(mean_log_ratio=('log_loss_ratio','mean'),direct_real_skill=('direct_real_skill','mean'),direct_synthetic_skill=('direct_synthetic_skill','mean')).groupby(['source','period','seed','capability']).mean().groupby(['source','period','capability']).mean().reset_index()
            groups['loss_ratio']=np.exp(groups.mean_log_ratio);groups['result_version']=label
            groups['interpretation']='Descriptive within-group family-balanced point estimates; no additional qualification or multiplicity claim.'
            self.save(label+'_primary_group_diagnostics',groups)
        self.save(label+'_coverage',coverage);self.save(label+'_weights',weights);self.save(label+'_synthetic_skill',newskills);self.save(label+'_transfer_replay',gaps)
        return self.save(label+'_summary_replay',summary)
