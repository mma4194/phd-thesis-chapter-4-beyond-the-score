"""Portable execution of recovered supplementary methods.

Original cells are called in dependency order. Only path/bootstrap cells are
replaced. Historical controls remain conditional on their original task cards
and licence records, as in the source analysis.
"""
from pathlib import Path
import ast, json, sys, types
import pandas as pd
import numpy as np
from .common import ROOT, code_binding, digest, environment, sha, write_json
from .recalculate import Audit

SOURCE=ROOT/'supplementary_source'

def _execute(ns, group, cell):
    p=SOURCE/group/f'{cell:02d}.py'
    print(f'Supplementary: {group}, cell {cell}',flush=True)
    exec(compile(p.read_text(),str(p),'exec'),ns)

def _context(stage, output, data_file=None, n_jobs=4):
    binding={'code':code_binding(),'environment':environment(),'stage':stage,'n_jobs':n_jobs}
    if data_file:
        path=Path(data_file).expanduser().resolve()
        expected=json.loads((ROOT/'protocols/residential_assets.json').read_text())['raw_dataset_manifest']['source_sha256']
        if not path.is_file() or sha(path)!=expected:
            raise ValueError('Supplementary residential Parquet identity differs or is missing.')
        binding['input_sha256']=expected
    else:path=Path('__RESIDENTIAL_INPUT_NOT_SET__')
    out=Path(output)/digest(binding)[:16]/stage
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/'execution_binding.json',binding)
    module=types.ModuleType('supplementary_'+stage)
    sys.modules[module.__name__]=module; ns=module.__dict__
    imports=(SOURCE/'targeted/01.py').read_text().split('PROJECT_ROOT =')[0]
    exec(compile(imports,str(SOURCE/'targeted/01.py'),'exec'),ns)
    art=ROOT/'provenance/residential_record'
    cfg=json.loads((art/'manifests/effective_config.json').read_text())
    cfg['n_jobs']=int(n_jobs)
    dirs={k:out/k for k in ['manifests','tables','figures','cache','logs','job_state']}
    dirs['root']=out
    for p in dirs.values():p.mkdir(exist_ok=True)
    ns.update(ARTIFACT=art,EVIDENCE_ZIP=art/'evidence.zip',
              CANONICAL_NOTEBOOK=ROOT/'provenance/canonical_cells.json',
              FINAL_ROOT=out.parent,OUT=out,OUTPUT=out,PROJECT_ROOT=ROOT,
              DATASET_PATH=path,CFG=cfg,DIRS=dirs,
              SEEDS=list(map(int,cfg['seeds'])),SEED0=int(cfg['seeds'][0]),
              MODE='real',ROW_LIMIT=0,RUN_FINGERPRINT={},TIER_ALIASES=dict(cfg['tier_aliases']),
              SCHEMA_MANIFEST=json.loads((art/'manifests/schema_and_scopes.json').read_text()),
              TASK_REGISTRY_MANIFEST=json.loads((art/'manifests/task_registry.json').read_text()),
              RUN_C2ST_CAPACITY_DIAGNOSTIC=False,RUN_NEW_EXPERIMENTS=False,
              POSCTRL_SIGMA_IQR={'mild':.02,'strong':.10},TEMP_BLOCK_ROWS=300,
              sha256_file=sha)
    # Rendering an entire 2,000-row table into a child log adds no evidence.
    ns['display']=lambda x:print(x.head(12).to_string(index=False) if isinstance(x,pd.DataFrame) else str(x),flush=True)
    return ns,out

def _compare(a,out,ref,name,keys,columns=None):
    fresh=out/name; old=ref/name
    if not fresh.is_file() or not old.is_file():
        a.check(name+' required output',False,'Missing fresh or reference file');return
    a.compare(name.removesuffix('.csv'),pd.read_csv(fresh),pd.read_csv(old),keys,columns,atol=1e-7,rtol=1e-6)

def temporal_window(path, schema, split, cap=70000):
    """Read the same canonical TEST slice one column at a time.

    The original diagnostic uses only the first 70,000 TEST rows in 155
    protocol fields. Materializing the entire 1,112-column household matrix
    is unnecessary. Float32 conversion and zero replacement are unchanged.
    """
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(path)
    sec=pf.read(columns=['sec']).column(0).to_numpy().astype(np.float64)
    order=np.argsort(sec,kind='stable')
    if not np.isfinite(sec).all() or not np.all(np.diff(sec[order])==1):
        raise ValueError('Temporal diagnostic requires the original one-second chronology.')
    start=int(split['test_start']);stop=min(int(split['test_end']),start+int(cap))
    selected=order[start:stop]
    required=set(schema['feature_scopes']['protocol_value_v3'])
    cols=[c for c in pf.schema_arrow.names if c in required]
    if set(cols)!=required:raise ValueError('Temporal protocol scope differs.')
    data={}
    for c in cols:
        # Conversion precedes replacement, matching the canonical loader.
        with np.errstate(over='ignore',invalid='ignore'):
            values=pf.read(columns=[c]).column(0).to_numpy().astype(np.float32)[selected]
        data[c]=np.nan_to_num(values,nan=0.,posinf=0.,neginf=0.)
    return pd.DataFrame(data),{'test_start':start,'test_stop':stop,'columns':cols,
                              'source_rows':len(sec),'float_dtype':'float32','zero_imputation':True}

