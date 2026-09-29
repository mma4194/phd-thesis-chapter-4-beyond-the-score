"""Compact author comparison report; unfinished newer runs cannot reuse an older PASS."""
from pathlib import Path
import json,zipfile,re
import pandas as pd
from .common import ROOT,write_json,new_output

def pointer(base,name,key='path'):
 p=base/name
 if not p.is_file():return None
 rel=json.loads(p.read_text()).get(key)
 if not rel:return None
 target=(base/rel).resolve()
 if not target.is_relative_to(base.resolve()):raise ValueError('Run pointer escapes its output folder.')
 return target

def result_paths(root=ROOT):
 runs=root/'runs';records=sorted(p for p in (runs/'records').glob('*') if p.is_dir())
 ctl=pointer(runs/'controlled','latest_full.json');res=pointer(runs/'residential','latest_run.json');ton=pointer(runs/'toniot','artifact_workflow.json','run')
 return {'records':records[-1]/'status.json' if records else None,'controlled':ctl/'artifact_status.json' if ctl else None,'residential':res/'status.json' if res else None,'toniot':ton/'paper_comparison/status.json' if ton else None,'predictions':ton/'prediction_verification/status.json' if ton else None,'toniot_execution':ton/'run_status.json' if ton else None}

def report(require_private=True):
 paths=result_paths();requirements=[('Recorded calculations','records','calculation_status','PASS'),('Controlled full experiment','controlled','paper_comparison','PASS'),('TON_IoT fresh evaluation','toniot','paper_comparison','PASS'),('TON_IoT prediction verification','predictions','passed',True)]
 if require_private:requirements.append(('Residential fresh evaluation','residential','paper_comparison','PASS'))
 rows=[];selected=[]
 ep=paths['toniot_execution'];ed=json.loads(ep.read_text()) if ep is not None and ep.is_file() else {}
 if ep is not None and ep.is_file():selected.append(ep)
 for name,kind,key,expected in requirements:
  p=paths[kind];exists=p is not None and p.is_file();d=json.loads(p.read_text()) if exists else {}
  passed=exists and d.get(key)==expected and (kind!='controlled' or d.get('fresh_full_scenario_run') is True) and (kind!='residential' or (d.get('p0_refitted') is True and d.get('prediction_loss_checks',{}).get('passed') is True))
  if kind in {'toniot','predictions'}:passed=passed and ed.get('execution_status')=='PLANNED_JOBS_COMPLETED'
  rows.append({'workflow':name,'status':'MATCH' if passed else ('NOT_RUN' if p is None else 'INCOMPLETE_OR_DIFFERENT'),'result':str(d.get(key,'missing')),'report':p.relative_to(ROOT).as_posix() if p else ''})
  if exists:
   selected.append(p);selected.extend(q for q in p.parent.glob('*.csv') if q.name.endswith(('comparison.csv','checks.csv')))
 table=pd.DataFrame(rows);out=new_output('author_report');table.to_csv(out/'workflow_status.csv',index=False)
 status={'ready_for_author_result_review':all(r['status']=='MATCH' for r in rows),'scope':'Required computational comparisons for the selected current runs only. Not editorial acceptance or population-validity certification.','private_rerun_required':require_private,'workflows':rows};write_json(out/'status.json',status)
 archive=out/'AUTHOR_RESULTS_TO_RETURN.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(set(selected+[out/'workflow_status.csv',out/'status.json'])):
   s=p.read_text(encoding='utf-8');s=re.sub(r'[A-Za-z]:[\\/][^\n\"\']*','<local path>',s);s=re.sub(r'/(?:Users|home|shared|workspace)/[^\n\"\']*','<local path>',s)
   z.writestr(p.relative_to(ROOT/'runs').as_posix(),s)
 print(table.to_string(index=False));print('Compact result report:',archive);return table,archive,status
