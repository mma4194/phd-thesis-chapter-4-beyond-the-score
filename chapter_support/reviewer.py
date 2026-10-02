"""Chapter-reported-result scope. No row filtering based on agreement."""
from pathlib import Path
import csv,hashlib,json,os,subprocess,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
STAGES=('records','canonical_metrics','controlled','input_verification','residential','telemetry','prepare','external')
PUBLIC={'records','controlled','telemetry','prepare','external'}
LABELS={'records':'Recorded arithmetic and headline values','canonical_metrics':'Metric-response experiments','controlled':'72 constructed cases and ablations','input_verification':'Residential input identity','residential':'Residential evaluation','telemetry':'Raw telemetry recovery','prepare':'Raw capture preparation','external':'External evaluation'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def write(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(p)
def checks(path):
 import pandas as pd
 p=Path(path)
 if not p.is_file():raise FileNotFoundError(p)
 d=pd.read_csv(p)
 if d.empty or 'passed' not in d:raise ValueError('Missing comparisons: '+str(p))
 bad=d[~d.passed.astype(str).str.lower().isin(['true','1'])]
 if len(bad):raise ValueError('Chapter comparison differs in '+str(p)+'\n'+bad.to_string(index=False))
 return len(d)
class ChapterRun:
 def __init__(self,mode,output,config=None,decoder_receipt=None):
  if mode not in {'evidence','fresh'}:raise ValueError('Choose evidence or fresh')
  self.mode=mode;self.output=Path(output).expanduser().resolve();self.output.mkdir(parents=True,exist_ok=True);self.rows=[];self.locations={};self.config=config
  write(self.output/'CHAPTER_RESULTS.json',{'mode':mode,'chapter_comparisons':'RUNNING','new_raw_model_run_in_this_execution':mode=='fresh'})
  self.decoder_path=Path(decoder_receipt) if decoder_receipt else ROOT/'evidence/local_decoder_receipt.json'
  self.index=json.loads((ROOT/'evidence/index.json').read_text());self.verify_bundle()
  if mode=='fresh':
   if not config:raise ValueError('Set fresh-run configuration')
   self.config={**config,'profile':'full','run_root':str(self.output/'execution')}
   if self.config.get('workers',0)<1:raise ValueError('workers must be positive')
   for name in ['public_python','residential_python']:
    if not Path(self.config[name]).expanduser().is_file():raise FileNotFoundError(name+': '+self.config[name])
   self.config_path=self.output/'execution/master_config.json'
   if self.config_path.exists() and json.loads(self.config_path.read_text())!=self.config:raise ValueError('Configuration differs from existing run; use a new output folder')
   write(self.config_path,self.config)
 def verify_bundle(self):
  manifest=json.loads((ROOT/'PACKAGE_SHA256.json').read_text())
  bad=[r for r,h in manifest.items() if not (ROOT/r).is_file() or sha(ROOT/r)!=h]
  if bad:raise ValueError('Package integrity differs: '+str(bad[:10]))
 def run(self,stage):
  if stage not in STAGES:raise ValueError('Stage is outside the declared chapter-result scope: '+stage)
  if self.mode=='evidence':
   base=ROOT/'evidence/author_run';r=json.loads((base/self.index[stage]['status']).read_text());out=base/self.index[stage]['output']
  else:
   log=self.output/'logs'/(stage+'.log');log.parent.mkdir(exist_ok=True)
   python=self.config[('public' if stage in PUBLIC else 'residential')+'_python'];env=os.environ.copy();env['MPLBACKEND']='Agg';env['PYTHONUNBUFFERED']='1'
   for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:env[k]='1'
   print(LABELS[stage]+': running. Progress log: '+str(log),flush=True)
   with log.open('w') as stream:
    proc=subprocess.Popen([python,'-m','artifact.stages','--config',str(self.config_path),'--stage',stage],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    try:
     last=time.monotonic()
     while proc.poll() is None:
      time.sleep(1)
      if time.monotonic()-last>=60:print(LABELS[stage]+': running; completed jobs are checkpointed.',flush=True);last=time.monotonic()
    except BaseException:
     proc.terminate()
     try:proc.wait(timeout=15)
     except subprocess.TimeoutExpired:proc.kill();proc.wait()
     raise
   p=Path(self.config['run_root'])/'master_status'/(stage+'.json')
   r=json.loads(p.read_text()) if p.is_file() else {'execution_status':'MISSING_STATUS'}
   if proc.returncode or r.get('comparison')!='PASS':raise RuntimeError('Chapter stage '+stage+' did not pass. '+json.dumps(r)+' Log: '+str(log))
   out=Path(r['output'])
  if r.get('execution_status')!='COMPLETED' or r.get('comparison')!='PASS':raise ValueError('Chapter stage did not pass: '+stage+' '+json.dumps(r))
  # Independently inspect complete comparison files. Never select only matching rows.
  details=[]
  if stage=='records':details.append(checks(out/'checks.csv'))
  if stage in {'residential','controlled','external'}:details.append(checks(out/'paper_comparison/checks.csv'))
  if stage=='canonical_metrics':details.append(checks(out/'comparison/checks.csv'))
  if stage in {'residential','external'}:
   ps=json.loads((out/'prediction_verification/status.json').read_text())
   if not ps.get('passed'):raise ValueError('Saved-prediction verification failed')
  self.locations[stage]=out
  row={'Experiment':LABELS[stage],'Execution':'Previously completed author run' if self.mode=='evidence' else 'Current run','Comparison':'PASS'}
  self.rows=[v for v in self.rows if v['Experiment']!=row['Experiment']]+[row];write(self.output/'progress.json',self.rows)
  return row
 def table(self,stage,relative):
  import pandas as pd
  return pd.read_csv(self.locations[stage]/relative)
 def decoder(self):
  from chapter_support.decoder_receipt import validate_decoder
  receipt=json.loads(self.decoder_path.read_text());r=validate_decoder(receipt)
  row={'Experiment':'Independent decoder: 15 captures / 150,000 packets','Execution':'Separate recorded local execution','Comparison':r['status']};self.rows.append(row);write(self.output/'decoder_evidence.json',{'receipt_sha256':sha(self.decoder_path),**r});return row
 def headline_comparison(self):
  import numpy as np,pandas as pd
  from artifact.recalculate import Audit
  from artifact.common import residential_namespace
  a=Audit(self.output/'headline_arithmetic');a.rns=residential_namespace();a.cfg=a.rns['CFG']
  rr=self.locations['residential'];u=pd.read_csv(rr/'utility_losses.csv');q=pd.read_csv(rr/'corrected_qualification.csv');ad=pd.read_csv(rr/'task_admission.csv')
  a.skills_and_summary(u,q,'residential',ad,True)
  bad=[c for c in a.checks if not c['passed']]
  if bad:raise ValueError('Headline arithmetic failed: '+str(bad))
  a.tables['toniot_utility']=self.table('external','tables/primary_utility_summary.csv').query("axis == 'temporal' and capability == 'network_volume_forecast'").assign(regime='primary')
  claims=json.loads((ROOT/'protocols/paper_headlines.json').read_text());rows=[]
  for claim in claims:
   t=a.tables[claim['table']].query(claim['query'])
   if len(t)!=1:raise ValueError('Nonunique headline: '+claim['id'])
   v=float(t.iloc[0][claim['column']]);places=claim['decimals'];paper=f"{claim['paper_value']:.{places}f}";computed=f'{v:.{places}f}'
   rows.append({'Claim':claim['id'],'Paper':paper,'Recomputed':computed,'Agreement':paper==computed,'Unrounded value':v})
  df=pd.DataFrame(rows);df.to_csv(self.output/'chapter_headline_comparison.csv',index=False)
  if not df.Agreement.all():raise ValueError('Reported chapter values differ; inspect chapter_headline_comparison.csv')
  self.headline_count=len(df);return df
 def finalise(self):
  import pandas as pd
  if set(self.locations)!=set(STAGES):raise ValueError('Required chapter stage missing')
  if not (self.output/'decoder_evidence.json').is_file():raise ValueError('Validate decoder evidence first')
  if not getattr(self,'headline_count',0):raise ValueError('Run the complete headline comparison first')
  d=pd.DataFrame(self.rows);d.to_csv(self.output/'chapter_workflow_comparison.csv',index=False)
  r={'scope':'Declared Chapter 4 experiments and 45 mapped headline values','mode':self.mode,'chapter_comparisons':'PASS','headline_values_checked':self.headline_count,'new_raw_model_run_in_this_execution':self.mode=='fresh','decoder_execution':'Separate recorded local execution','fixed_historical_task_registry':True,'posthoc_extensions_in_scope':False}
  write(self.output/'CHAPTER_RESULTS.json',r)
  with zipfile.ZipFile(self.output/'CHAPTER_RESULTS_TO_RETURN.zip','w',zipfile.ZIP_DEFLATED) as z:
   for p in self.output.rglob('*'):
    if p.is_file() and p.suffix in {'.json','.csv'} and not any(k in p.relative_to(self.output).parts for k in {'cache','jobs','completed_sources','predictions'}):z.write(p,p.relative_to(self.output))
  return d,r
