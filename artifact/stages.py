"""CLI stages used by the single master notebook; no hidden fallback to old runs."""
from pathlib import Path
import argparse, datetime, importlib.metadata as metadata, json, os, subprocess, sys, zipfile
import pandas as pd
from .common import ROOT, sha, digest, environment, write_json, code_binding

ENVIRONMENTS=json.loads((ROOT/'protocols/expected_environments.json').read_text())
PUBLIC={'preflight','history','records','supplementary_audit','controlled','classifier_capacity','telemetry','prepare','decoder','external','report'}
CORE=['preflight','records','controlled','input_verification','residential','telemetry','prepare','decoder','external']
SUPPLEMENT=['thresholds','fixture_audit','canonical_metrics','classifier_capacity','temporal_controls','positive_controls','positive_diagnostics','supplementary_audit']

class Incomplete(RuntimeError):pass

def check_environment(stage):
    group='public' if stage in PUBLIC else 'residential'
    observed=environment();bad={}
    for name,expected in ENVIRONMENTS[group].items():
        try:actual=metadata.version(name)
        except metadata.PackageNotFoundError:actual='missing'
        if actual!=expected:bad[name]={'expected':expected,'actual':actual}
    if bad:raise RuntimeError('Select the pinned '+group+' interpreter. '+json.dumps(bad))
    return observed

def history(out):
    base=ROOT/'validation/author_reference/author_results'
    files=[('record_arithmetic','records/20260921T153200_979364Z/status.json'),
           ('controlled','controlled/cc440df80810281d/full/artifact_status.json'),
           ('residential','residential/e2617436c6c829d7/status.json'),
           ('external','toniot/evaluation/rebuilt_57b58882af399285/paper_comparison/status.json'),
           ('external_predictions','toniot/evaluation/rebuilt_57b58882af399285/prediction_verification/status.json')]
    rows=[]
    for name,rel in files:
        p=base/rel;d=json.loads(p.read_text())
        rows.append({'workflow':name,'evidence_type':'Previously returned verification report',
                     'status':d.get('paper_comparison',d.get('calculation_status',str(d.get('passed')))),
                     'file':str(p.relative_to(ROOT)),'sha256':sha(p),
                     'new_model_execution_here':False,'original_prediction_arrays_bundled':False})
    out.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(out/'previously_verified.csv',index=False)
    write_json(out/'status.json',{'execution_status':'COMPLETED','scope':'Read archived verification reports only','workflows':rows})
    return out

def public_project(config):
    from external_rebuild.project import Project
    return Project(config['toniot_data_root'],output_root=Path(config['run_root'])/'toniot',
                   n_jobs=config['workers'],budget_hours=config['budget_hours'])

def load_project(config):
    from .preparation_integrity import verify
    p=public_project(config)
    pointer=json.loads((p.out/'latest_preparation.json').read_text())
    p.prep=p.out/pointer['path'];p.prep_id=pointer['id']
    verify(p.prep,p.prep_id)
    return p

def _prior(config,stage):
    p=Path(config['run_root'])/'master_status'/(stage+'.json')
    if not p.is_file():raise Incomplete('Run the '+stage+' stage first.')
    r=json.loads(p.read_text())
    if r.get('config_digest')!=digest(config) or r.get('source_digest')!=digest(code_binding()):
        raise Incomplete('The '+stage+' status belongs to a different configuration or source version.')
    if r.get('execution_status')!='COMPLETED' or r.get('comparison') not in {'PASS','ARCHIVED_REPORTS_ONLY','RECORDED_DISCREPANCIES'}:
        raise Incomplete('The '+stage+' stage has not completed successfully.')
    return r

