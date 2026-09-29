
def jitter_continuous(base, train_support, columns, sigma_iqr, seed):
    rng=np.random.default_rng(seed)
    out=base[list(columns)].copy().reset_index(drop=True)
    for c in columns:
        if c.endswith("__nonfinite_mask"): continue
        x=out[c].to_numpy(float,copy=True)
        tr=train_support[c].to_numpy(float,copy=False)
        finite=tr[np.isfinite(tr)]
        if len(finite)<20: continue
        sup=infer_column_support(finite)
        iqr=robust_iqr(finite)
        if sup["binary"] or sup["integer_like"] or iqr<=1e-9:
            continue
        x += rng.normal(0.0,sigma_iqr*iqr,size=len(x))
        out[c]=x
    return project_frame_to_train_support(out,train_support[list(columns)],columns)

train=CANON_DF.iloc[PRIMARY_SPLIT["train"]].reset_index(drop=True)
gen_cols=list(FEATURE_SCOPES["generator_v2"])
n=int(CFG["generation_rows"])

POS_SOURCES={}
for role in ["contemporaneous","temporal"]:
    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            if role=="contemporaneous":
                base=real_resample_generator(train,n,int(seed),gen_cols,{})
            else:
                base=real_block_generator(train,n,int(seed),gen_cols,{})
            POS_SOURCES[(role,label,seed)] = jitter_continuous(
                base,train,gen_cols,sigma_iqr=sigma,seed=int(seed)+10000
            )

print("Constructed role-matched positive-control frames:",len(POS_SOURCES))
