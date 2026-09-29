# Imports and general helpers. No previous notebook is executed.
import os, sys, json, math, time, hashlib, traceback, warnings, zipfile, platform
from pathlib import Path
from collections import defaultdict
from typing import Any, Sequence
from importlib import metadata
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import wasserstein_distance
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
import matplotlib
import matplotlib.pyplot as plt


def plain(x):
    if isinstance(x, dict): return {str(k):plain(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [plain(v) for v in x]
    if isinstance(x, np.ndarray): return plain(x.tolist())
    if isinstance(x, np.generic): return plain(x.item())
    if isinstance(x, Path): return str(x)
    if isinstance(x, float) and not math.isfinite(x): return None
    return x


def digest(x):
    return hashlib.sha256(json.dumps(plain(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()


def atomic_json(path, obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(plain(obj),indent=2,allow_nan=False),encoding='utf-8');temp.replace(p)


def freeze_json(path,obj):
    p=Path(path)
    if p.exists():
        old=json.loads(p.read_text())
        if digest(old)!=digest(obj): raise RuntimeError(f'Frozen record differs: {p}. Keep the old run and use a new output folder.')
    else: atomic_json(p,obj)


def table(path,rows,columns=None):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    frame=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows,columns=columns)
    temp=p.with_name(p.name+'.tmp');frame.to_csv(temp,index=False);temp.replace(p)
    return frame


def finite(x):
    try:return bool(np.isfinite(float(x)))
    except (TypeError,ValueError):return False


def progress(message):
    print(time.strftime('%H:%M:%S'),message,flush=True)


def read_table(path,columns=None):
    path=Path(path)
    if path.suffix=='.parquet': return pd.read_parquet(path,columns=columns)
    if path.suffix=='.csv': return pd.read_csv(path,usecols=columns)
    raise ValueError('Use a Parquet or CSV input. Pickled input data are not needed.')


def environment_record():
    versions={}
    for name in ['numpy','pandas','scipy','scikit-learn','pyarrow','matplotlib','threadpoolctl']:
        try:versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError:versions[name]='not installed'
    return {'python':sys.version,'platform':platform.platform(),'packages':versions}


def check_dependencies():
    if EXTERNAL_CANON.suffix=='.parquet':
        try: import pyarrow
        except ImportError as exc:
            raise RuntimeError('Install pyarrow in this kernel, then restart and Run All. See the installation cell above.') from exc


def residual_audit_tables(raw, seconds, saved):
    """Exact historical profile arithmetic, with all squared-distance terms saved."""
    global CANON_DF,time_sorted,FEATURE_SCOPES,ACTIVE_TIERS,P0_PROFILE_COLS,TIER_ALIASES,CFG
    prior={k:globals().get(k) for k in ['CANON_DF','time_sorted','FEATURE_SCOPES','ACTIVE_TIERS','P0_PROFILE_COLS','TIER_ALIASES','CFG']}
    try:
        TIER_ALIASES=saved['cfg']['tier_aliases'];FEATURE_SCOPES=saved['scopes'];ACTIVE_TIERS=saved['active_tiers']
        P0_PROFILE_COLS=saved['plan']['profile_columns'];CFG=saved['cfg']
        vals=raw.astype(np.float32);CANON_DF=vals.replace([np.inf,-np.inf],np.nan).fillna(0)
        time_sorted=np.asarray(seconds,float)
        blocks=[np.arange(b['start'],b['end']) for b in saved['plan']['blocks']]
        profiles,pairs=match_p0_blocks(blocks)
        names=sorted(profiles.columns);matrix=profiles[names].to_numpy(float)
        center=np.median(matrix,axis=0);mad=np.median(np.abs(matrix-center),axis=0)*1.4826
        scale=mad.copy();scale[scale<1e-8]=1.0;z=(matrix-center)/scale
        scale_rows=[{'profile_field':c,'median':center[j],'raw_MAD_scale':mad[j],'applied_scale':scale[j],'scale_replaced_by_one':bool(mad[j]<1e-8)} for j,c in enumerate(names)]
        values=[]
        for i,ids in enumerate(blocks):
            for col in P0_PROFILE_COLS:
                v=CANON_DF.iloc[ids][col].to_numpy(float);q=robust_iqr(v)
                values.append({'block_id':i,'feature':col,'mean_after_historical_imputation':v.mean(),'IQR':q,'applied_IQR_denominator':max(q,1e-6),'IQR_floor_used':q<1e-6,'zero_rate':np.mean(v==0),'nonfinite_rate_before_imputation':float(np.mean(~np.isfinite(raw.iloc[ids][col].to_numpy(float))))})
        saved_lookup={p['pair_id']:p for p in saved['plan']['pairs']};contrib=[];checks=[]
        for p in pairs:
            a=p['source_block'];b=p['target_block'];old=saved_lookup.get(p['pair_id'],{})
            squared=(z[a]-z[b])**2;total=squared.sum()
            checks.append({**p,'recorded_distance':old.get('profile_distance'),'same_target_as_saved':b==old.get('target_block'),'same_phase_as_saved':p['phase']==old.get('phase'),'distance_reproduced':bool(np.isclose(p['profile_distance'],old.get('profile_distance',np.nan),rtol=1e-6,atol=1e-6))})
            for j,c in enumerate(names):
                contrib.append({'pair_id':p['pair_id'],'profile_field':c,'source_profile':matrix[a,j],'target_profile':matrix[b,j],'raw_profile_difference':matrix[a,j]-matrix[b,j],'applied_MAD_scale':scale[j],'standardised_difference':z[a,j]-z[b,j],'squared_distance_contribution':squared[j],'fraction_of_squared_distance':squared[j]/total if total else 0.})
        # Diagnostic comparison only. Global TRAIN scaling is not used to replace any match.
        diagnostics=[]
        for col in P0_PROFILE_COLS:
            train_v=CANON_DF[col].to_numpy(float);q=robust_iqr(train_v)
            for old in saved['plan']['pairs']:
                a=train_v[old['source_start']:old['source_end']];b=train_v[old['target_start']:old['target_end']]
                diagnostics.append({'pair_id':old['pair_id'],'feature':col,'source_mean':a.mean(),'target_mean':b.mean(),'global_train_IQR':q,'mean_difference_in_global_IQR_units':(a.mean()-b.mean())/q if q>0 else np.nan,'KS_distance':stats.ks_2samp(a,b,method='asymp').statistic,'zero_rate_difference':np.mean(a==0)-np.mean(b==0),'diagnostic_only':True})
        return {'profiles':profiles.assign(block_id=range(len(profiles))),'scales':scale_rows,'blocks':values,'pairs':checks,'contributions':contrib,'raw_differences':diagnostics}
    finally:
        for k,v in prior.items():
            if v is None:globals().pop(k,None)
            else:globals()[k]=v


def run_residential_audit():
    out=OUTPUT_ROOT/'residential_matching';out.mkdir(parents=True,exist_ok=True)
    saved=ASSETS['residential'];expected=saved['raw']['source_sha256']
    if not RESIDENTIAL_DATA.is_file():
        result={'status':'INPUT_UNAVAILABLE','reason':'Residential source file not found. The external run can continue, but this weakness is unresolved.','path':str(RESIDENTIAL_DATA)}
        atomic_json(out/'audit_status.json',result);progress(result['reason']);return result
    progress('Hashing the residential input. This is a one-time sequential read.')
    actual=file_hash(RESIDENTIAL_DATA)
    if actual!=expected:
        result={'status':'INPUT_DIFFERS_FROM_RECORDED_RUN','actual_sha256':actual,'expected_sha256':expected,'reason':'Historical matches cannot be claimed to be reconstructed from a different input. No matching rule was changed.'}
        atomic_json(out/'audit_status.json',result);progress(result['reason']);return result
    bound=max(b['end'] for b in saved['plan']['blocks'])
    cols=sorted(set(saved['scopes']['all_value_v3'])|set(saved['plan']['profile_columns']))
    # Read column by column to avoid a second multi-GB copy of the complete data.
    sec=read_table(RESIDENTIAL_DATA,[saved['raw']['time_column']]).iloc[:,0].to_numpy(float)
    order=np.argsort(sec,kind='stable');selected=order[:bound];seconds=sec[selected]
    if not np.all(np.diff(sec[order])>0):raise RuntimeError('Residential times are not unique.')
    matrix={}
    for i,col in enumerate(cols):
        matrix[col]=read_table(RESIDENTIAL_DATA,[col]).iloc[selected,0].to_numpy(dtype=np.float32)
        if (i+1)%100==0:progress(f'Residential audit: loaded {i+1}/{len(cols)} TRAIN columns.')
    raw=pd.DataFrame(matrix);result=residual_audit_tables(raw,seconds,saved)
    for name,rows in result.items():table(out/(name+'.csv'),rows)
    c=pd.DataFrame(result['contributions']);top=c.sort_values('fraction_of_squared_distance',ascending=False).groupby('pair_id',sort=False).head(5)
    table(out/'largest_contributors.csv',top)
    checks=pd.DataFrame(result['pairs']);ok=bool(checks[['same_target_as_saved','same_phase_as_saved','distance_reproduced']].all().all())
    status={'status':'RECONSTRUCTED' if ok else 'RECONSTRUCTION_DIFFERENCE','source_sha256':actual,'pairs':len(checks),'all_recorded_matches_reproduced':ok,'original_matches_changed':False,'interpretation':'Distance contributions and raw-value comparisons are available. Numerical reconstruction does not establish that the matched blocks are substantively similar. Inspect the largest contributors before deciding whether any residential results need recalculation.'}
    atomic_json(out/'audit_status.json',status);progress(status['status']);return status