def report(config):
    run=Path(config['run_root']);out=run/'final_report';out.mkdir(parents=True,exist_ok=True)
    expected=['preflight','history','records','supplementary_audit','thresholds','fixture_audit'] if config['profile']=='records' else CORE+SUPPLEMENT
    rows=[]
    for stage in expected:
        p=run/'master_status'/(stage+'.json')
        r=json.loads(p.read_text()) if p.is_file() else {}
        current=r.get('config_digest')==digest(config) and r.get('source_digest')==digest(code_binding())
        complete=current and r.get('execution_status')=='COMPLETED'
        passes=complete and r.get('comparison') in {'PASS','ARCHIVED_REPORTS_ONLY','RECORDED_DISCREPANCIES'}
        rows.append({'stage':stage,'execution':r.get('execution_status','NOT_RUN'),'comparison':r.get('comparison','NOT_RUN'),
                     'current_binding':current,'complete':complete,'passed':passes,'output':r.get('output',''),
                     'evidence_type':r.get('evidence_type','No execution evidence')})
    table=pd.DataFrame(rows);table.to_csv(out/'workflow_comparison.csv',index=False)
    audit_path=run/'supplementary_discrepancies/status.json'
    current_audit=json.loads(audit_path.read_text()) if audit_path.is_file() else {}
    unresolved=not current_audit.get('current_supplementary_records_match',False)
    result={'execution_status':'COMPLETED','profile':config['profile'],
            'selected_workflows_complete':bool(table.complete.all()),'selected_workflow_checks_passed':bool(table.passed.all()),
            'new_full_raw_reproduction_complete':config['profile']=='full' and bool(table.passed.all()),
            'strict_manuscript_agreement':config['profile']=='full' and bool(table.passed.all()) and not unresolved,'supplementary_discrepancies_unresolved':unresolved,
            'reason':'Current supplement targets are checked separately from historical canonical curves; full raw reproduction requires every selected fresh stage.',
            'historical_results_do_not_satisfy_new_runs':True,'environment':environment(),'workflows':rows}
    write_json(out/'status.json',result)
    archive=out/'RESULTS_TO_RETURN.zip'
    selected=[p for p in (run/'master_status').glob('*.json')]
    for r in rows:
        root=Path(r['output']) if r['output'] else None
        if root and root.is_dir():
            for p in root.rglob('*'):
                if not p.is_file() or p.suffix not in {'.json','.csv','.md','.txt','.pdf'}:continue
                if any(x in p.relative_to(root).parts for x in ['arrays','predictions','cache','jobs','checkpoints','completed_sources']):continue
                if p.stat().st_size<25*2**20:selected.append(p)
    selected += [out/'workflow_comparison.csv',out/'status.json']
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(selected)):
            if p.is_relative_to(run):z.write(p,p.relative_to(run))
    print(table.to_string(index=False));print('Result report:',archive)
    return out,result

