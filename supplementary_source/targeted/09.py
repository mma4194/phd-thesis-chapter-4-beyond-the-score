
PRIMARY = METRICS[METRICS["fold_id"].eq("primary")].copy()
anchor_id = "real_resample"
# Include real_resample itself: the frozen 27-row resolution table contains the anchor
# as a self-comparison in each of the three scopes.
candidate_ids = sorted(PRIMARY["generator_id"].unique())

# The manuscript's 27-row resolution analysis is based on SAME-PERIOD C2ST,
# not future-transfer C2ST. These prefixes reproduce the frozen resolution table.
scope_map = {
    "protocol_value": "same_period",
    "all_modal": "same_period_all_modal",
    "mask_only": "same_period_mask_only",
}

rows=[]
for gid in candidate_ids:
    cand = PRIMARY[PRIMARY.generator_id.eq(gid)].sort_values("seed")
    anc = PRIMARY[PRIMARY.generator_id.eq(anchor_id)].sort_values("seed")
    common = sorted(set(cand.seed) & set(anc.seed))
    cand = cand[cand.seed.isin(common)].sort_values("seed")
    anc = anc[anc.seed.isin(common)].sort_values("seed")
    for scope, prefix in scope_map.items():
        crf = pd.to_numeric(cand[f"{prefix}_c2st_rf_auc"],errors="coerce").to_numpy(float)
        clin = pd.to_numeric(cand[f"{prefix}_c2st_linear_auc"],errors="coerce").to_numpy(float)
        cmax = pd.to_numeric(cand[f"{prefix}_c2st_max_auc"],errors="coerce").to_numpy(float)
        arf = pd.to_numeric(anc[f"{prefix}_c2st_rf_auc"],errors="coerce").to_numpy(float)
        alin = pd.to_numeric(anc[f"{prefix}_c2st_linear_auc"],errors="coerce").to_numpy(float)
        amax = pd.to_numeric(anc[f"{prefix}_c2st_max_auc"],errors="coerce").to_numpy(float)
        excess = cmax-amax
        rows.append({
            "generator_id":gid,"scope":scope,"n_seeds":len(common),
            "candidate_rf_auc":float(np.nanmean(crf)),
            "candidate_linear_auc":float(np.nanmean(clin)),
            "candidate_max_auc":float(np.nanmean(cmax)),
            "candidate_selection_gain":float(np.nanmean(cmax-np.maximum(crf,clin))), # should ~0 per seed
            "anchor_rf_auc":float(np.nanmean(arf)),
            "anchor_linear_auc":float(np.nanmean(alin)),
            "anchor_max_auc":float(np.nanmean(amax)),
            "excess_auc":float(np.nanmean(excess)),
            "excess_seed_sd":float(np.nanstd(excess,ddof=1)),
            "candidate_n_per_class":float(np.nanmean(pd.to_numeric(cand[f"{prefix}_c2st_n_per_class"],errors="coerce"))),
            "candidate_null_p95":float(np.nanmean(pd.to_numeric(cand[f"{prefix}_c2st_null_p95"],errors="coerce"))),
            "candidate_perm_p":float(np.nanmean(pd.to_numeric(cand[f"{prefix}_c2st_permutation_p"],errors="coerce"))),
        })

C2ST27 = pd.DataFrame(rows)
for ceiling in [0.9940,0.9945,0.9950,0.9955,0.9960]:
    tag=str(ceiling).replace(".","_")
    C2ST27[f"resolved_{tag}"] = (
        (C2ST27["candidate_max_auc"] < ceiling) &
        (C2ST27["anchor_max_auc"] < ceiling)
    )

C2ST27["candidate_headroom_0_995"] = 0.995-C2ST27["candidate_max_auc"]
C2ST27["anchor_headroom_0_995"] = 0.995-C2ST27["anchor_max_auc"]

display(C2ST27)
print("Rows:",len(C2ST27))
print(C2ST27[[c for c in C2ST27.columns if c.startswith("resolved_")]].sum())

C2ST27.to_csv(OUT/"C2ST2_primary_27_rows.csv",index=False)
