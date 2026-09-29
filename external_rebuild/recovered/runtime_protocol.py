# Proposed corrections are recorded here. Historical notebooks and results are read-only.
SOURCES=['real_row_resample','real_contiguous_block','independent_marginals','column_shuffle','hurdle_iid','independent_stitch','shared_stitch','learned_gmm_overlay','learned_latent_var_overlay']
SOURCE_CONTRACT={'real_row_resample':'REAL_SAMPLING_ANCHOR','real_contiguous_block':'REAL_CHRONOLOGICAL_ANCHOR','independent_marginals':'MARGINAL_DESTRUCTION_MECHANISM','column_shuffle':'COLUMN_SHUFFLE_INVARIANT','hurdle_iid':'TRANSPARENT_OUTPUT_HEALTH','independent_stitch':'TRANSPARENT_STITCH_HEALTH','shared_stitch':'TRANSPARENT_STITCH_HEALTH','learned_gmm_overlay':'LEARNED_FIT_HEALTH','learned_latent_var_overlay':'LEARNED_FIT_HEALTH'}
GEN_FUNCS={name:globals()[name] for name in SOURCES}
RULES=ASSETS['external']['decision_rules']
CFG={'n_jobs':N_JOBS,'p0_bootstrap_draws':5000,'acf_lags':[1,5,30,60,300],
     'seeds':[1337,1338,1339,1340,1341],'min_rows':300,'reference_loss_floor':1e-5,'target_IQR_floor':1e-4,
     'reference_skill_gain':.10,'auc_min':.60,'ap_gain_min':.01,'prevalence_range':[.005,.50],
     'inner_selection_fraction':.20,'ni_ratio':1.10,'min_pairs':4,'min_suite_capabilities':4,'min_suite_fraction':.60,
     'id_margin':.03,'margin_quantile':.90,'xs_floor':math.log(1.10),'xs_cap':math.log(1.50),
     'temporal_floor':1.25,'temporal_cap':1.80,'order_min':math.log(1.05),'ni_rate_min':.75,
     'c2st_block_rows':60,'c2st_splits':3,'c2st_trees':100,'c2st_depth':12,'c2st_leaf':3,
     'c2st_null_trees':25,'c2st_permutations':19,'c2st_rows_per_class':8000,'c2st_ceiling':.995,
     'instrument_seeds':[19,29,39],'instrument_rows':24000,'instrument_rho':.80,'instrument_null_excess':.03,
     'block_coverage_min':.95,'pairs':10,'stitch_rows':60,'support_violation_max':1e-4}

