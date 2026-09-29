
wq = INST_QUAL[INST_QUAL.instrument=="wasserstein_iqr_mean"].copy()
print("Frozen qualification row:")
display(wq)

ws = INST_SEED[INST_SEED.perturbation=="marginal"].copy()
print("Per-seed/per-severity aggregate Wasserstein/IQR:")
display(ws[["fixture_seed","severity","wasserstein_iqr_mean","marginal_n_features"]])

# We can independently verify the frozen aggregate endpoint from the seed-level ledger:
endpoint_by_seed = ws[ws.severity==1.0]["wasserstein_iqr_mean"]
baseline_by_seed = ws[ws.severity==0.0]["wasserstein_iqr_mean"]
endpoint_effect_from_seed_table = float(endpoint_by_seed.mean() - baseline_by_seed.mean())
reported = float(wq.iloc[0].endpoint_effect) if len(wq) else np.nan
print("Recomputed aggregate endpoint effect:", endpoint_effect_from_seed_table)
print("Reported Table 5 endpoint effect:", reported)
print("Absolute difference:", abs(endpoint_effect_from_seed_table-reported))

# Important limitation: the evidence package contains aggregate per-seed values,
# not the per-feature raw Wasserstein numerator and IQR denominator required to
# rule out domination by near-zero IQR. This remains a targeted Stage-1 rerun/audit.
WASS_STATUS = {
    "aggregate_reproduced": bool(np.isfinite(reported) and abs(endpoint_effect_from_seed_table-reported) < 1e-8),
    "feature_level_denominator_audit_available": False,
    "required_next_step": "rerun controlled fixture with per-feature raw Wasserstein and reference-IQR logging"
}
print(json.dumps(WASS_STATUS,indent=2))
