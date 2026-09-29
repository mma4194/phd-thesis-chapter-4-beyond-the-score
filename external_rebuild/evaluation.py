"""Recovered corrected evaluation with explicit new-data adapters.

The recovered modules are retained unchanged. Their historical hash/row-count
guards are not used to certify new data. This entry point has its own prepared-
input validation, protocol identity, chronological splits and fresh TRAIN P0.
"""
from __future__ import annotations
import ast, json, math, time, traceback
from pathlib import Path
import numpy as np
import pandas as pd
from .project import ROOT, code_manifest
from .telemetry_recovery import file_hash, json_write

MODULES=['runtime_core','canonical_metrics','matching_helpers','legacy_generators',
         'statistics_helpers','runtime_protocol','runtime_tasks','runtime_c2st',
         'runtime_p0','runtime_evaluation','runtime_checks']
ADAPTATIONS=[
 {'item':'Data identity','change':'New preparation hashes and rules; no recovered historical row-count/hash certification.'},
 {'item':'Calendar interval','change':'Longest common observed session; whole 5 s bins; no historical target row count.'},
 {'item':'Splits','change':'Recalculate the recovered 60/20/20 primary fractions after two 25-row embargoes; rolling TRAIN 45/50/55% with 15% near and future blocks and the same embargoes.'},
 {'item':'P0','change':'Use the recovered origin-local TRAIN-only matching for ALL four origins, including primary. No old pair indices or availability flags are reused.'},
 {'item':'Real sampling anchors','change':'Preserve observation masks on resampled/contiguous real targets. Their zero-imputed missing targets do not become measured labels.'},
 {'item':'Generators','change':'All nine value-generating algorithms and settings retained; no new architecture search.'},
 {'item':'Masks','change':'Missing real targets excluded. Real predictors retain zero imputation. Generated value outputs have no learned missingness model.'},
 {'item':'Claims','change':'Scientific interpretation conditional on available capture prefixes, stated clock convention and prior task exposure. Failed instruments/contracts and Not-Estimable outcomes are retained.'},
 {'item':'Runtime','change':'Save each completed job, stop between jobs at the operational time budget, resume with identical inputs/code/environment/settings.'},
]

class TimeBudgetReached(RuntimeError): pass

def plan_regimes(n,cfg):
    embargo=25;usable=n-2*embargo;nt=int(.6*usable);nv=int(.2*usable)
    out=[{'name':'primary','train':(0,nt),'near':(nt+embargo,nt+embargo+nv),
          'future':(nt+2*embargo+nv,n),'evaluation_seeds':cfg['seeds']}]
    for i,frac in enumerate([.45,.50,.55]):
        end=int(frac*n);width=int(.15*n);v0=end+embargo;v1=v0+width
        out.append({'name':f'roll{i}','train':(0,end),'near':(v0,v1),'future':(v1+embargo,v1+embargo+width),'evaluation_seeds':[cfg['seeds'][0]]})
    for r in out:
        end=r['train'][1];inner=int(end*(1-cfg['inner_selection_fraction']))
        r.update(selection_fit=(0,inner),selection_validation=(inner+embargo,end),output_rows=r['near'][1]-r['near'][0])
        for key in ['train','near','future','selection_fit','selection_validation']:
            a,b=r[key]
            if not 0<=a<b<=n or b-a<=2*cfg['min_rows']:raise ValueError('Insufficient rows for the declared split: '+r['name']+'/'+key)
    return out