CHANGE_RECORD=[
 {'item':'Scientific scope','previous':'Earlier TON_IoT implementation lacked Stage 3A','new':'All six stages, with absolute reference losses and matched real/simple baselines','reason':'Test the final procedure rather than infer missing checks.'},
 {'item':'Task templates','previous':'32 tasks selected from 155 candidates in earlier work','new':'Use those 32 documented templates as prior choices. Re-estimate thresholds and re-admit tasks inside each TRAIN period. Do not claim to recreate the unavailable full candidate-selection process.','reason':'Preserve the actual task definitions without inventing missing selection code.'},
 {'item':'Period roles','previous':'Outer VAL selected tasks and overlapped some rolling tests','new':'Earlier 80% of TRAIN fits task admission models and remaining TRAIN after embargo selects tasks. The old VAL interval is the near-period evaluation. The old TEST interval is the future evaluation. Sources fit full TRAIN once for both evaluations.','reason':'Keep task selection before both evaluated periods. Near-period does not prove an unchanged data distribution.'},
 {'item':'Utility models','previous':'External Ridge/logistic fitted without a scaling pipeline','new':'Use the residential StandardScaler plus Ridge/logistic definitions with fitting only on the model training examples.','reason':'Consistent numeric treatment across heterogeneous columns. This is an explicit implementation correction.'},
 {'item':'Training counts','previous':'Real reference had more usable training rows','new':'Match usable real and synthetic task-example counts before fitting, on the same two real evaluation sets.','reason':'Remove the known count confound. Equal counts do not imply equal independent information.'},
 {'item':'P0 controls','previous':'External P0 supplied C2ST only. Residential block controls used stitched sub-blocks.','new':'Keep the recorded primary matched pairs. Add identity, two contiguous TRAIN-block controls, and row resampling, with equal usable task counts. Control length equals block length minus the maximum task span.','reason':'Provide actual task losses for Stages 3A/3B. The span-based subtraction leaves room for distinct contiguous controls without inserting joins. These are new external task comparisons, not reconstructed residential values.'},
 {'item':'Rolling P0','previous':'No origin-specific final-procedure qualification','new':'Repeat TRAIN-only block selection and qualification inside each rolling TRAIN period. A conservative 0.95 finite-value availability screen replaces the unavailable acquisition-coverage calculation for these new pairs. This distinction is recorded.','reason':'Earlier primary blocks may lie beyond a rolling training boundary.'},
 {'item':'C2ST','previous':'Random 65/35 row split and RF only','new':'Three grouped splits. Use paired five-minute groups before sampling, trim boundary context, RF and scaled logistic, and conditional randomisation diagnostics.','reason':'Keep related temporal groups together and match the documented discriminator design. This is not a calibrated test for arbitrary sequence dependence.'},
 {'item':'Target observability','previous':'Canonical imputed values could enter real labels','new':'Read the saved pre-imputation table and exclude unobserved real targets. Predictors use the original zero-imputed canonical values.','reason':'An unobserved target must not be labelled as a measured zero. Synthetic outputs are a complete value view. No generated-mask claim is made.'},
 {'item':'Source models','previous':'Nine sources including GMM and latent-VAR on different bases','new':'Keep the nine original external generator functions and their settings. Report learned-feature checks and whole-output checks separately.','reason':'Avoid changing generators to obtain favourable results. The different-base and model-breadth limits remain.'},
 {'item':'Aggregation','previous':'Five-seed ranges and different external weighting','new':'Family-balanced capability summaries and pair/seed bootstrap qualification. Five-seed bootstrap intervals for primary utility and paired transfer. Rolling runs remain separate descriptive checks.','reason':'Do not pool adjacent rows, task clones, or rolling origins as independent deployments.'},
 {'item':'Sensitivity','previous':'Selected checks reported separately','new':'Always report raw and clipped P0 decisions, the existing 0.9945 secondary ceiling, and distances to primary thresholds. Primary rules remain unchanged.','reason':'Check known boundary sensitivity without selecting the most favourable rule.'},
 {'item':'Record keeping','previous':'Caches could be reused by path without input/code binding','new':'Freeze data, code, environment and settings. Save component records and verify every cache payload hash.','reason':'Prevent stale or mixed results from being treated as a new experiment.'}
]

SETTING_REASONS={
 'seeds':'Retain the five prior seeds. They describe stochastic variation, not five independent deployments.',
 'bootstrap_draws':'Retain 5,000 resamples from the residential procedure. This reduces Monte Carlo noise but does not add independent evidence.',
 'inner_selection_fraction':'Retain the prior 80/20 inner allocation. It is a design convention, not a demonstrated optimum.',
 'min_rows':'Retain the prior 300 usable-example requirement for task fitting/evaluation. Too few examples produce Not-Estimable, never an automatic pass.',
 'source_settings':'GMM up to 8 diagonal components, VAR up to 16 PCA components and lags 1/5/30, 60-row stitching. Exact functions are copied from the external notebook. No new architecture tuning.',
 'c2st_group_duration':'300 seconds was stated in the external protocol. This is 60 rows at the 5-second cadence. Boundary trim uses the full 25-row task span. Remaining dependence is still possible.',
 'c2st_compute':'100 trees, depth 12, 3 splits and 19 null repetitions retain the residential settings. The external cap of 8,000 rows per class bounds computation.',
 'p0_duration':'Primary P0 uses the recorded 30-minute pairs. Rolling origins choose the first 30/60/90/120/150/180-minute duration supporting ten screened pairs, using TRAIN only.',
 'p0_counts':'Retain ten disjoint pairs with five for calibration and five for qualification. At least four usable qualification pairs and all planned seeds are required.',
 'p0_controls':'Subtract the maximum target/predictor span from a matched block so two contiguous samples can start at different positions. This is derived from task context, not an outcome-selected percentage.',
 'numerical_guards':'Keep reference loss >=1e-5, target IQR >=1e-4, IQR floor 1e-6 for scaled loss, and epsilon 1e-12 for skill. Record each activation. These guards do not prove a reference is useful.',
 'thresholds':'Retain rho .80, skill .10, AUC .60, AP gain .01, prevalence .005–.50, identity log margin .03, order log(1.05), NI 1.10 and 75% card rate. They are operational conventions, not universal constants.',
 'scope':'Keep the four externally documented feature views, 48 learned columns, and all 32 prior task templates. Their earlier selection is a disclosed historical exposure.',
 'source_health':'Retain role-specific external checks. Learned variation >=.70, support violations <=1e-4, activity errors <=.08/.20/.40. Report each feature, not only the terminal flag.'}