def run(stage,output,data_file=None,n_jobs=4,positive_utility=None):
    ns,out=_context(stage,output,data_file,n_jobs)
    ref=ROOT/'reference/supplementary'
    audit=Audit(out/'comparison')
    try:
        if stage=='thresholds':
            for i in [2,4,6,8,10,12,14]:_execute(ns,'threshold_closeout',i)
            audit.check('Original raw/applied P0 states unchanged',int(ns['RAW_DECISIONS'].changed.sum())==0)
            audit.check('Original equal training budgets',ns['SAMPLE_PARITY']['rows_nonparity']==0 and ns['SAMPLE_PARITY']['rows_ntrain_reference_difference']==0)
            audit.check('Original task selection excludes TEST',ns['TASK_AUDIT']['test_used_for_selection']==0 and ns['TASK_AUDIT']['failed_leakage_checks']==0)
        elif stage in {'fixture_audit','classifier_capacity','temporal_controls','canonical_metrics'}:
            _execute(ns,'targeted',4);_execute(ns,'targeted',5)
            if stage=='fixture_audit':
                for i in [7,9,10,21]:_execute(ns,'targeted',i)
                _compare(audit,out,ref/'targeted','WASS2_feature_level.csv',['fixture_seed','severity','feature_name'])
                _compare(audit,out,ref/'targeted','C2ST2_primary_27_rows.csv',['generator_id','scope'])
                _compare(audit,out,ref/'targeted','C2ST2_classifier_selection_sensitivity.csv',['ceiling','selection_rule'])
            elif stage=='classifier_capacity':
                ns['RUN_C2ST_CAPACITY_DIAGNOSTIC']=True;_execute(ns,'targeted',12)
                _compare(audit,out,ref/'targeted','C2ST2_controlled_sample_size_response.csv',['condition','row_cap_total'])
            elif stage=='canonical_metrics':
                # Load the original qualification function, including its decorators.
                src=''.join(ns['CANON_CODE'][3]['source']);tree=ast.parse(src)
                node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='qualify_metrics_on_controlled_fixture')
                piece='\n'.join(src.splitlines()[node.lineno-1:node.end_lineno])
                exec(compile(piece,'canonical_metric_qualification','exec'),ns)
                ns['qualify_metrics_on_controlled_fixture']()
                curve=pd.read_csv(out/'tables/table_controlled_instrument_ladder_seed_level.csv')
                expected=pd.read_csv(ref/'canonical_table_controlled_instrument_ladder_seed_level.csv')
                audit.compare('canonical_metric_curves',curve,expected,['fixture_seed','perturbation','severity'],atol=1e-8,rtol=1e-7)
            else:
                ns['RUN_NEW_EXPERIMENTS']=True
                split=json.loads((ns['ARTIFACT']/'manifests/splits.json').read_text())['primary']
                window,selection=temporal_window(ns['DATASET_PATH'],ns['SCHEMA_MANIFEST'],split)
                ns.update(CANON_DF=window,PRIMARY_SPLIT={'test':np.arange(len(window))},
                          FEATURE_SCOPES={'protocol_value_v3':list(window)})
                write_json(out/'temporal_input_selection.json',selection)
                _execute(ns,'targeted',19)
                _compare(audit,out,ref/'targeted','TEMPCTRL1_temporal_instruments.csv',['condition','seed'])
        elif stage=='positive_controls':
            for i in [2,3,4,5,6,7,8,10,11,12]:_execute(ns,'positive_control',i)
            _compare(audit,out,ref/'positive_control','POSCTRL_V41_utility.csv',
                     ['positive_control_role','positive_control','seed','card_id'],
                     ['status','synthetic_loss','reference_loss','naive_loss','loss_ratio','p0_licensed','n_train','n_reference_train','n_test'])
            _compare(audit,out,ref/'positive_control','POSCTRL_V41_C2ST_summary.csv',['role','control','scope'])
            _compare(audit,out,ref/'positive_control','POSCTRL_V41_capability_summary.csv',['positive_control_role','positive_control','capability'])
        elif stage=='positive_diagnostics':
            if not positive_utility or not Path(positive_utility).is_file():
                raise FileNotFoundError('A completed fresh positive-control utility table is required.')
            ns['V41_UTILITY']=Path(positive_utility);ns['V41_DIR']=Path(positive_utility).parent
            for i in [2,3,4,6,8,10,12]:_execute(ns,'positive_diagnostics',i)
            for name,keys in [
                ('POSCTRL_V42_direct_anchor_c2st_summary.csv',['role','control','scope']),
                ('POSCTRL_V42_perturbation_realisation_summary.csv',['role','control']),
                ('POSCTRL_V42_anchor_relative_utility_summary.csv',['positive_control_role','positive_control'])]:
                _compare(audit,out/'tables',ref/'positive_diagnostics/tables',name,keys)
        else:raise ValueError('Unknown supplementary stage '+stage)
        audit.save('checks',audit.checks)
        status={'execution_status':'COMPLETED','comparison':'PASS' if all(r['passed'] for r in audit.checks) else 'DIFFERENT',
                'checks':len(audit.checks),'failed':sum(not r['passed'] for r in audit.checks),
                'stage':stage,'new_fits':stage in {'classifier_capacity','canonical_metrics','positive_controls','positive_diagnostics'},
                'scope':'Recovered fixed supplementary methods. Historical canonical task/licence records remain explicit inputs.'}
        write_json(out/'status.json',status)
    except BaseException as exc:
        write_json(out/'status.json',{'execution_status':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'ERROR','error':repr(exc),'stage':stage})
        raise
    return out