def runtime(project):
    ns={'__name__':'tiot_reconstructed_runtime','N_JOBS':project.n_jobs,'OUTPUT_ROOT':project.out/'evaluation'}
    source_root=ROOT/'external_rebuild'/'recovered'
    ns['ASSETS']=json.loads((source_root/'historical_assets.json').read_text(encoding='utf-8'))
    snapshot={x:(source_root/(x+'.py')).read_text(encoding='utf-8') for x in MODULES}
    ns['LEGACY_GENERATOR_SOURCE']=snapshot['legacy_generators']
    for module in MODULES:exec(compile(snapshot[module],str(source_root/(module+'.py')),'exec'),ns)
    # The only branch removed is the old primary-pair lookup, which is inapplicable to new input rows.
    node=next(n for n in ast.parse(snapshot['runtime_p0']).body if isinstance(n,ast.FunctionDef) and n.name=='select_p0_pairs')
    branches=[n for n in node.body if isinstance(n,ast.If) and ast.unparse(n.test)=="regime['name'] == 'primary'"]
    if len(branches)!=1:raise RuntimeError('Recovered P0 source differs from the reviewed adapter')
    node.body.remove(branches[0]);module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
    exec(compile(module,'reconstruction_fresh_P0.py','exec'),ns)
    # Propagate real-anchor observation masks while retaining byte-identical sampled values.
    exec('''def reconstructed_row_resample(X,n,rng):
    idx=rng.integers(0,len(X),size=n)
    return X[idx].copy(),{'sample_indices_preview':idx[:100].tolist(),'sample_indices':idx.tolist()}
''',ns)
    ns['GEN_FUNCS']['real_row_resample']=ns['reconstructed_row_resample']
    src=snapshot['runtime_evaluation'];tree=ast.parse(src)
    fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='source_job')
    job='\n'.join(src.splitlines()[fun.lineno-1:fun.end_lineno])
    old="key=f\"{regime['name']}__{source}__{seed}\""
    new="""syn_observed=None
    if source=='real_row_resample':syn_observed=realobs[np.asarray(meta['sample_indices'],dtype=int)]
    elif source=='real_contiguous_block':syn_observed=realobs[int(meta['base_start']):int(meta['base_start'])+len(syn)]
    key=f"{regime['name']}__{source}__{seed}"
"""
    if job.count(old)!=1:raise RuntimeError('Recovered source job differs from adapter')
    job=job.replace(old,new).replace('paired_task_fit(real,realobs,syn,c,seed,tests,key)','paired_task_fit(real,realobs,syn,c,seed,tests,key,syn_observed=syn_observed)')
    exec(compile(job,'reconstruction_anchor_masks.py','exec'),ns)
    tasks=snapshot['runtime_tasks'];node=next(n for n in ast.parse(tasks).body if isinstance(n,ast.FunctionDef) and n.name=='paired_task_fit')
    fun='\n'.join(tasks.splitlines()[node.lineno-1:node.end_lineno])
    fun=fun.replace("xr,yr,ri=examples(real,real_observed,card,(0,len(real)))", "mask_policy='propagated real-source observation mask' if syn_observed is not None else 'complete generated value view; no generated-mask claim'\n    xr,yr,ri=examples(real,real_observed,card,(0,len(real)))")
    fun=fun.replace("'synthetic_target_observation_policy':'finite complete value output. Missingness generation is outside this run.'","'synthetic_target_observation_policy':mask_policy")
    exec(compile(fun,'reconstruction_mask_description.py','exec'),ns)
    ns['NOTEBOOK_SOURCE_SNAPSHOT']={**snapshot,'adaptations':ADAPTATIONS,'source_manifest':code_manifest()}
    ns['OUTPUT_ROOT'].mkdir(parents=True,exist_ok=True);return ns