def code_fingerprint():
    import types
    def signature(co):
        const=[]
        for x in co.co_consts:
            if isinstance(x,types.CodeType):const.append(signature(x))
            elif isinstance(x,(str,int,float,bool,type(None),bytes,tuple)):
                const.append(repr(x))
            else:const.append(type(x).__name__)
        return {'bytes':co.co_code.hex(),'names':co.co_names,'vars':co.co_varnames,'constants':const}
    return digest({n:signature(v.__code__) for n,v in globals().items() if isinstance(v,types.FunctionType) and v.__globals__ is globals()})


def validate_external_time_axes(frame,pre):
    """Check the shared recorded timestamps. Only canonical data require sec."""
    time_col='timestamp_utc_coordinate'
    for name,data in [('canonical',frame),('preimputation',pre)]:
        if time_col not in data.columns:
            raise RuntimeError(f'{name} is missing the recorded {time_col} column.')
        times=data[time_col]
        if not pd.api.types.is_datetime64_any_dtype(times.dtype):
            raise RuntimeError(f'{name} timestamp column is not a datetime column: {times.dtype}.')
        if times.isna().any() or times.duplicated().any() or not times.is_monotonic_increasing:
            raise RuntimeError(f'{name} timestamps contain missing, duplicate, or out-of-order values.')
    if len(frame)!=33170 or len(pre)!=len(frame):
        raise RuntimeError(f'Unexpected TON_IoT row counts: canonical={len(frame)}, preimputation={len(pre)}. Expected 33170 each.')
    canonical_time=frame[time_col].reset_index(drop=True)
    pre_time=pre[time_col].reset_index(drop=True)
    if not canonical_time.equals(pre_time):
        raise RuntimeError('Recorded timestamp columns differ. No rows were reordered, shifted, or filled.')
    elapsed=(canonical_time-canonical_time.iloc[0]).dt.total_seconds().to_numpy()
    if not np.all(np.diff(elapsed)==5):
        raise RuntimeError('Recorded TON_IoT timestamps do not have the expected five-second cadence.')
    if 'sec' not in frame.columns:
        raise RuntimeError('Canonical data are missing sec.')
    seconds=frame['sec'].to_numpy(dtype=float,na_value=np.nan)
    if not np.array_equal(seconds,elapsed):
        raise RuntimeError('Canonical sec differs from elapsed seconds on its recorded timestamp axis.')
    if 'sec' in pre.columns and not np.array_equal(pre['sec'].to_numpy(dtype=float,na_value=np.nan),seconds):
        raise RuntimeError('Pre-imputation sec, when present, must match canonical sec.')
    return seconds


def load_external():
    check_dependencies()
    for p in [EXTERNAL_CANON,EXTERNAL_PREIMPUTATION]:
        if not p.is_file():raise FileNotFoundError(f'Required input not found: {p}. Change only its path in the configuration cell if it moved.')
    hashes={'canonical':file_hash(EXTERNAL_CANON),'preimputation':file_hash(EXTERNAL_PREIMPUTATION)}
    expected={'canonical':ASSETS['external']['canonical_sha256'],'preimputation':'e9ceacc4d8638ef1f7e56c8bc8d2004430f1de413bd677d124a9ffb6b893968d'}
    if hashes!=expected:raise RuntimeError('TON_IoT inputs differ from the recorded files. Do not reuse this protocol silently. Save the observed hashes and resolve the input change first. '+json.dumps(hashes))
    frame=read_table(EXTERNAL_CANON);pre=read_table(EXTERNAL_PREIMPUTATION)
    seconds=validate_external_time_axes(frame,pre)
    scopes=ASSETS['external']['c2st']['scopes'];features=sorted(set(sum(scopes.values(),[])+ASSETS['external']['generators']['learned_scope']+sum([x['predictors']+[x['target']] for x in ASSETS['task_templates']],[])))
    absent=[c for c in features if c not in frame or c not in pre]
    if absent:raise RuntimeError('Required value columns missing from the canonical or pre-imputation table: '+str(absent))
    values=frame[features].to_numpy(float)
    if not np.isfinite(values).all():raise RuntimeError('Canonical value view contains non-finite values. Do not silently alter the earlier preparation.')
    observed=np.isfinite(pre[features].to_numpy(dtype=float,na_value=np.nan))
    return frame[features].copy(),observed,seconds,hashes


