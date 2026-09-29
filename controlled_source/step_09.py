
# ============================================================
# 5. Fixture, split, scopes and global binding
# ============================================================
def primary_split():
    tr=np.arange(0,KT_TRAIN_ROWS,dtype=np.int64)
    vs=KT_TRAIN_ROWS+KT_EMBARGO_ROWS; va=np.arange(vs,vs+KT_VAL_ROWS,dtype=np.int64)
    ts=vs+KT_VAL_ROWS+KT_EMBARGO_ROWS; te=np.arange(ts,ts+KT_TEST_ROWS,dtype=np.int64)
    assert int(te[-1])+1==KT_TOTAL_ROWS
    return {"fold_id":"primary","train":tr,"val":va,"test":te,"inner_fit":np.array([],dtype=np.int64),"inner_calib":np.array([],dtype=np.int64)}
PRIMARY_SPLIT_TEMPLATE=primary_split()

def ar_noise(rng,n,phi,sigma):
    x=np.zeros(n); e=rng.normal(0,sigma,n)
    for i in range(1,n): x[i]=phi*x[i-1]+e[i]
    return x

def make_fixture(fixture_seed,context,session_severity=1.0):
    rng=np.random.default_rng(int(fixture_seed)); n=KT_TOTAL_ROWS; split=PRIMARY_SPLIT_TEMPLATE
    frame=build_controlled_iot_fixture(n=n,seed=int(fixture_seed)).copy()
    # Explicit lag mechanism.
    raw=np.log1p(np.maximum(frame["router__bytes"].to_numpy(float),0)); out=np.empty(n); out[0]=raw[0]; noise=rng.normal(0,.015,n)
    for i in range(1,n): out[i]=.84*out[i-1]+.16*raw[i]+noise[i]
    frame["router__bytes"]=np.expm1(np.clip(out,0,None))
    # Explicit contemporaneous mechanism.
    frame["iot__power"]=np.maximum(0,4+3*frame["router__packets"]+1.4*frame["ota24__frames"]+4.5*frame["iot__state"]+.2*frame["iot__sensor"]+rng.normal(0,.7,n))
    base_by_tier={"router":frame["router__packets"].to_numpy(float),"ota24":frame["ota24__frames"].to_numpy(float),"zigbee":frame["zigbee__packets"].to_numpy(float),"iot":frame["iot__power"].to_numpy(float)}
    for tier,base in base_by_tier.items():
        count=6 if tier!="iot" else 2; scale=max(float(np.std(base)),1.0)
        for j in range(count):
            ar=ar_noise(rng,n,.55+.05*(j%4),.08+.02*j)
            if j%3==0: value=np.maximum(0,.35*base+scale*ar)
            elif j%3==1:
                active=rng.random(n)<np.clip(.01+.12*(base>np.median(base)),.001,.45); value=active*np.maximum(0,.15*base+scale*np.abs(ar))
            else: value=.20*base+scale*ar
            frame[f"{tier}__aux_{j:02d}"]=value.astype(float)
    frame["router__session_marker"]=rng.normal(0,.01,n)
    frame["iot__regime"]=((np.arange(n)//max(1,3600*4))%2).astype(float)
    frame["iot__regime_interaction"]=frame["iot__regime"].to_numpy(float)*(6.4*frame["router__packets"].to_numpy(float)+3.0*frame["ota24__frames"].to_numpy(float))
    if context=="constant_target": frame["iot__power"]=float(np.median(frame["iot__power"]))
    elif context=="rare_class":
        events=np.zeros(n); events[split["train"][::max(1,len(split["train"])//3)][:3]]=1; frame["zigbee__events"]=events
    elif context=="regime_unstable":
        regime=np.zeros(n); midpoint=len(split["train"])//2; regime[split["train"][midpoint:]]=1; regime[split["val"]]=1; regime[split["test"]]=1; frame["iot__regime"]=regime
        p=frame["router__packets"].to_numpy(float); o=frame["ota24__frames"].to_numpy(float)
        mp=float(np.quantile(p[split["train"]],.995)); mo=float(np.quantile(o[split["train"]],.995))
        a=20+3.2*p+1.5*o; b=20+3.2*np.maximum(0,mp-p)+1.5*np.maximum(0,mo-o)
        frame["iot__regime_interaction"]=regime*(6.4*p+3.0*o)
        frame["iot__power"]=np.maximum(0,np.where(regime<.5,a,b)+rng.normal(0,.7,n))
    elif context=="regime_mild":
        regime=np.zeros(n); midpoint=len(split["train"])//2; regime[split["train"][midpoint:]]=1; regime[split["val"]]=1; regime[split["test"]]=1; frame["iot__regime"]=regime
        p=frame["router__packets"].to_numpy(float); o=frame["ota24__frames"].to_numpy(float)
        # Discriminating positive control: relationship changes, but not enough to destroy useful transfer.
        a=20+3.2*p+1.5*o
        b=20+2.75*p+1.25*o
        frame["iot__regime_interaction"]=regime*(0.45*p+0.25*o)
        frame["iot__power"]=np.maximum(0,np.where(regime<.5,a,b)+rng.normal(0,.7,n))
    elif context=="session_shift":
        marker=np.zeros(n); marker[split["test"]]=float(session_severity)*10; frame["router__session_marker"]=marker
    elif context not in {"stable","no_order"}: raise ValueError(context)
    frame=frame.astype(float)
    values=[c for c in frame if not c.endswith("__nonfinite_mask")]
    if len(values)!=32: raise RuntimeError(f"Expected 32 value fields, found {len(values)}")
    truth={"fixture_seed":int(fixture_seed),"context":context,"rows":len(frame),"time_step_seconds":KT_TIME_STEP_SECONDS,"value_columns":values,"regime_shift_planted":context in {"regime_unstable","regime_mild"},"session_shift_planted":context=="session_shift"}
    return frame,truth,np.arange(n,dtype=float)*KT_TIME_STEP_SECONDS

def build_scopes(frame):
    values=[c for c in frame if not c.endswith("__nonfinite_mask")]; masks=[c for c in frame if c.endswith("__nonfinite_mask")]
    protocol=[c for c in values if infer_tier(c) in {"router","ota","zigbee"}]
    return {"generator_v2":values+masks,"all_value_v3":values,"protocol_value_v3":protocol,"observability_v1":masks,"mask_only_v1":masks}

def bind_fixture(frame,fixture_seed,context,time_seconds):
    global CANON_DF,PRIMARY_SPLIT,FEATURE_SCOPES,ACTIVE_TIERS,P0_PROFILE_COLS,LEARNED_MODEL_COLS,time_sorted,RUN_FINGERPRINT,VALID_TASK_MODELS
    CANON_DF=frame.reset_index(drop=True); PRIMARY_SPLIT={k:(v.copy() if isinstance(v,np.ndarray) else v) for k,v in PRIMARY_SPLIT_TEMPLATE.items()}
    FEATURE_SCOPES=build_scopes(CANON_DF); ACTIVE_TIERS=["iot","ota","router","zigbee"]
    P0_PROFILE_COLS=list(FEATURE_SCOPES["all_value_v3"]); LEARNED_MODEL_COLS=list(FEATURE_SCOPES["all_value_v3"]); time_sorted=np.asarray(time_seconds,float); VALID_TASK_MODELS=[]
    RUN_FINGERPRINT={"dataset":stable_hash({"experiment":EXPERIMENT_VERSION,"fixture_seed":fixture_seed,"context":context}),"splits":stable_hash({k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in PRIMARY_SPLIT.items()}),"scopes":stable_hash(FEATURE_SCOPES)}
