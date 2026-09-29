
# ============================================================
# A1. Exact v4.1 transformation, but return pre/post projection
# ============================================================
def make_positive_control_with_audit(base, train_support, columns, sigma_iqr, seed):
    rng=np.random.default_rng(seed)
    raw=base[list(columns)].copy().reset_index(drop=True)
    eligibility={}

    for c in columns:
        if c.endswith("__nonfinite_mask"):
            eligibility[c]={"eligible":False,"reason":"mask"}
            continue

        tr=train_support[c].to_numpy(float,copy=False)
        finite=tr[np.isfinite(tr)]
        if len(finite)<20:
            eligibility[c]={"eligible":False,"reason":"insufficient_finite"}
            continue

        sup=infer_column_support(finite)
        iqr=float(robust_iqr(finite))
        if sup["binary"]:
            eligibility[c]={"eligible":False,"reason":"binary","train_iqr":iqr}
            continue
        if sup["integer_like"]:
            eligibility[c]={"eligible":False,"reason":"integer_like","train_iqr":iqr}
            continue
        if iqr<=1e-9:
            eligibility[c]={"eligible":False,"reason":"zero_iqr","train_iqr":iqr}
            continue

        x=raw[c].to_numpy(float,copy=True)
        x += rng.normal(0.0,sigma_iqr*iqr,size=len(x))
        raw[c]=x
        eligibility[c]={"eligible":True,"reason":"jittered","train_iqr":iqr}

    projected=project_frame_to_train_support(raw,train_support[list(columns)],columns)
    return raw,projected,eligibility

train=CANON_DF.iloc[PRIMARY_SPLIT["train"]].reset_index(drop=True)
gen_cols=list(FEATURE_SCOPES["generator_v2"])
n=int(CFG["generation_rows"])

realisation_rows=[]
summary_rows=[]

for role in ["contemporaneous","temporal"]:
    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            if role=="contemporaneous":
                anchor=real_resample_generator(train,n,int(seed),gen_cols,{})
            else:
                anchor=real_block_generator(train,n,int(seed),gen_cols,{})

            raw,pos,elig=make_positive_control_with_audit(
                anchor,train,gen_cols,sigma_iqr=sigma,seed=int(seed)+10000
            )

            for c in gen_cols:
                a=anchor[c].to_numpy(float,copy=False)
                r=raw[c].to_numpy(float,copy=False)
                p=pos[c].to_numpy(float,copy=False)

                info=elig.get(c,{"eligible":False,"reason":"unknown"})
                iqr=float(info.get("train_iqr",robust_iqr(train[c].to_numpy(float,copy=False))))
                scale=iqr if iqr>1e-12 else np.nan

                raw_abs=np.abs(r-a)
                post_abs=np.abs(p-a)
                raw_changed=np.abs(r-a)>1e-12
                post_changed=np.abs(p-a)>1e-12
                projection_changed=np.abs(p-r)>1e-12
                collapsed=raw_changed & (~post_changed)

                realisation_rows.append({
                    "role":role,"control":label,"sigma_iqr":sigma,"seed":int(seed),
                    "feature_name":c,
                    "eligible_for_jitter":bool(info.get("eligible",False)),
                    "eligibility_reason":info.get("reason","unknown"),
                    "train_iqr":iqr,
                    "raw_fraction_changed":float(np.mean(raw_changed)),
                    "post_fraction_changed":float(np.mean(post_changed)),
                    "raw_mean_abs_change":float(np.mean(raw_abs)),
                    "post_mean_abs_change":float(np.mean(post_abs)),
                    "raw_median_abs_change":float(np.median(raw_abs)),
                    "post_median_abs_change":float(np.median(post_abs)),
                    "raw_mean_abs_change_iqr":float(np.mean(raw_abs)/scale) if np.isfinite(scale) else np.nan,
                    "post_mean_abs_change_iqr":float(np.mean(post_abs)/scale) if np.isfinite(scale) else np.nan,
                    "projection_fraction_changed":float(np.mean(projection_changed)),
                    "projection_collapse_fraction":float(np.mean(collapsed)),
                })

            del anchor,raw,pos
            gc.collect()

REALISATION=pd.DataFrame(realisation_rows)
REALISATION.to_csv(OUT/"tables"/"POSCTRL_V42_perturbation_realisation_feature_level.csv",index=False)

REALISATION_SUMMARY=(
    REALISATION[REALISATION["eligible_for_jitter"]]
    .groupby(["role","control"])
    .agg(
        n_feature_seed_rows=("feature_name","size"),
        n_unique_features=("feature_name","nunique"),
        median_post_fraction_changed=("post_fraction_changed","median"),
        median_post_mean_abs_change_iqr=("post_mean_abs_change_iqr","median"),
        mean_post_mean_abs_change_iqr=("post_mean_abs_change_iqr","mean"),
        median_projection_fraction_changed=("projection_fraction_changed","median"),
        median_projection_collapse_fraction=("projection_collapse_fraction","median"),
    )
    .reset_index()
)

display(REALISATION_SUMMARY)
REALISATION_SUMMARY.to_csv(OUT/"tables"/"POSCTRL_V42_perturbation_realisation_summary.csv",index=False)

# Paired strong:mild realised-severity ratio by role/feature/seed.
paired=(
    REALISATION[REALISATION["eligible_for_jitter"]]
    .pivot_table(
        index=["role","feature_name","seed"],
        columns="control",
        values="post_mean_abs_change_iqr",
        aggfunc="first"
    )
    .reset_index()
)
paired["strong_to_mild_realised_ratio"]=paired["strong"]/paired["mild"].replace(0,np.nan)
display(
    paired.groupby("role")["strong_to_mild_realised_ratio"]
    .agg(["count","median","mean","min","max"])
    .reset_index()
)
paired.to_csv(OUT/"tables"/"POSCTRL_V42_realised_strong_to_mild_ratio.csv",index=False)