def plan_regimes(n,old):
    prim={x['split']:(x['start'],x['end_exclusive']) for x in old['primary_splits']}
    out=[{'name':'primary','train':prim['TRAIN'],'near':prim['VAL'],'future':prim['TEST'],'evaluation_seeds':CFG['seeds']}]
    for r in old['robustness_origins']:
        out.append({'name':f"roll{r['origin']}",'train':(r['train_start'],r['train_end']),'near':(r['val_start'],r['val_end']),'future':(r['test_start'],r['test_end']),'evaluation_seeds':[CFG['seeds'][0]]})
    for r in out:
        start,end=r['train'];boundary=start+int((end-start)*(1-CFG['inner_selection_fraction']))
        r['selection_fit']=(start,boundary);r['selection_validation']=(boundary+25,end)
        r['output_rows']=min(r['near'][1]-r['near'][0],end-start)
        for a,b in [r['selection_fit'],r['selection_validation'],r['train'],r['near'],r['future']]:
            if a<0 or b>n or b-a<=2*CFG['min_rows']:raise RuntimeError('Insufficient rows for the fixed split design.')
        assert r['selection_fit'][1]+25<=r['selection_validation'][0]
        assert r['train'][1]+25<=r['near'][0] and r['near'][1]+25<=r['future'][0]
    return out


def initialise_run(data_hashes,regimes):
    global RUN,PROTOCOL_HASH,EXECUTION_RECORDS
    env=environment_record()
    plan={'study':'Corrected TON_IoT evaluation with residential matching audit','not_independent_confirmation':True,
          'code_sha256':code_fingerprint(),'embedded_source_sha256':digest(ASSETS),'data_sha256':data_hashes,
          'environment':env,'settings':CFG,'regimes':regimes,'changes':CHANGE_RECORD,'setting_reasons':SETTING_REASONS,
          'source_contracts':SOURCE_CONTRACT,'decision_rules':RULES,'feature_scopes':ASSETS['external']['c2st']['scopes'],'prior_task_templates':ASSETS['task_templates'],'utility_metric_requirements':{'contemporaneous':['marginal_ks_mean','coupling_corr_mae'],'temporal':['acf_abs_error_mean','spectral_l1_mean','transition_rate_mae']},'old_generator_source_sha256':digest(LEGACY_GENERATOR_SOURCE),
          'sensitivity_only':{'C2ST_secondary_ceiling':.9945,'P0_unclipped':True},'raw_data_exported':False}
    PROTOCOL_HASH=digest(plan);RUN=OUTPUT_ROOT/('external_'+PROTOCOL_HASH[:16]);RUN.mkdir(parents=True,exist_ok=True)
    freeze_json(RUN/'protocol.json',plan)
    if 'NOTEBOOK_SOURCE_SNAPSHOT' in globals():freeze_json(RUN/'calculation_source.json',NOTEBOOK_SOURCE_SNAPSHOT)
    for p in ['tables','jobs','arrays','logs','figures','selection']: (RUN/p).mkdir(exist_ok=True)
    table(RUN/'tables'/'protocol_changes.csv',CHANGE_RECORD)
    table(RUN/'tables'/'setting_reasons.csv',[{'setting':k,'reason':v} for k,v in SETTING_REASONS.items()])
    EXECUTION_RECORDS=[]
    progress(f'Protocol fixed before selection and performance calculations. Run: {RUN.name}')
    return plan


def cached_job(kind,key,fn):
    path=RUN/'jobs'/kind/(digest(key)+'.json');path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        record=json.loads(path.read_text())
        if record.get('protocol_hash')!=PROTOCOL_HASH or record.get('key')!=plain(key) or record.get('payload_hash')!=digest(record.get('payload')):
            raise RuntimeError(f'Checkpoint does not match its protocol, job, or payload: {path}')
        payload=record['payload']
        for rel,h in record.get('files',{}).items():
            p=RUN/rel
            if not p.is_file() or file_hash(p)!=h:raise RuntimeError('A saved job output is missing or changed: '+str(p))
        EXECUTION_RECORDS.append({'kind':kind,'key':json.dumps(key,sort_keys=True),'status':'cached','seconds':record.get('seconds')})
        return payload
    start=time.monotonic()
    payload=fn();payload=plain(payload)
    files={}
    for rel in payload.pop('_files',[]):files[rel]=file_hash(RUN/rel)
    record={'protocol_hash':PROTOCOL_HASH,'key':key,'payload':payload,'payload_hash':digest(payload),'seconds':time.monotonic()-start,'files':files}
    atomic_json(path,record)
    EXECUTION_RECORDS.append({'kind':kind,'key':json.dumps(key,sort_keys=True),'status':'computed','seconds':record['seconds']})
    return payload
