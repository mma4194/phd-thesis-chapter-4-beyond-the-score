
# C2ST relative to role-matched frozen real anchors.
test=CANON_DF.iloc[PRIMARY_SPLIT["test"]].reset_index(drop=True)
scope_cols={
    "protocol_value":list(FEATURE_SCOPES["protocol_value_v3"]),
    "all_modal":list(FEATURE_SCOPES["all_value_v3"]),
    "mask_only":list(FEATURE_SCOPES["mask_only_v1"]),
}

rows=[]
for role in ["contemporaneous","temporal"]:
    anchor_id="real_resample" if role=="contemporaneous" else "real_block"
    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            src=POS_SOURCES[(role,label,seed)]
            for scope,cols in scope_cols.items():
                cols=[c for c in cols if c in src.columns and c in test.columns]
                m=c2st_profile(
                    test,src,cols,seed=int(seed),
                    row_cap=int(CFG["row_cap_metrics"]),
                    n_splits=int(CFG["c2st_splits"]),
                    n_permutations=int(CFG["c2st_permutations"]),
                    rf_trees=int(CFG["c2st_trees"]),
                    null_trees=int(CFG["c2st_null_trees"]),
                )
                frozen=FROZEN_METRICS[
                    (FROZEN_METRICS.fold_id=="primary") &
                    (FROZEN_METRICS.generator_id==anchor_id) &
                    (FROZEN_METRICS.seed==seed)
                ].iloc[0]
                prefix={"protocol_value":"same_period","all_modal":"same_period_all_modal","mask_only":"same_period_mask_only"}[scope]
                anchor_auc=float(frozen[f"{prefix}_c2st_max_auc"])
                rows.append({
                    "role":role,"control":label,"sigma_iqr":sigma,"seed":seed,
                    "scope":scope,"anchor_id":anchor_id,
                    "candidate_c2st_max_auc":m["c2st_max_auc"],
                    "anchor_c2st_max_auc":anchor_auc,
                    "delta_auc":m["c2st_max_auc"]-anchor_auc,
                    "candidate_null_p95":m["c2st_null_p95"],
                    "candidate_permutation_p":m["c2st_permutation_p"],
                })

POS_C2ST=pd.DataFrame(rows)
POS_C2ST.to_csv(OUT/"POSCTRL_V41_C2ST_relative_to_anchor.csv",index=False)
display(POS_C2ST.groupby(["role","control","scope"])[["candidate_c2st_max_auc","anchor_c2st_max_auc","delta_auc"]].agg(["mean","std"]))
