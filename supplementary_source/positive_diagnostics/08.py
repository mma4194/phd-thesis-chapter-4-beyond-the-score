
# ============================================================
# B1. Checkpointed direct C2ST
# ============================================================
scope_cols={
    "protocol_value":list(FEATURE_SCOPES["protocol_value_v3"]),
    "all_modal":list(FEATURE_SCOPES["all_value_v3"]),
    "mask_only":list(FEATURE_SCOPES["mask_only_v1"]),
}

C2ST_DIR=OUT/"checkpoints"/"direct_c2st"
C2ST_DIR.mkdir(parents=True,exist_ok=True)

total_jobs=2*2*len(SEEDS)*len(scope_cols)
job_no=0

for role in ["contemporaneous","temporal"]:
    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            if role=="contemporaneous":
                anchor=real_resample_generator(train,n,int(seed),gen_cols,{})
                anchor_id="real_resample"
            else:
                anchor=real_block_generator(train,n,int(seed),gen_cols,{})
                anchor_id="real_block"

            _,pos,_=make_positive_control_with_audit(
                anchor,train,gen_cols,sigma_iqr=sigma,seed=int(seed)+10000
            )

            for scope,cols in scope_cols.items():
                job_no+=1
                ck=C2ST_DIR/f"{role}__{label}__seed{seed}__{scope}.csv"
                if ck.exists():
                    print(f"[{job_no}/{total_jobs}] SKIP existing {ck.name}")
                    continue

                cols=[c for c in cols if c in anchor.columns and c in pos.columns]
                t0=time.time()
                print(f"[{job_no}/{total_jobs}] {role} / {label} / seed={seed} / {scope} / p={len(cols)}")

                m=c2st_profile(
                    anchor,pos,cols,
                    seed=int(seed),
                    row_cap=int(CFG["row_cap_metrics"]),
                    n_splits=int(CFG["c2st_splits"]),
                    n_permutations=int(CFG["c2st_permutations"]),
                    rf_trees=int(CFG["c2st_trees"]),
                    null_trees=int(CFG["c2st_null_trees"]),
                )

                row={
                    "role":role,"control":label,"sigma_iqr":sigma,"seed":int(seed),
                    "scope":scope,"anchor_id":anchor_id,
                    "n_features":len(cols),
                    "elapsed_seconds":time.time()-t0,
                    **m
                }
                pd.DataFrame([row]).to_csv(ck,index=False)
                print(f"    max_auc={m['c2st_max_auc']:.6f} null_p95={m['c2st_null_p95']:.6f} "
                      f"perm_p={m['c2st_permutation_p']:.4f} time={row['elapsed_seconds']/60:.1f}m")

            del anchor,pos
            gc.collect()

files=sorted(C2ST_DIR.glob("*.csv"))
if len(files)!=total_jobs:
    print(f"WARNING: only {len(files)}/{total_jobs} C2ST checkpoints exist.")
else:
    print("All direct C2ST checkpoints complete.")

DIRECT_C2ST=pd.concat([pd.read_csv(p) for p in files],ignore_index=True)
DIRECT_C2ST.to_csv(OUT/"tables"/"POSCTRL_V42_direct_anchor_c2st.csv",index=False)

DIRECT_C2ST_SUMMARY=(
    DIRECT_C2ST
    .groupby(["role","control","scope"])
    .agg(
        n=("c2st_max_auc","size"),
        max_auc_mean=("c2st_max_auc","mean"),
        max_auc_sd=("c2st_max_auc","std"),
        max_auc_median=("c2st_max_auc","median"),
        null_p95_mean=("c2st_null_p95","mean"),
        excess_over_null_mean=("c2st_excess_over_null_p95","mean"),
        permutation_p_median=("c2st_permutation_p","median"),
    )
    .reset_index()
)

display(DIRECT_C2ST_SUMMARY)
DIRECT_C2ST_SUMMARY.to_csv(OUT/"tables"/"POSCTRL_V42_direct_anchor_c2st_summary.csv",index=False)

# Paired strong-minus-mild direct AUC.
direct_paired=(
    DIRECT_C2ST
    .pivot_table(index=["role","scope","seed"],columns="control",values="c2st_max_auc",aggfunc="first")
    .reset_index()
)
direct_paired["strong_minus_mild_auc"]=direct_paired["strong"]-direct_paired["mild"]
display(
    direct_paired.groupby(["role","scope"])["strong_minus_mild_auc"]
    .agg(["count","mean","median","min","max"]).reset_index()
)
direct_paired.to_csv(OUT/"tables"/"POSCTRL_V42_direct_c2st_mild_vs_strong.csv",index=False)
