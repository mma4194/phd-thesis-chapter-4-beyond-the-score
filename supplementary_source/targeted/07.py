
WASS_ROWS = []
fixture_seeds = list(map(int, CFG["instrument_fixture_seeds"]))
severities = [0.0, 0.25, 0.50, 0.75, 1.0]
n_fixture = 24000

for fixture_seed in fixture_seeds:
    base = build_controlled_iot_fixture(n=n_fixture, seed=fixture_seed)
    columns = [c for c in base.columns if not c.endswith("__nonfinite_mask")]
    for severity in severities:
        pert = perturb_fixture(
            base, "marginal", severity,
            seed=fixture_seed + int(100*severity) + len("marginal")
        )
        for column in columns:
            a = base[column].to_numpy(dtype=float)
            b = pert[column].to_numpy(dtype=float)
            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]
            if len(a) < 10 or len(b) < 10:
                continue
            raw_w = float(wasserstein_distance(a,b))
            ref_iqr = float(robust_iqr(a))
            denom = max(ref_iqr, 1e-6)  # EXACT denominator rule in canonical marginal_profile
            norm = raw_w / denom
            WASS_ROWS.append({
                "fixture_seed":fixture_seed,
                "severity":severity,
                "feature_name":column,
                "wasserstein_raw":raw_w,
                "reference_iqr":ref_iqr,
                "denominator_floor":1e-6,
                "denominator_used":denom,
                "floor_active":bool(ref_iqr < 1e-6),
                "wasserstein_iqr_normalised":norm,
            })

WASS_FEATURE = pd.DataFrame(WASS_ROWS)
WASS_FEATURE["share_within_seed_severity"] = (
    WASS_FEATURE["wasserstein_iqr_normalised"]
    / WASS_FEATURE.groupby(["fixture_seed","severity"])["wasserstein_iqr_normalised"].transform("sum").replace(0,np.nan)
)

agg = (
    WASS_FEATURE.groupby(["fixture_seed","severity"], as_index=False)
    .agg(
        reconstructed_mean=("wasserstein_iqr_normalised","mean"),
        median=("wasserstein_iqr_normalised","median"),
        max=("wasserstein_iqr_normalised","max"),
        min_reference_iqr=("reference_iqr","min"),
        n_floor_active=("floor_active","sum"),
        top1_share=("share_within_seed_severity","max"),
    )
)

frozen = INSTRUMENT_SEED[INSTRUMENT_SEED["perturbation"].eq("marginal")][
    ["fixture_seed","severity","wasserstein_iqr_mean"]
].copy()
check = agg.merge(frozen,on=["fixture_seed","severity"],how="left")
check["abs_diff"] = (check["reconstructed_mean"]-check["wasserstein_iqr_mean"]).abs()

display(check)
display(
    WASS_FEATURE[WASS_FEATURE["severity"].eq(1.0)]
    .sort_values(["fixture_seed","wasserstein_iqr_normalised"],ascending=[True,False])
    .groupby("fixture_seed").head(9)
)

WASS_FEATURE.to_csv(OUT/"WASS2_feature_level.csv",index=False)
check.to_csv(OUT/"WASS2_aggregate_reproduction.csv",index=False)

summary = {
    "max_abs_reproduction_error":float(check["abs_diff"].max()),
    "n_floor_active_total":int(WASS_FEATURE["floor_active"].sum()),
    "severity1_min_reference_iqr":float(WASS_FEATURE.loc[WASS_FEATURE.severity.eq(1.0),"reference_iqr"].min()),
    "severity1_max_top1_share":float(
        WASS_FEATURE[WASS_FEATURE.severity.eq(1.0)]
        .groupby("fixture_seed")["share_within_seed_severity"].max().max()
    ),
}
print(json.dumps(summary,indent=2))
write_json(OUT/"WASS2_summary.json",summary)
