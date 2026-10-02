
# Exact C2ST + exact utility evaluation for the positive control.
if RUN_NEW_EXPERIMENTS:
    pos_metric_rows=[]
    pos_utility_rows=[]

    scope_cols={
        "protocol_value":list(FEATURE_SCOPES["protocol_value_v3"]),
        "all_modal":list(FEATURE_SCOPES["all_value_v3"]),
        "mask_only":list(FEATURE_SCOPES["mask_only_v1"]),
    }

    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            src=POS_SOURCES[(label,seed)]
            spec=GeneratorSpec(
                generator_id=f"positive_control_{label}",
                family="posthoc_positive_control",
                cost_kind="posthoc",
                order_preserving=True,
                release_eligible=False,
                required_for_core=False,
                params={"sigma_iqr":sigma,"selection":"prespecified_train_only"},
            )
            # Candidate compared with future TEST using exact canonical C2ST function.
            test=CANON_DF.iloc[PRIMARY_SPLIT["test"]].reset_index(drop=True)
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
                pos_metric_rows.append({
                    "control":label,"sigma_iqr":sigma,"seed":seed,"scope":scope,**m
                })

            # Exact canonical downstream utility evaluator.
            u=evaluate_utility(
                src,spec,PRIMARY_SPLIT,int(seed),
                force_all_suites=False,
                evaluation_axis="future",
                task_models=VALID_TASK_MODELS,
            )
            u=apply_p0_licences(u,spec)
            u["positive_control"]=label
            u["sigma_iqr"]=sigma
            pos_utility_rows.append(u)

    POS_METRICS=pd.DataFrame(pos_metric_rows)
    POS_UTILITY=pd.concat(pos_utility_rows,ignore_index=True)
    POS_METRICS.to_csv(OUT/"POSCTRL1_metrics.csv",index=False)
    POS_UTILITY.to_csv(OUT/"POSCTRL1_utility.csv",index=False)
    display(POS_METRICS.groupby(["control","scope"])["c2st_max_auc"].agg(["mean","min","max"]))
    display(POS_UTILITY.groupby(["positive_control","suite","status"]).size().rename("n").reset_index())
else:
    print("Skipped POSCTRL evaluation")
