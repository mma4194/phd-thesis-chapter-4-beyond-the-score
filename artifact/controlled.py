"""Fresh fixtures, model fits, instruments, P0 and development scenarios."""
from pathlib import Path
import types,sys,json,time,zipfile
from .common import ROOT,code_binding,environment,digest,write_json,sha

def run(profile='full',output=None,metrics_only=False):
 if profile not in {'smoke','full'}:raise ValueError('Use smoke or full.')
 out=Path(output) if output else ROOT/'runs'/'controlled'
 binding={'code':code_binding(),'environment':environment(),'profile':profile}
 base=out;out=out/digest(binding)[:16];pr=out/profile
 if not metrics_only:write_json(base/('latest_'+profile+'.json'),{'path':pr.relative_to(base).as_posix()})
 for f in ['manifests','truth','checkpoints','tables','figure_data','figures','logs','cache']:(pr/f).mkdir(parents=True,exist_ok=True)
 (out/'manifests').mkdir(exist_ok=True);(out/'truth').mkdir(exist_ok=True)
 module=types.ModuleType('tiot_controlled_runtime');sys.modules[module.__name__]=module;ns=module.__dict__
 ns.update(RUN_PROFILE=profile,OUTPUT_ROOT=out,PROFILE_ROOT=pr,EXECUTION_BINDING=binding,BASE_CFG=json.loads((ROOT/'protocols/controlled_config.json').read_text()),CANONICAL_SHA256=sha(ROOT/'controlled_source/canonical_definitions.py'),CANONICAL_P0_DECISION_SHA256=sha(ROOT/'controlled_source/p0_decision.py'),CANONICAL_P0_DECISION_SOURCE=(ROOT/'controlled_source/p0_decision.py').read_text())
 def execute(name):
  p=ROOT/'controlled_source'/name;print('Running',name,flush=True);exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'),ns)
 try:
  execute('step_01.py');execute('step_03.py');execute('canonical_definitions.py')
  import ast
  ns['DEFINITION_AUDIT']=[n.name for n in ast.parse((ROOT/'controlled_source/canonical_definitions.py').read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
  execute('step_06.py')
  ev=pr/'instrument_reference.zip'
  with zipfile.ZipFile(ev,'w') as z:z.write(ROOT/'reference/controlled/table_controlled_instrument_qualification.csv','tables/table_controlled_instrument_qualification.csv')
  ns['EVIDENCE_ZIP']=ev
  execute('step_09.py');execute('step_10.py');execute('step_12.py')
  if not metrics_only:
   for i in [14,15,16,18,19,20,21,23,25,27,28,29]:execute(f'step_{i:02d}.py')
  status={'execution_status':'COMPLETED','profile':profile,'fresh_metrics':profile=='full','fresh_full_scenario_run':profile=='full' and not metrics_only,'scope':'Constructed development cases; not independent validation.','environment':environment()}
  if profile=='full':
   from .recalculate import Audit
   import pandas as pd
   a=Audit(pr/'paper_comparison');m=pr/'stage1_exact/tables'
   a.compare('metric_instruments',pd.read_csv(m/'table_controlled_instrument_qualification.csv'),pd.read_csv(ROOT/'reference/controlled/table_controlled_instrument_qualification.csv'),['instrument','target_perturbation'],['spearman_rho','endpoint_effect','passed'],atol=1e-8,rtol=1e-7)
   if not metrics_only:
    a.compare('development_results',pd.read_csv(pr/'tables/full_protocol_results.csv'),pd.read_csv(ROOT/'reference/controlled/full_protocol_results.csv'),['scenario_id','fixture_seed'],['observed_permission','observed_outcome','observed_failure_stage','utility_geometric_mean_loss_ratio','utility_ci_lo','utility_ci_hi'],atol=1e-7,rtol=1e-6)
    a.compare('development_ablations',pd.read_csv(pr/'tables/stage_ablation_results.csv'),pd.read_csv(ROOT/'reference/controlled/stage_ablation_results.csv'),['scenario_id','fixture_seed','ablation'],['observed_permission','observed_outcome'])
   a.save('checks',a.checks);status['paper_comparison']='PASS' if all(x['passed'] for x in a.checks) else 'DIFFERENT'
  write_json(pr/'artifact_status.json',status);print(json.dumps(status,indent=2));return pr
 except BaseException as exc:
  write_json(pr/'artifact_status.json',{'execution_status':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'ERROR','error':repr(exc),'profile':profile});raise
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--profile',choices=['smoke','full'],default='full');p.add_argument('--metrics-only',action='store_true');a=p.parse_args();run(a.profile,metrics_only=a.metrics_only)
