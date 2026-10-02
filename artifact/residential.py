"""Author-only rerun on the withheld residential input.
Frozen task definitions, exact original input SHA256, new model fits and
prediction evidence. No old real-reference loss is imported into this run.
"""
from pathlib import Path
import gc,json,time,warnings
import numpy as np
import pandas as pd
from .common import ROOT,residential_namespace,code_binding,environment,sha,digest,write_json,require_file
class BudgetReached(RuntimeError):pass

def run(data_file,output=None,n_jobs=4,budget_hours=6,recompute_p0=True):
 path=require_file(data_file,'Private residential Parquet');ns=residential_namespace();a=ns['ASSETS']
 h=sha(path)
 if h!=a['raw_dataset_manifest']['source_sha256']:raise ValueError('Residential input SHA256 differs from the paper. No model was fitted.')
 env=environment();expected=json.loads((ROOT/'protocols/residential_environment.json').read_text())['packages']
 mismatch={k:[v,env['packages'].get(k)] for k,v in expected.items() if v!=env['packages'].get(k)}
 if mismatch:raise RuntimeError('Select the residential kernel installed from requirements-residential.txt. Version differences: '+json.dumps(mismatch))
 plan={'input_sha256':h,'code':code_binding(),'environment':env,'n_jobs':int(n_jobs),'recompute_p0':bool(recompute_p0),'scope':'Fresh fits on the fixed recorded task and source protocol; earlier task discovery remains conditional.'}
 base=Path(output) if output else ROOT/'runs/residential';out=base/digest(plan)[:16];out.mkdir(parents=True,exist_ok=True);write_json(base/'latest_run.json',{'path':out.relative_to(base).as_posix()});write_json(out/'protocol.json',plan)
 ns.update(RUN=out,PROTOCOL_HASH=digest(plan),DATA_PATH=path,CFG={**ns['CFG'],'n_jobs':int(n_jobs)},COLS=json.loads((ROOT/'protocols/residential_columns.json').read_text()),VALUE_COLS=a['schema_and_scopes']['feature_scopes']['all_value_v3'],LEARNED_MODEL_COLS=a['learned_model_scope']['columns'],BLOCKS=a['p0_matched_block_plan']['blocks'],PROFILE_COLS=a['p0_matched_block_plan']['profile_columns'])
 ns['MASK_MAP']={k:v['indicator'] for k,v in a['missingness']['columns_with_nonfinite'].items() if v['indicator']};ns['REVERSE_MASK']={v:k for k,v in ns['MASK_MAP'].items()}
 cards=[ns['card_from'](d) for d in json.loads((ROOT/'protocols/residential_cards.json').read_text())]
 # Score evidence is written from actual targets and predictions of this run.
 start=time.monotonic();score_count=0;current={};new_arrays=[]
 oldscore=ns['score_model']
 def score(m,ytrain,X,y,card):
  nonlocal score_count
  d=oldscore(m,ytrain,X,y,card)
  if d['status']=='ok':
   pred=m.predict_proba(X)[:,1] if card.task.task_type=='classification' else m.predict(X)
   meta={'context':dict(current),'card_id':card.card_id,'task_type':card.task.task_type,'loss':d['loss'],'naive_loss':d['naive_loss']}
   key=digest({**meta,**{name:__import__('hashlib').sha256(np.asarray(vals,float).tobytes()).hexdigest() for name,vals in [('prediction_hash',pred),('target_hash',y),('training_target_hash',ytrain)]}})
   p=out/'predictions'/(key+'.npz');p.parent.mkdir(exist_ok=True)
   np.savez_compressed(p,y_train=np.asarray(ytrain,float),y=np.asarray(y,float),prediction=np.asarray(pred,float),metadata=np.array(json.dumps(meta)))
   new_arrays.append(p);score_count+=1
  return d
 ns['score_model']=score
 verified_file_hashes={}
 def verify_file(rel,expected):
  if rel not in verified_file_hashes:verified_file_hashes[rel]=sha(out/rel)
  if verified_file_hashes[rel]!=expected:raise RuntimeError('Prediction evidence changed: '+rel)
 def cache(kind,key,fn):
  if budget_hours is not None and time.monotonic()-start>budget_hours*3600:raise BudgetReached('Time budget reached between jobs; rerun the cell to resume.')
  previous=dict(current);current.clear();current.update(kind=kind,key=key)
  cp=out/'jobs'/kind/(ns['dh'](key)+'.json')
  try:
   if cp.exists():
    record=json.loads(cp.read_text())
    if record.get('protocol')!=ns['PROTOCOL_HASH'] or record.get('key')!=ns['clean'](key) or record.get('payload_hash')!=ns['dh'](record.get('payload')):raise RuntimeError('Job checkpoint differs: '+str(cp))
    if 'prediction_files' not in record:raise RuntimeError('Missing prediction manifest: '+str(cp))
    for rel,hv in record['prediction_files'].items():verify_file(rel,hv)
    return record['payload']
   before=len(new_arrays);payload=ns['clean'](fn())
   # Atomically commit result and its evidence manifest together after all arrays are written.
   proof={p.relative_to(out).as_posix():sha(p) for p in new_arrays[before:]}
   ns['save_json'](cp,{'protocol':ns['PROTOCOL_HASH'],'key':key,'payload':payload,'payload_hash':ns['dh'](payload),'prediction_files':proof})
   return payload
  finally:
   current.clear();current.update(previous)
 ns['cache']=cache
 support_ns={'N':ns,'np':np,'DEFINITIONS':{r['feature']:r for r in json.loads((ROOT/'protocols/residential_field_definitions.json').read_text())}}
 exec(compile((ROOT/'residential_source/support.py').read_text(),str(ROOT/'residential_source/support.py'),'exec'),support_ns)
 affected={'hurdle_iid','hurdle_independent_stitch','hurdle_shared_stitch','learned_gmm_overlay','learned_latent_var_overlay'}
 try:
  with ns['threadpool_limits'](limits=1):
   raw,seconds=ns['load_raw']();ns['revise_thresholds'](raw)
   if recompute_p0:
    admitted=ns['recheck_admission'](raw);plans=ns['profile_and_match'](raw,seconds);q=ns['corrected_qualification'](raw,plans,admitted)
   else:
    adm=pd.read_csv(ROOT/'reference/residential/task_admission.csv');admitted=set(adm.loc[adm.admitted,'card_id']);q=pd.read_csv(ROOT/'reference/residential/corrected_qualification.csv')
   rows=[];checks=[];split=ns['SPLIT']
   for period,fitlo,fithi,testlo,testhi in [('same_period',split['inner_fit_start'],split['inner_fit_end'],split['inner_calib_start'],split['inner_calib_end']),('future',split['train_start'],split['train_end'],split['test_start'],split['test_end'])]:
    train=raw.iloc[fitlo:fithi];test=raw.iloc[testlo:testhi];prepared,impute=ns['generation_inputs'](train)
    ns['save_csv'](out/(period+'_imputation.csv'),impute)
    for spec in a['generator_registry']['generators']:
     source=spec['generator_id']
     for seed in ns['CFG']['seeds']:
      key={'source':source,'period':period,'seed':seed};done=out/'completed_sources'/(digest(key)+'.json')
      if done.exists():
       rec=json.loads(done.read_text());assert rec['protocol']==digest(plan) and rec['payload_hash']==digest(rec['payload'])
       for rel,hp in rec['prediction_files'].items():
        verify_file(rel,hp)
       rows.extend(rec['payload']['rows']);checks.append(rec['payload']['health']);continue
      if budget_hours is not None and time.monotonic()-start>budget_hours*3600:raise BudgetReached('Time budget reached before source fit; rerun the same cell.')
      print(period,source,seed,flush=True);array_start=len(new_arrays)
      try:
       with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always');syn=ns['GENERATOR_FUNCTIONS'][source](prepared,ns['CFG']['generation_rows'],seed,ns['COLS'],spec['params'])
      except ns['ScientificInvalidFit'] as exc:
       healthrow={**key,'source_valid':False,'source_hash':None,'scientific_status':'Fit-Invalid','diagnostics':exc.diagnostics,'reason':str(exc)}
       rr=[{**key,'card_id':c.card_id,'suite':c.task.suite,'capability':c.task.capability,'task_family':c.task.family,'model_id':c.model_id,'source_valid':False,'status':'source_fit_unavailable'} for c in cards]
       payload={'rows':rr,'health':healthrow};write_json(done,{'protocol':digest(plan),'payload':payload,'payload_hash':digest(payload),'prediction_files':{}});rows.extend(rr);checks.append(healthrow);continue
      notes=[{'category':w.category.__name__,'message':str(w.message)} for w in ws]
      assert list(syn)==ns['COLS'] and len(syn)==ns['CFG']['generation_rows']
      health=support_ns['check_output'](train,prepared,syn,source,notes) if source in affected else ns['source_health'](train,prepared,syn,source,notes)
      healthrow={**key,'source_valid':health['source_valid'],'source_hash':ns['frame_digest'](syn),'health':health};rr=[]
      for c in cards:
       ck={**key,'card':c.key(),'source_hash':healthrow['source_hash']}
       rr.append(cache('utility',ck,lambda c=c:ns['utility_card'](train,syn,test,c,seed,source,period,health['source_valid'])))
      payload={'rows':rr,'health':healthrow};write_json(done,{'protocol':digest(plan),'payload':payload,'payload_hash':digest(payload),'prediction_files':{rel:hv for proof in (out/'jobs').rglob('*.json') for rel,hv in json.loads(proof.read_text()).get('prediction_files',{}).items()}});rows.extend(rr);checks.append(healthrow);del syn;gc.collect()
    del prepared;gc.collect()
   losses=pd.DataFrame(rows);ns['save_csv'](out/'utility_losses.csv',losses);ns['save_json'](out/'source_health.json',checks);summ,gaps=ns['summarise_utility'](losses,q,admitted)
  from .recalculate import Audit
  audit=Audit(out/'paper_comparison');r=ROOT/'reference/residential'
  audit.compare('utility_losses',losses,pd.read_csv(r/'utility_losses.csv'),['source','period','seed','card_id'],['reference_loss','synthetic_loss','naive_loss','loss_ratio','status','source_valid','n_train','n_test'],atol=1e-7,rtol=1e-6)
  audit.compare('utility_summary',summ,pd.read_csv(r/'corrected_utility_summary.csv'),['matching','source','suite','period'],['loss_ratio','ci_lo','ci_hi','outcome','complete_support'],atol=1e-7,rtol=1e-6)
  if recompute_p0:audit.compare('qualification',q,pd.read_csv(r/'corrected_qualification.csv'),['arm','suite','capability','clipped'],['final_rule_licensed','reference_skill_lo','block_ratio_hi','resample_minus_block_log_lo'],atol=1e-7,rtol=1e-6)
  audit.save('checks',audit.checks);prediction_check=verify_predictions(out);status={'execution_status':'COMPLETED','paper_comparison':'PASS' if all(x['passed'] for x in audit.checks) else 'DIFFERENT','source_jobs':len(checks),'utility_rows':len(rows),'p0_refitted':recompute_p0,'frozen_task_discovery':True,'new_prediction_files':len(list((out/'predictions').glob('*.npz'))),'private_outputs_do_not_submit':True,'prediction_loss_checks':prediction_check}
 except BudgetReached as exc:status={'execution_status':'PAUSED_TIME_BUDGET','paper_comparison':'INCOMPLETE','reason':str(exc)}
 except BaseException as exc:
  write_json(out/'status.json',{'execution_status':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'ERROR','paper_comparison':'INCOMPLETE','error':repr(exc)});raise
 finally:gc.collect()
 write_json(out/'status.json',status);print(json.dumps(status,indent=2));return out


