import os,sys,json,math,time,hashlib,traceback,warnings,zipfile,io,platform,tempfile
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Any,Sequence
from importlib import metadata
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestRegressor,RandomForestClassifier
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import brier_score_loss,roc_auc_score,average_precision_score,balanced_accuracy_score,mean_absolute_error,r2_score
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
import matplotlib.pyplot as plt

TIER_ALIASES={'router':'router','rtr':'router','eth':'router','wan':'router','net':'router','ota':'ota','ota24':'ota','ota5':'ota','ota2':'ota','wifi':'ota','wlan':'ota','otawifi':'ota','zigbee':'zigbee','zb':'zigbee','zwave':'zwave','zw':'zwave','iot':'iot','dev':'iot','sensor':'iot','plug':'iot','actuator':'iot','telemetry_in_sec':'iot','telemetry':'iot','events_in_sec':'iot','events':'iot','state_in_sec':'iot'}

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,Path):return str(x)
    if isinstance(x,float) and not math.isfinite(x):return None
    return x

def dh(x):return hashlib.sha256(json.dumps(clean(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def fh(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save_json(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(clean(x),indent=2,allow_nan=False));q.replace(p)
def save_csv(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp');pd.DataFrame(x).to_csv(q,index=False);q.replace(p)
def msg(s):print(time.strftime('%H:%M:%S'),s,flush=True)
def cache(kind,key,fn):
    p=RUN/'jobs'/kind/(dh(key)+'.json')
    if p.exists():
        d=json.loads(p.read_text())
        if d['protocol']!=PROTOCOL_HASH or d['key']!=clean(key) or d['payload_hash']!=dh(d['payload']):raise RuntimeError('Changed checkpoint: '+str(p))
        return d['payload']
    result=fn();save_json(p,{'protocol':PROTOCOL_HASH,'key':key,'payload':result,'payload_hash':dh(result)})
    return result

