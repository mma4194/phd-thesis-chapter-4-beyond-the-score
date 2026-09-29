from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np,pyarrow.parquet as pq
import argparse
p=argparse.ArgumentParser();p.add_argument('--input-file',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=Path('results'));args=p.parse_args()
P=args.input_file;R=Path(__file__).resolve().parent/'evidence';O=args.output_dir;O.mkdir(parents=True,exist_ok=True);a=json.loads((R/'archival_assets.json').read_text());pf=pq.ParquetFile(P);checks=[]
def ck(k,v,d=''):checks.append(dict(check=k,passed=bool(v),detail=str(d)))
h=hashlib.sha256()
with P.open('rb') as f:
 for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
ck('input SHA256',h.hexdigest()==a['raw_dataset_manifest']['source_sha256']);ck('stored dimensions',(pf.metadata.num_rows,pf.metadata.num_columns)==(1277694,740))
sec=pf.read(columns=['sec']).column(0).to_numpy();order=np.argsort(sec,kind='stable');sec=sec[order];ck('unique one-second chronology',np.all(np.diff(sec)==1));ck('stored chronological order',np.array_equal(order,np.arange(len(order))))
split=a['splits']['primary'];mm={k:v['indicator'] for k,v in a['missingness']['columns_with_nonfinite'].items() if v['indicator']};rm={v:k for k,v in mm.items()};values=a['schema_and_scopes']['feature_scopes']['all_value_v3'];cards=a['task_registry']['valid_cards']+a['p0_matched_block_plan']['task_model_cards'];required={c for x in cards for c in [x['task']['target'],*x['task']['predictors']]};cols=sorted(set(values)|required|set(a['learned_model_scope']['columns'])|{mm[c] for c in values if c in mm});rawcols=sorted({rm.get(c,c) for c in cols});ck('required input fields',set(rawcols)<=set(pf.schema_arrow.names));ck('working scope',len(cols)==1010 and len(values)==635,f'{len(cols)} working columns; {len(rawcols)} raw source columns')
expected=pd.read_csv(R/'input_value_audit.csv').set_index(['split','feature']);aud=[];maskrows=[];cache={};tasks=json.loads((R/'fixed_task_cards.json').read_text());targets={t['task']['target'] for t in tasks}
for no,c in enumerate(sorted(set(rawcols)|set(mm))):
 raw=pf.read(columns=[c]).column(0).to_numpy().astype(float)[order]
 with np.errstate(over='ignore',invalid='ignore',under='ignore'):v=raw.astype(np.float32)
 finite=np.isfinite(v)
 if c in targets:cache[c]=v
 if c in mm:
  n=int((~np.isfinite(raw)).sum());exp=a['missingness']['columns_with_nonfinite'][c]['count'];ck('registered missing count:'+c,n==exp);maskrows.append(dict(feature=c,missing=n,recorded_missing=exp))
 if c in rawcols:
  for name,lo,hi in [('TRAIN',split['train_start'],split['train_end']),('VAL',split['val_start'],split['val_end']),('TEST',split['test_start'],split['test_end'])]:
   x=raw[lo:hi];f=finite[lo:hi];stats=dict(rows=len(x),missing_nonfinite=int((~np.isfinite(x)).sum()),float32_overflow=int((np.isfinite(x)&~f).sum()),stored_zero=int((np.isfinite(x)&(x==0)).sum()),float32_underflow_to_zero=int((np.isfinite(x)&(x!=0)&f&(v[lo:hi]==0)).sum()))
   e=expected.loc[(name,c)];ck('input diagnostics:'+name+':'+c,all(int(e[k])==val for k,val in stats.items()));aud.append(dict(split=name,feature=c,**stats))
 if (no+1)%100==0:print(no+1,'columns inspected',flush=True)
# Independently count valid real-data target contexts, without fitting predictors.
contexts=pd.read_csv(R/'residential_context_counts.csv');print('context parts',contexts.part.unique(),flush=True)
rows=[];windows=[]
for record in tasks:
 t=record['task'];cid=t['task_id']+'__model_'+record['model_id'];target=cache[t['target']];lag=max(t['lags'],default=0);span=int(t['label_window_steps'] or t['horizon'])
 for period,fit,test in [('same_period',(split['inner_fit_start'],split['inner_fit_end']),(split['inner_calib_start'],split['inner_calib_end'])),('future',(split['train_start'],split['train_end']),(split['test_start'],split['test_end']))]:
  ck('real fit/eval split separation:'+period,fit[1]<=test[0]);
  for part,(lo,hi) in [('real_training',fit),('evaluation',test)]:
   x=target[lo:hi];ok=np.isfinite(x);ix=np.arange(lag,max(lag,len(x)-span));onset=t['task_id'].startswith(('state_transition__','event_onset__')) or t.get('threshold_kind')=='binary_onset'
   if t['task_type']=='classification' and t['label_window_steps']>0:
    start=ix if onset else ix+1;end=ix+span+1;cum=np.r_[0,np.cumsum(~ok)];valid=(cum[end]-cum[start])==0
   else:valid=ok[ix+t['horizon']]
   stats=dict(possible_contexts=len(ix),missing_target_contexts=int((~valid).sum()),available_before_cap=int(valid.sum()));rows.append(dict(card_id=cid,period=period,part=part,**stats))
   old=contexts[(contexts.card_id==cid)&(contexts.period==period)&(contexts.part==part)]
   if len(old):
    ck('real context counts:'+cid+period+part,all((old[k]==v).all() for k,v in stats.items()),f'{len(old)} saved comparisons')
   windows.append(dict(card_id=cid,period=period,part=part,start=lo,end=hi,max_lag=lag,target_span=span,contexts=len(ix),observed_contexts=int(valid.sum()),saved_records=len(old)))
pd.DataFrame(checks).to_csv(O/'checks.csv',index=False);pd.DataFrame(aud).to_csv(O/'input_diagnostics_recomputed.csv',index=False);pd.DataFrame(maskrows).to_csv(O/'registered_missingness_recomputed.csv',index=False);pd.DataFrame(windows).to_csv(O/'real_task_windows.csv',index=False)
summary=dict(sha256=h.hexdigest(),bytes=P.stat().st_size,rows=len(sec),stored_columns=pf.metadata.num_columns,working_columns=len(cols),raw_working_columns=len(rawcols),registered_masks=len(maskrows),registered_missing_cells=sum(r['missing'] for r in maskrows),input_diagnostic_rows=len(aud),real_task_windows=len(windows),windows_with_saved_records=sum(r['saved_records']>0 for r in windows),checks=len(checks),failures=[r for r in checks if not r['passed']],model_fits=0,first_second=int(sec[0]),last_second=int(sec[-1]))
(O/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if summary['failures']: raise SystemExit(1)
