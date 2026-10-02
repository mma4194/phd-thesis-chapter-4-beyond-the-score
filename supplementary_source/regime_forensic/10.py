
# ============================================================
# 7. Does KT10 violate "contemporaneous dependency" or "regime invariance"?
# ============================================================
SEMANTIC=[]
for fs in FIXTURE_SEEDS:
    d=DGP_AUDIT[DGP_AUDIT.fixture_seed==fs].set_index("regime")
    slope_flip=(
        np.sign(d.loc[0,"router_packets_slope"]) != np.sign(d.loc[1,"router_packets_slope"])
        and np.sign(d.loc[0,"ota_frames_slope"]) != np.sign(d.loc[1,"ota_frames_slope"])
    )
    dependency_present_both=(
        abs(d.loc[0,"corr_router_packets_power"])>0.1
        and abs(d.loc[1,"corr_router_packets_power"])>0.1
    )
    ref=DERIVATION[DERIVATION.fixture_seed==fs].iloc[0]
    absolute_transfer_bad=(
        ref["median_absolute_reference_skill_gain"] <= 0
        or ref["median_absolute_reference_r2"] <= 0
    )
    SEMANTIC.append({
        "fixture_seed":fs,
        "relationship_sign_flip":bool(slope_flip),
        "contemporaneous_dependency_present_in_both_regimes":bool(dependency_present_both),
        "absolute_cross_regime_transfer_bad":bool(absolute_transfer_bad),
        "stage3_relative_identity_passed":bool(ref["identity_passed"]),
        "stage3_relative_resample_property_passed":bool(ref["property_passed"]),
    })
SEMANTIC=pd.DataFrame(SEMANTIC)
display(SEMANTIC)
SEMANTIC.to_csv(FORENSIC_ROOT/"tables"/"KT10_semantic_contract_audit.csv",index=False)

print("""
Interpretive distinction:
- The planted DGP *does* violate relationship invariance / cross-regime transportability.
- It does *not* remove contemporaneous dependence inside either regime.
- The frozen capability name only states 'contemporaneous_dependency|regime_power';
  therefore the truth label assumes that Stage 3 is meant to require transportable/stable
  dependence across matched real blocks, not merely existence of within-regime dependence.
""")
