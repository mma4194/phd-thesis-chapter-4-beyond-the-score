if RUN_C2ST_CAPACITY_DIAGNOSTIC:
    
    C2ST_CAPACITY_ROWS=[]
    base = build_controlled_iot_fixture(24000, seed=19)
    cols=[c for c in base.columns if not c.endswith("__nonfinite_mask")]
    same = base.copy()
    mild = perturb_fixture(base,"marginal",0.25,seed=19+25+len("marginal"))
    
    for label, syn in [("same_distribution",same),("marginal_0.25",mild)]:
        for total_cap in [2000,5000,10000,12000,20000,40000]:
            result = c2st_profile(
                base,syn,cols,seed=19001+total_cap,
                row_cap=total_cap,
                n_splits=int(CFG["c2st_splits"]),
                n_permutations=9,
                rf_trees=int(CFG["c2st_trees"]),
                null_trees=int(CFG["c2st_null_trees"]),
            )
            C2ST_CAPACITY_ROWS.append({"condition":label,"row_cap_total":total_cap,**result})
    
    C2ST_CAPACITY=pd.DataFrame(C2ST_CAPACITY_ROWS)
    display(C2ST_CAPACITY[[
        "condition","row_cap_total","c2st_n_per_class","c2st_rf_auc",
        "c2st_linear_auc","c2st_max_auc","c2st_null_p95",
        "c2st_excess_over_null_p95","c2st_permutation_p"
    ]])
    C2ST_CAPACITY.to_csv(OUT/"C2ST2_controlled_sample_size_response.csv",index=False)
else:
    print('Skipped optional repeated-fit C2ST capacity diagnostic; frozen 27-row audit still runs.')