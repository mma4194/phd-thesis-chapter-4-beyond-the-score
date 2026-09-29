"""Recalculate statistics from included task losses and seed-level responses.
This path fits no model and does not claim to recover predictions from losses.
"""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .common import ROOT,new_output,write_json,environment,residential_namespace,public_namespace
from .record_methods import RecordMethods
class Audit(RecordMethods):
 def __init__(self,out):
  self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True);self.tables={};self.checks=[]
 def check(self,name,ok,detail='',severity='FAIL'):
  self.checks.append({'check':name,'passed':bool(ok),'detail':str(detail)});return bool(ok)
 def save(self,name,rows):
  d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows);self.tables[name]=d;d.to_csv(self.out/(name+'.csv'),index=False);return d
 def residential(self):
  r=ROOT/'reference/residential';self.rns=residential_namespace();self.cfg=self.rns['CFG']
  raw=pd.read_csv(r/'P0_losses.csv');parts=[]
  self.check('Residential P0 distinct observations',not raw.duplicated(['source_block','target_block','seed','card_id','p0_anchor']).any())
  for arm in ['balanced_observed','original_pairs','prior_observed_pairs']:
   plan=pd.read_csv(r/f'matching_{arm}.csv');blocks=[]
   self.check('Disjoint pair sets '+arm,plan.source_block.is_unique and plan.target_block.is_unique and set(plan.source_block).isdisjoint(plan.target_block))
   for p in plan.itertuples():
    x=raw[(raw.source_block==p.source_block)&(raw.target_block==p.target_block)].copy();x['pair_id']=p.pair_id;x['phase']=p.phase;x['matching']=arm;blocks.append(x)
   x=pd.concat(blocks,ignore_index=True)
   for clipped in [True,False]:parts+=self.rns['qualify'](x,arm,clipped)
  q=pd.DataFrame(parts).rename(columns={'historical_rule_licensed':'without_reference_skill_check'});self.save('residential_P0',q)
  self.compare('residential_P0',q,pd.read_csv(r/'corrected_qualification.csv'),['arm','suite','capability','clipped'])
  u=pd.read_csv(r/'utility_losses.csv');ad=pd.read_csv(r/'task_admission.csv')
  valid=u.status.eq('ok');self.check('Residential log ratios derived from primitive losses',np.allclose(np.log(np.maximum(u.loc[valid,'synthetic_loss']/u.loc[valid,'reference_loss'],1e-12)),u.loc[valid,'log_loss_ratio'],atol=1e-10,rtol=1e-9))
  self.check('Residential expected utility records',len(u)==3060 and u.source.nunique()==9 and u.card_id.nunique()==34)
  summary=self.skills_and_summary(u,q,'residential',ad,True)
  self.compare('residential_utility',summary,pd.read_csv(r/'corrected_utility_summary.csv'),['matching','source','suite','period'])
  self.compare('residential_transfer',self.tables['residential_transfer_replay'],pd.read_csv(r/'corrected_transfer_summary.csv'),['matching','source','suite'])
  self.check('Residential primary supported groups',q.query("arm == 'balanced_observed' and clipped and final_rule_licensed").suite.value_counts().to_dict()=={'contemporaneous':3})
  self.check('Residential primary temporal groups withheld',len(q.query("arm == 'balanced_observed' and clipped and eligible and suite == 'temporal'"))==7)
  return summary.query("matching == 'balanced_observed' and period == 'future'")
 def toniot(self):
  r=ROOT/'reference/toniot';ns=public_namespace();protocol=json.loads((r/'protocol.json').read_text());allsummary=[];skills=[]
  for reg in protocol['regimes']:
   name=reg['name'];ad=pd.read_csv(r/f'{name}_task_admission.csv');cards=ad[ad.admitted].to_dict('records');p0=pd.read_csv(r/f'{name}_P0_losses.csv')
   for unclipped in [False,True]:
    q=pd.DataFrame(ns['p0_decisions'](p0.to_dict('records'),cards,unclipped));ref=pd.read_csv(r/(name+'_qualification'+('_unclipped' if unclipped else '')+'.csv'))
    self.compare('toniot_'+name+'_P0_'+str(unclipped),q,ref,['axis','capability','unclipped']);self.save('toniot_'+name+'_P0_'+str(unclipped),q)
   u=pd.read_csv(r/f'{name}_utility_rows.csv');rows=[];gaps=[]
   self.check(name+' unique utility observations',not u.duplicated(['source','seed','task_id','period']).any())
   good=u[u.status.eq('ok')]
   self.check(name+' observed equal training counts',(good.n_real_train==good.n_synthetic_train).all())
   self.check(name+' log ratios from losses',np.allclose(np.log(np.maximum(good.synthetic_loss/good.real_loss,1e-12)),good.log_ratio,atol=1e-10,rtol=1e-9))
   for (source,axis,cap),g in u.groupby(['source','axis','capability']):
    keep=[]
    for tid,tg in g.groupby('task_id'):
     if len(tg)==2*len(reg['evaluation_seeds']) and set(tg.seed)==set(reg['evaluation_seeds']) and set(tg.period)=={'near','future'} and tg.permission.eq('Admissible').all():keep.append(tid)
    x=g[g.task_id.isin(keep)].copy()
    if x.empty:continue
    x['direct_skill']=1-x.synthetic_loss/x.naive_loss
    for period,pp in x.groupby('period'):
     vals=lambda v:pp.groupby(['seed','family'])[v].median().groupby('seed').mean().reindex(reg['evaluation_seeds'])
     ci=ns['seed_interval'](vals('log_ratio'),811);sc=ns['seed_interval'](vals('reference_skill'),814);sy=ns['seed_interval'](vals('direct_skill'),814)
     key=dict(regime=name,source=source,axis=axis,capability=cap,period=period)
     rows.append(dict(**key,loss_ratio=np.exp(ci['estimate']),lo=np.exp(ci['lo']) if ci['lo'] is not None else np.nan,hi=np.exp(ci['hi']) if ci['hi'] is not None else np.nan,common_reportable_tasks=len(keep),n_seeds=ci['n_seeds'],period_reference_skill=sc['estimate'],period_reference_skill_lo=sc['lo'],period_reference_skill_hi=sc['hi']))
     skills.append(dict(**key,skill=sy['estimate'],lo=sy['lo'],hi=sy['hi']))
    v=x.pivot(index=['seed','family','task_id'],columns='period',values='log_ratio');v['gap']=v.future-v.near;v=v.reset_index();ci=ns['seed_interval'](v.groupby(['seed','family']).gap.median().groupby('seed').mean().reindex(reg['evaluation_seeds']),812)
    gaps.append(dict(source=source,axis=axis,capability=cap,**ci))
   now=pd.DataFrame(rows);expected=pd.read_csv(r/f'{name}_utility_summary.csv');self.compare('toniot_'+name+'_utility',now,expected[expected.loss_ratio.notna()],['regime','source','axis','capability','period']);allsummary.extend(rows)
   self.compare('toniot_'+name+'_transfer',pd.DataFrame(gaps),pd.read_csv(r/f'{name}_transfer_summary.csv'),['source','axis','capability'],['estimate','lo','hi','n_seeds'])
   # Resolution is checked against measured anchor and candidate AUCs, including the self-comparison exception.
   c=pd.read_csv(r/f'{name}_C2ST_summary.csv');resolved=(c.P0_max_AUC<.995)&(c.candidate_max_AUC<.995)&(c.anchor_max_AUC<.995)
   self.check(name+' classifier resolution rule',np.array_equal(resolved,c.resolution_available))
  self.save('toniot_utility',allsummary);sk=self.save('toniot_direct_skill',skills)
  self.compare('toniot_direct_skill_primary',sk[sk.regime=='primary'].drop(columns=['regime','axis','capability']),pd.read_csv(r/'recomputed_direct_skill.csv'),['source','period'],['skill','lo','hi'])
  src=pd.read_csv(r/'source_checks.csv');self.check('TON_IoT expected 72 source jobs',len(src)==72 and not src.duplicated(['regime','source','seed']).any());self.check('TON_IoT source health counts',int(src.contract_valid.sum())==56 and (~src.contract_valid).sum()==16);self.check('TON_IoT execution completed',src.execution_status.eq('completed').all())
  return self.tables['toniot_utility'].query("regime == 'primary' and period == 'future'")
 def controlled(self):
  r=ROOT/'reference/controlled';curve=pd.read_csv(r/'table_controlled_instrument_ladder_seed_level.csv');expected=pd.read_csv(r/'table_controlled_instrument_qualification.csv');rows=[]
  for e in expected[expected.target_perturbation!='none'].itertuples():
   y=curve[curve.perturbation==e.target_perturbation].groupby('severity')[e.instrument].mean().sort_index();rho=float(spearmanr(y.index,y.values).statistic);effect=float(y.iloc[-1]-y.iloc[0]);rows.append(dict(instrument=e.instrument,target_perturbation=e.target_perturbation,spearman_rho=rho,endpoint_effect=effect,passed=np.isfinite(rho) and rho>=e.threshold and effect>e.minimum_endpoint_effect))
  self.compare('metric_responses',pd.DataFrame(rows),expected[expected.target_perturbation!='none'],['instrument','target_perturbation'],['spearman_rho','endpoint_effect','passed']);self.save('metric_responses',rows)
  d=pd.read_csv(r/'full_protocol_results.csv');self.check('72 controlled scenario/fixture observations',len(d)==72 and not d.duplicated(['scenario_id','fixture_seed']).any())
  # Reapply precedence from independently stored gate outputs; expected labels are not used as inputs.
  observed=np.select([~d.instrument_valid,~(d.stage2_estimable & (~d.claim_kind.eq('closeness') | d.resolution_available)),~d.stage3_property_licensed,~d.source_valid],['INSTRUMENT_INVALID','NOT_ESTIMABLE','PROPERTY_UNLICENSED','SOURCE_INVALID'],default='ADMISSIBLE')
  observed=np.where((observed=='SOURCE_INVALID')&d.source_failure_type.eq('FIT_INVALID'),'FIT_INVALID',observed)
  self.check('Controlled decision precedence',np.array_equal(observed,d.observed_permission))
  self.check('Controlled development-label agreement',(d.expected_permission==observed).all() and (d.expected_outcome==d.observed_outcome).all())
  a=pd.read_csv(r/'stage_ablation_results.csv');a['accepted_withheld']=a.expected_permission.ne('ADMISSIBLE')&a.observed_permission.eq('ADMISSIBLE');summ=a.groupby('ablation').agg(cases=('scenario_id','size'),accepted_withheld=('accepted_withheld','sum')).reset_index();self.save('controlled_ablation_counts',summ)
  return summ
 def headlines(self):
  claims=json.loads((ROOT/'protocols/paper_headlines.json').read_text());rows=[]
  for c in claims:
   d=self.tables[c['table']].query(c['query']);ok=len(d)==1
   value=float(d.iloc[0][c['column']]) if ok else np.nan
   rendered=f"{value:.{c['decimals']}f}";expected=f"{c['paper_value']:.{c['decimals']}f}"
   match=ok and rendered==expected;self.check('Paper headline '+c['id'],match,rendered+' vs '+expected)
   rows.append({**c,'recalculated_value':value,'printed_value':rendered,'matched':match})
  self.save('paper_headline_comparison',rows)
  w=pd.read_csv(ROOT/'reference/residential/Wasserstein_sparse_feature_contribution.csv')
  self.check('Wasserstein IQR floor operands',np.allclose(w.denominator_used,np.maximum(w.reference_iqr,w.denominator_floor)))
  self.check('Wasserstein feature-normalized values',np.allclose(w.wasserstein_iqr_normalised,w.wasserstein_raw/w.denominator_used))
  end=w[w.severity==1].groupby('feature_name').wasserstein_iqr_normalised.mean();share=end.max()/end.sum()
  self.check('Sparse feature share prints as 99.83 percent',f'{100*share:.2f}'=='99.83')
  return rows
 def finish(self):
  d=self.save('checks',self.checks);status={'execution_status':'COMPLETED','calculation_status':'PASS' if d.passed.all() else 'FAIL','checks':len(d),'failed':int((~d.passed).sum()),'model_fits':0,'scope':'Recalculation from saved task losses, gate inputs and metric responses. Predictions and raw-input fits are separate workflows.','environment':environment()};write_json(self.out/'status.json',status)
  if not d.passed.all():raise AssertionError(f"{status['failed']} checks differ; inspect {self.out/'checks.csv'}")
  return status

def run(out=None):
 a=Audit(out or new_output('records'))
 try:
  print('Residential losses and P0 ...',flush=True);a.residential();print('TON_IoT losses and P0 ...',flush=True);a.toniot();print('Controlled responses and decisions ...',flush=True);a.controlled();a.headlines();status=a.finish()
 except BaseException as exc:
  a.save('checks',a.checks);write_json(a.out/'execution_error.json',{'error':repr(exc),'scope':'record recalculation'});raise
 print(json.dumps(status,indent=2));print('Results:',a.out);return a
if __name__=='__main__':run()