def execute(config,stage):
    run=Path(config['run_root']);run.mkdir(parents=True,exist_ok=True)
    status_path=run/'master_status'/(stage+'.json')
    base={'stage':stage,'config_digest':digest(config),'source_digest':digest(code_binding()),
          'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution_status':'RUNNING'}
    write_json(status_path,base)
    try:
        base['environment']=check_environment(stage)
        comparison='PASS';scope='New execution in this invocation'
        if stage=='preflight':
            from .preflight import run as check
            out=check(run/'preflight')
        elif stage=='history':
            out=history(run/'history');comparison='ARCHIVED_REPORTS_ONLY';scope='Previously returned author reports, read now'
        elif stage=='records':
            from .recalculate import run as recalc
            from .plots import create,paper_figures
            a=recalc(run/'records');create(a);paper_figures(a);out=a.out
            scope='New arithmetic and plots from archived primitive records; no new model fits'
        elif stage=='supplementary_audit':
            from .supplementary_audit import run as audit
            out=audit(run/'supplementary_discrepancies');comparison='PASS'
            scope='New population and printed-precision comparisons of both archived snapshots'
        elif stage=='input_verification':
            out=run/'residential_input';out.mkdir(exist_ok=True)
            subprocess.run([sys.executable,str(ROOT/'input_verification/verify_residential_input.py'),
                            '--input-file',config['residential_parquet'],'--output-dir',str(out)],check=True,cwd=ROOT)
            scope='New hash, missingness, chronology and context checks on the residential Parquet; no fits'
        elif stage=='controlled':
            from .controlled import run as controlled
            out=controlled('full',output=run/'controlled')
            s=json.loads((out/'artifact_status.json').read_text());comparison=s.get('paper_comparison','INCOMPLETE')
            if not s.get('fresh_full_scenario_run'):raise Incomplete('Full controlled scenarios have not completed.')
        elif stage=='residential':
            _prior(config,'input_verification')
            from .residential import run as residential
            out=residential(config['residential_parquet'],output=run/'residential',n_jobs=config['workers'],budget_hours=config['budget_hours'],recompute_p0=True)
            s=json.loads((out/'status.json').read_text())
            if s.get('execution_status')!='COMPLETED':raise Incomplete(s.get('reason','Residential evaluation incomplete'))
            comparison=s['paper_comparison']
        elif stage=='telemetry':
            from .toniot import verify_telemetry_members
            from external_rebuild.telemetry_recovery import Recovery
            path=Path(config['toniot_data_root'])/'TON_IOT_IOT_DATA.zip'
            out=run/'telemetry_input';out.mkdir(exist_ok=True)
            write_json(out/'member_identity.json',verify_telemetry_members(path))
            recovery=Recovery({'input_root':str(path.parent),'telemetry_input':str(path),'output_root':str(out)})
            recovery.locate();recovery.telemetry();out=recovery.out
            scope='New checks of all 42 raw telemetry members, date recovery and five-second telemetry aggregation'
        elif stage=='prepare':
            from .toniot import prepare
            from .preparation_integrity import verify
            p=prepare(config['toniot_data_root'],output=run/'toniot',n_jobs=config['workers'],budget_hours=config['budget_hours'])
            out=p.prep;base['preparation_verification']=verify(out,p.prep_id)
            scope='New/revalidated raw PCAP and telemetry preparation, immutable tables and frozen input checks'
        elif stage=='decoder':
            _prior(config,'prepare')
            from external_rebuild.crosscheck import run as crosscheck
            p=load_project(config);p.inventory();r=crosscheck(p);out=p.out
            if r.get('status')!='PASS':raise Incomplete('Independent packet cross-check not executed. Install TShark and rerun this stage. The other result files remain available.')
            scope='New independent TShark comparison on the first 10,000 packets of each capture'
        elif stage=='external':
            _prior(config,'prepare')
            from .toniot import evaluate,compare,verify_predictions
            from .preparation_integrity import verify
            p=load_project(config);s=evaluate(p)
            if s.get('execution_status')!='PLANNED_JOBS_COMPLETED':raise Incomplete(s.get('reason','External evaluation incomplete'))
            r=compare(p,raise_on_difference=False);verify_predictions(p.runtime['RUN']);out=p.runtime['RUN']
            base['preparation_verification_after_evaluation']=verify(p.prep,p.prep_id)
            comparison=r['paper_comparison']
        elif stage in SUPPLEMENT:
            from .supplementary import run as supplement
            kwargs={}
            if stage in {'temporal_controls','positive_controls','positive_diagnostics'}:
                _prior(config,'input_verification');kwargs['data_file']=config['residential_parquet']
            if stage=='positive_diagnostics':
                prior=_prior(config,'positive_controls');kwargs['positive_utility']=str(Path(prior['output'])/'POSCTRL_V41_utility.csv')
            out=supplement(stage,run/'supplementary',n_jobs=config['workers'],**kwargs)
            r=json.loads((out/'status.json').read_text());comparison=r['comparison']
            if stage=='thresholds':scope='New arithmetic from original canonical P0 records; separate from corrected P0'
            if stage=='fixture_audit':scope='Fresh Wasserstein fixtures plus 27-row classifier reconstruction from archived metrics'
        elif stage=='report':
            out,r=report(config);comparison='PASS' if r['selected_workflow_checks_passed'] else 'INCOMPLETE'
        else:raise ValueError(stage)
        base.update(execution_status='COMPLETED',comparison=comparison,output=str(Path(out).resolve()),evidence_type=scope,
                    finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_json(status_path,base)
        if comparison in {'DIFFERENT','FAIL','INCOMPLETE'}:
            return 2
        return 0
    except BaseException as exc:
        base.update(execution_status='PAUSED_OR_BLOCKED' if isinstance(exc,Incomplete) else ('INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'ERROR'),comparison='INCOMPLETE',error=repr(exc))
        write_json(status_path,base);raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--stage',required=True)
    args=p.parse_args();config=json.loads(args.config.read_text());raise SystemExit(execute(config,args.stage))
if __name__=='__main__':main()