def initialise(project,ns,hashes,regimes):
    plan={'study':'TON_IoT external validation rebuilt from raw sources','version':'2.0.0',
          'historical_byte_reproduction':False,'independent_confirmation':False,
          'preparation_status':project.prep_report,'data_hashes':hashes,'source_manifest':code_manifest(),
          'environment':ns['environment_record'](),'settings':ns['CFG'],'regimes':regimes,
          'source_contracts':ns['SOURCE_CONTRACT'],'decision_rules':ns['RULES'],
          'prior_task_templates':ns['ASSETS']['task_templates'],'feature_scopes':ns['C2ST_SCOPES'],
          'adaptations':ADAPTATIONS,'recovered_protocol_changes':ns['CHANGE_RECORD'],
          'recovered_setting_reasons':ns['SETTING_REASONS'],
          'inference_scope':'Conditional intervals over the specified seeds/pairs, not independent deployments; prior data/task exposure remains.',
          'clock_scope':'Supplied UTC coordinates; no independently validated sensor/network synchronization.',
          'sensitivity_only':{'P0_unclipped':True,'C2ST_secondary_ceiling':.9945}}
    ns['PROTOCOL_HASH']=ns['digest'](plan);ns['RUN']=project.out/'evaluation'/('rebuilt_'+ns['PROTOCOL_HASH'][:16]);ns['RUN'].mkdir(parents=True,exist_ok=True)
    for tag in ['tables','jobs','arrays','logs','figures','selection']:(ns['RUN']/tag).mkdir(exist_ok=True)
    ns['freeze_json'](ns['RUN']/'protocol.json',plan);ns['freeze_json'](ns['RUN']/'calculation_source.json',ns['NOTEBOOK_SOURCE_SNAPSHOT'])
    ns['EXECUTION_RECORDS']=[];ns['table'](ns['RUN']/'tables'/'reconstruction_changes.csv',ADAPTATIONS)
    json_write(project.out/'latest_evaluation.json',{'path':ns['RUN'].relative_to(project.out).as_posix(),'protocol_hash':ns['PROTOCOL_HASH']})
    return plan

