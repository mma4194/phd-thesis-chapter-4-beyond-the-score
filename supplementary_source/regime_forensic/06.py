
# ============================================================
# 4. Audit all frozen P0 matches: were they actually cross-regime?
# ============================================================
PAIR_ROWS=[]
for fs in FIXTURE_SEEDS:
    pairs=pd.read_csv(FULL/"tables"/"p0"/"regime_unstable"/f"fixture{fs}"/"matched_pairs.csv")
    for _,r in pairs.iterrows():
        sr=int(r["source_block"]); tr=int(r["target_block"])
        PAIR_ROWS.append({
            "fixture_seed":fs,"pair_id":r["pair_id"],"phase":r["phase"],
            "source_block":sr,"target_block":tr,
            "source_regime":0 if sr<10 else 1,
            "target_regime":0 if tr<10 else 1,
            "cross_regime":(sr<10)!=(tr<10),
            "profile_distance":float(r["profile_distance"])
        })
PAIR_AUDIT=pd.DataFrame(PAIR_ROWS)
display(PAIR_AUDIT)
print("Cross-regime matched pairs:",int(PAIR_AUDIT.cross_regime.sum()),"/",len(PAIR_AUDIT))
PAIR_AUDIT.to_csv(FORENSIC_ROOT/"tables"/"KT10_matched_pair_regime_audit.csv",index=False)
