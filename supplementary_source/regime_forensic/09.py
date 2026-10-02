
# ============================================================
# 6. Exact Stage-3 decision ledger and derivation
# ============================================================
DECISION_ROWS=[]
LICENCE_ROWS=[]
for fs in FIXTURE_SEEDS:
    base=FULL/"tables"/"p0"/"regime_unstable"/f"fixture{fs}"
    dec=pd.read_csv(base/"table_p0_harness_qualification.csv",low_memory=False)
    dec["fixture_seed"]=fs
    DECISION_ROWS.append(dec)

    lic=pd.read_csv(base/"table_p0_capability_licences.csv",low_memory=False)
    lic["fixture_seed"]=fs
    LICENCE_ROWS.append(lic)

DECISIONS=pd.concat(DECISION_ROWS,ignore_index=True)
LICENCES=pd.concat(LICENCE_ROWS,ignore_index=True)

kt_dec=DECISIONS[
    DECISIONS["capability"].astype(str).eq(EXPECTED_KT10_CAPABILITY)
].copy()
kt_lic=LICENCES[
    LICENCES["capability"].astype(str).eq(EXPECTED_KT10_CAPABILITY)
].copy()

display(kt_dec)
display(kt_lic)

kt_dec.to_csv(FORENSIC_ROOT/"tables"/"KT10_stage3_exact_decisions.csv",index=False)
kt_lic.to_csv(FORENSIC_ROOT/"tables"/"KT10_stage3_exact_licences.csv",index=False)

# Derive the two contemporaneous decisions from raw completed P0 utility rows.
derive=[]
for fs in FIXTURE_SEEDS:
    x=P0U[(P0U.fixture_seed==fs)&(P0U.p0_phase=="qualification")]
    identity=x[x.p0_anchor=="real_identity"]["log_loss_ratio"].dropna()
    resample=x[x.p0_anchor=="real_resample"]["log_loss_ratio"].dropna()

    # The exact reported CIs/thresholds are read from the frozen decision table rather than re-bootstrapped.
    di=kt_dec[(kt_dec.fixture_seed==fs)&(kt_dec.criterion=="identity_equivalence")&
              (kt_dec.suite=="contemporaneous")].iloc[0]
    dr=kt_dec[(kt_dec.fixture_seed==fs)&(kt_dec.criterion=="matched_block_resample_equivalence")&
              (kt_dec.suite=="contemporaneous")].iloc[0]

    ref=x[x.p0_anchor=="real_identity"]
    derive.append({
        "fixture_seed":fs,
        "identity_raw_max_abs_log_ratio":float(identity.abs().max()),
        "identity_decision_estimate":float(di["estimate"]),
        "identity_ci_lo":float(di["ci_lo"]),
        "identity_ci_hi":float(di["ci_hi"]),
        "identity_passed":bool(di["passed"]),
        "property_resample_median_log_ratio":float(resample.median()),
        "property_decision_estimate":float(dr["estimate"]),
        "property_ci_lo":float(dr["ci_lo"]),
        "property_ci_hi":float(dr["ci_hi"]),
        "property_passed":bool(dr["passed"]),
        "median_absolute_reference_skill_gain":float(ref["reference_skill_gain"].median()),
        "median_absolute_reference_r2":float(ref["reference_r2"].median()),
        "fraction_reference_skill_positive":float((ref["reference_skill_gain"]>0).mean()),
        "fraction_reference_r2_positive":float((ref["reference_r2"]>0).mean()),
    })
DERIVATION=pd.DataFrame(derive)
display(DERIVATION)
DERIVATION.to_csv(FORENSIC_ROOT/"tables"/"KT10_stage3_derivation.csv",index=False)