def run(project):
    values_df,observed,seconds,hashes=project.load_prepared();ns=runtime(project);project.runtime=ns
    ns['VALUE_FEATURES']=list(values_df);ns['feature_index']={c:i for i,c in enumerate(values_df)}
    ns['LEARNED_SCOPE']=ns['ASSETS']['external']['generators']['learned_scope'];ns['C2ST_SCOPES']=ns['ASSETS']['external']['c2st']['scopes']
    values=values_df.to_numpy(float);regimes=plan_regimes(len(values),ns['CFG']);initialise(project,ns,hashes,regimes)
    table=ns['table'];run_dir=ns['RUN'];start=time.monotonic();cache=ns['cached_job']
    def bounded_cache(kind,key,fn):
        if time.monotonic()-start>=project.budget_hours*3600:raise TimeBudgetReached('Operational time budget reached between jobs. Rerun the evaluation cell to resume this same protocol.')
        return cache(kind,key,fn)
    ns['cached_job']=bounded_cache
    table(run_dir/'tables'/'observed_input_fraction.csv',[{'feature':c,'observed_fraction':observed[:,i].mean(),'training_observed_fraction':observed[:regimes[0]['train'][1],i].mean()} for i,c in enumerate(values_df)])
    all_results={};all_sources=[];report={}
    try:
        with ns['threadpool_limits'](limits=1):
            checks=ns['run_instruments']()
            for regime in regimes:
                ad=bounded_cache('task_admission',{'regime':regime},lambda:ns['admission'](regime,values,observed))
                ns['freeze_json'](run_dir/'selection'/f"{regime['name']}_tasks.json",ad)
                table(run_dir/'tables'/f"{regime['name']}_task_admission.csv",ad['rows']);cards=ad['cards']
                ns['progress'](f"{regime['name']}: {len(cards)}/32 prior task templates admitted using TRAIN only.")
                qual=ns['run_qualification'](regime,cards,values,observed,seconds);records=[]
                for source in ns['SOURCES']:
                    for seed in regime['evaluation_seeds']:
                        key={'regime':regime,'source':source,'seed':seed,'cards_hash':ns['digest'](cards)}
                        result=bounded_cache('sources',key,lambda:ns['source_job'](regime,source,seed,cards,values,observed));records.append(result)
                        ns['progress'](f"{regime['name']} / {source} / {seed}: {result['contract']['contract_state']}")
                summary=ns['summaries'](regime,records,qual,checks,cards)
                all_results[regime['name']]={'qualification':qual,'results':summary,'admitted_tasks':len(cards)};all_sources+=records
                json_write(run_dir/'progress.json',{'completed_regimes':list(all_results),'source_jobs_completed':len(all_sources)})
            source_rows=[];health=[];fidelity=[]
            for x in all_sources:
                source_rows.append({'regime':x['regime'],'source':x['source'],'seed':x['seed'],'execution_status':x['execution_status'],**x['contract'],'warnings':x.get('generator_warnings',[]),'error':x.get('error')})
                health.extend([{'regime':x['regime'],'source':x['source'],'seed':x['seed'],**r} for r in x['feature_health']])
                for r in x['fidelity']:
                    for metric in ns['ENDPOINT_MIN']:
                        if metric!='c2st_max_auc' and metric in r:
                            fidelity.append({**{k:r[k] for k in ['regime','source','seed','period','scope']},'metric':metric,'value':r[metric],
                                             'metric_qualified':ns['metric_gate'](checks,metric),'source_valid':x['contract'].get('contract_valid',False)})
            for name,rows in [('source_checks',source_rows),('feature_checks',health),('fidelity',fidelity)]:table(run_dir/'tables'/(name+'.csv'),rows)
            errors=sum(x['execution_status']=='error' for x in source_rows)
            task_errors=sum(r.get('status')=='execution_error' for x in all_sources for r in x['utility'])+sum(r.get('status')=='execution_error' for x in all_results.values() for r in x['qualification']['rows'])
            admission_errors=sum(r.get('reason')=='execution_error' for p in (run_dir/'jobs'/'task_admission').glob('*.json') for r in json.loads(p.read_text(encoding='utf-8'))['payload']['rows'])
            classifier_errors=sum(r.get('status')=='execution_error' for x in all_sources for r in x['c2st'])
            report={'execution_status':'COMPLETED_WITH_EXECUTION_ERRORS' if errors+task_errors+classifier_errors+admission_errors else 'PLANNED_JOBS_COMPLETED',
                    'scientific_status':project.prep_report['scientific_status'],'planned_source_jobs':72,'completed_source_jobs':len(source_rows),
                    'source_execution_errors':errors,'task_execution_errors':task_errors,'admission_execution_errors':admission_errors,'classifier_execution_errors':classifier_errors,
                    'primary_admitted_tasks':all_results['primary']['admitted_tasks'],'instrument_checks_passed':sum(x['passed'] for x in checks),'instrument_checks_total':len(checks),
                    'historical_raw_to_canonical_reproduction':'NOT_ESTABLISHED','independent_confirmation':False,'paper_results_automatically_replaced':False,
                    'interpretation':'A completed computation does not imply admissible scientific outcomes. Inspect instruments, P0, source health, availability and reference skill.'}
            ns['make_plots'](all_results)
    except TimeBudgetReached as exc:
        report={'execution_status':'PAUSED_TIME_BUDGET','scientific_status':'EVALUATION_INCOMPLETE','reason':str(exc),'completed_regimes':list(all_results)}
        print(str(exc),flush=True)
    except BaseException as exc:
        report={'execution_status':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'EXECUTION_ERROR','scientific_status':'EVALUATION_INCOMPLETE','error':repr(exc),'traceback':traceback.format_exc()};raise
    finally:
        report['elapsed_this_invocation_seconds']=round(time.monotonic()-start,3);json_write(run_dir/'run_status.json',report)
        table(run_dir/'tables'/'execution.csv',ns['EXECUTION_RECORDS'])
        manifest=[{'path':p.relative_to(run_dir).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in sorted(run_dir.rglob('*')) if p.is_file() and p.name!='result_file_manifest.csv']
        table(run_dir/'result_file_manifest.csv',manifest);project.export()
    return report
