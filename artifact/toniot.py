"""Public-input pipeline and comparison with the reported TON_IoT experiment."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from .common import ROOT,sha,write_json,require_file
from .recalculate import Audit
from external_rebuild.project import Project

def verify_telemetry_members(path):
 from external_rebuild.telemetry_recovery import TelemetrySource
 import hashlib
 source=TelemetrySource(Path(path));rows=[]
 for row in json.loads((ROOT/'protocols/telemetry_members.json').read_text()):
  data=source.read(row['basename']);actual=hashlib.sha256(data).hexdigest()
  rows.append({'name':row['basename'],'sha256':actual,'expected_sha256':row['sha256'],'match':actual==row['sha256'] and len(data)==row['bytes']})
 if len(rows)!=42 or not all(r['match'] for r in rows):raise ValueError('Telemetry member bytes differ from the paper. Exact content of all 42 members is required.')
 return rows

def prepare(data_root,output=None,n_jobs=4,budget_hours=6):
 data_root=Path(data_root).expanduser().resolve()
 if not data_root.is_dir():raise FileNotFoundError('Set DATA_ROOT to the folder containing TON_IOT_IOT_DATA.zip and pcap_files/.')
 p=Project(data_root,output_root=Path(output) if output else ROOT/'runs/toniot',n_jobs=int(n_jobs),budget_hours=(None if budget_hours is None else float(budget_hours)))
 write_json(p.out/'artifact_workflow.json',{'phase':'PREPARING','run':None})
 p.phase('Input inventory',p.inventory)
 # Hash every raw file before fitting. Archive repackaging also changes the archive hash;
 # an equivalent repackaging is accepted only after all 42 member hashes match.
 expected=json.loads((ROOT/'reference/toniot/preparation_protocol.json').read_text())['input_files']
 actual=[]
 for row in expected:
  f=p.telemetry_input if row['role']=='telemetry' else p.captures[Path(row['name']).stem]
  h=sha(f)
  same=h==row['sha256'];basis='exact file bytes'
  if row['role']=='telemetry':
   members=verify_telemetry_members(f);write_json(p.out/'telemetry_member_comparison.json',members)
   if not same:same=True;basis='all 42 member bytes identical; archive packaging differs'
  actual.append(dict(name=row['name'],sha256=h,expected_sha256=row['sha256'],match=same,basis=basis))
 write_json(p.out/'input_identity_comparison.json',actual)
 if not all(r['match'] for r in actual):raise ValueError('Raw-input identity differs from the paper. Inspect input_identity_comparison.json; do not lower comparison thresholds.')
 p.phase('Decoder software checks',p.software_checks)
 p.phase('Telemetry and packet preparation',p.prepare)
 V,M,S,H=p.load_prepared()
 if V.shape!=(28752,64):raise AssertionError(f'Prepared shape differs: {V.shape}; expected (28752,64).')
 if not np.all(np.diff(S)==5):raise AssertionError('Prepared time grid differs.')
 comp=[]
 for name,h in json.loads((ROOT/'reference/toniot/prepared_files.json').read_text()).items():
  if name.endswith('.csv.gz') and name.startswith(('TON_IoT','general_','iot_named_','telemetry_observed')):
   comp.append({'file':name,'sha256':sha(p.prep/name),'expected_sha256':h,'exact_bytes_match':sha(p.prep/name)==h})
 write_json(p.out/'prepared_table_comparison.json',comp)
 from .prepared_content import verify_prepared
 content_check=verify_prepared(p.prep,p.out/'prepared_content_comparison.json')
 print('Prepared content: PASS (all six tables; exact fields and at most one ULP in packet-length standard deviations).',flush=True)
 from .preparation_integrity import freeze
 freeze(p.prep,p.out,p.prep_id)
 write_json(p.out/'artifact_workflow.json',{'phase':'PREPARED','run':None,'preparation':p.prep_id})
 return p

def evaluate(p):
 from .preparation_integrity import verify
 verify(p.prep,p.prep_id)
 write_json(p.out/'artifact_workflow.json',{'phase':'EVALUATING','run':None,'preparation':p.prep_id})
 try:
  return p.phase('Evaluation',p.evaluate)
 finally:
  run=p.runtime.get('RUN') if p.runtime else None
  write_json(p.out/'artifact_workflow.json',{'phase':'EVALUATION_RETURNED','run':run.relative_to(p.out).as_posix() if run else None,'preparation':p.prep_id})

def compare(p,raise_on_difference=True):
 if p.runtime is None or 'RUN' not in p.runtime:raise RuntimeError('Evaluation has not run.')
 run=p.runtime['RUN'];status=json.loads((run/'run_status.json').read_text())
 if status.get('execution_status')!='PLANNED_JOBS_COMPLETED':raise RuntimeError('Evaluation incomplete or contains execution errors: '+json.dumps(status))
 a=Audit(run/'paper_comparison');ref=ROOT/'reference/toniot'
 for name in ['primary','roll0','roll1','roll2']:
  schemas=[('task_admission',['task_id'],['admitted','reason','threshold','n_train','n_validation','loss','reference_skill']),('qualification',['axis','capability','unclipped'],['eligible','licensed','state','reference_skill_lo','block_ratio_hi','relative_log_difference_lo','noninferiority_rate']),('qualification_unclipped',['axis','capability','unclipped'],['eligible','licensed','state']),('utility_rows',['source','seed','task_id','period'],['status','permission','real_loss','synthetic_loss','naive_loss','n_real_train','n_synthetic_train','n_test']),('utility_summary',['source','axis','capability','period'],['permission','outcome','loss_ratio','lo','hi','common_reportable_tasks']),('transfer_summary',['source','axis','capability'],['estimate','lo','hi','outcome']),('C2ST_summary',['source','period','scope'],['resolution_available','secondary_resolution_available','candidate_max_AUC','anchor_max_AUC','P0_max_AUC','excess_AUC','excess_lo','excess_hi'])]
  for tag,keys,cols in schemas:
   a.compare(name+'_'+tag,pd.read_csv(run/'tables'/f'{name}_{tag}.csv'),pd.read_csv(ref/f'{name}_{tag}.csv'),keys,cols,atol=1e-7,rtol=1e-6)
 a.compare('source_contracts',pd.read_csv(run/'tables/source_checks.csv'),pd.read_csv(ref/'source_checks.csv'),['regime','source','seed'],['execution_status','contract_state','contract_valid','support_violation'],atol=1e-7,rtol=1e-6)
 a.save('checks',a.checks);result={'execution_status':'COMPLETED','paper_comparison':'PASS' if all(c['passed'] for c in a.checks) else 'DIFFERENT','checks':len(a.checks),'failed':sum(not c['passed'] for c in a.checks)};write_json(run/'paper_comparison/status.json',result)
 if result['failed'] and raise_on_difference:raise AssertionError('Fresh TON_IoT results differ. Inspect paper_comparison/checks.csv and comparison tables.')
 return result

def verify_predictions(run):
 run=Path(run);rows=[]
 for name in ['primary','roll0','roll1','roll2']:
  for kind in ['utility','P0']:
   d=pd.read_csv(run/'tables'/f"{name}_{kind}_{'rows' if kind=='utility' else 'losses'}.csv");cards=pd.read_csv(run/'tables'/f'{name}_task_admission.csv').set_index('task_id')
   for r in d.to_dict('records'):
    if not np.isfinite(r.get('real_loss',np.nan)):continue
    prefix=f"{name}__{r['source']}__{int(r['seed'])}" if kind=='utility' else f"p0_{name}_{r['pair_id']}_{int(r['seed'])}_{r['anchor']}"
    path=run/'arrays'/(prefix+'__'+r['task_id']+'.npz');a=np.load(path,allow_pickle=False);period=r['period'];y=a[period+'_y'];real=a[period+'_real_prediction'];syn=a[period+'_synthetic_prediction'];train=a['real_training_y']
    if cards.loc[r['task_id'],'task_type']=='regression':
     scale=max(float(np.quantile(y,.75)-np.quantile(y,.25)),1e-6);vals=[np.abs(y-real).mean()/scale,np.abs(y-syn).mean()/scale,np.abs(y-np.median(train)).mean()/scale]
    else:vals=[np.mean((y-real)**2),np.mean((y-syn)**2),np.mean((y-train.mean())**2)]
    ok=bool(np.allclose(vals,[r['real_loss'],r['synthetic_loss'],r['naive_loss']],atol=1e-10,rtol=1e-9))
    rows.append(dict(regime=name,kind=kind,array=path.name,period=period,passed=ok,real_loss=vals[0],synthetic_loss=vals[1],naive_loss=vals[2]))
    a.close()
 out=run/'prediction_verification';out.mkdir(exist_ok=True);d=pd.DataFrame(rows);d.to_csv(out/'loss_checks.csv',index=False)
 status={'loss_comparisons':len(d),'expected':8508,'passed':len(d)==8508 and bool(d.passed.all()),'model_fits':0};write_json(out/'status.json',status)
 if not status['passed']:raise AssertionError('Prediction checks differ; inspect prediction_verification/.')
 return status