def verify_predictions(run):
 run=Path(run);records=[]
 for p in sorted((run/'predictions').glob('*.npz')):
  with np.load(p,allow_pickle=False) as a:
   m=json.loads(str(a['metadata']));y=a['y'];tr=a['y_train'];pred=a['prediction']
   if m['task_type']=='classification':loss=np.mean((y-pred)**2);naive=np.mean((y-tr.mean())**2)
   else:
    scale=max(float(np.quantile(y,.75)-np.quantile(y,.25)),1e-6);loss=np.abs(y-pred).mean()/scale;naive=np.abs(y-np.median(tr)).mean()/scale
   records.append({'array':p.name,'card_id':m['card_id'],'loss':float(loss),'naive_loss':float(naive),'passed':bool(np.allclose([loss,naive],[m['loss'],m['naive_loss']],atol=1e-10,rtol=1e-9))})
 out=run/'prediction_verification';out.mkdir(exist_ok=True);df=pd.DataFrame(records);df.to_csv(out/'checks.csv',index=False)
 status={'arrays':len(df),'passed':bool(len(df) and df.passed.all()),'scope':'Fresh score outputs independently recalculated from their saved targets and predictions; no old-array byte claim.'};write_json(out/'status.json',status)
 if not status['passed']:raise AssertionError('Residential prediction evidence missing or inconsistent.')
 return status
