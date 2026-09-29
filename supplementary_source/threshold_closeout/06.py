
u = UTILITY.copy()
ratio = pd.to_numeric(u["training_sample_size_ratio"], errors="coerce")
valid = ratio.notna()
nonparity = valid & ~np.isclose(ratio,1.0,rtol=0,atol=1e-12)
n_diff = (
    u["n_train"].notna() & u["n_reference_train"].notna() &
    (pd.to_numeric(u["n_train"],errors="coerce") != pd.to_numeric(u["n_reference_train"],errors="coerce"))
)
SAMPLE_PARITY = {
    "rows_total":len(u),
    "rows_with_accounting":int(valid.sum()),
    "rows_nonparity":int(nonparity.sum()),
    "rows_ntrain_reference_difference":int(n_diff.sum()),
    "unique_nonmissing_ratios":sorted(ratio.dropna().unique().tolist()),
}
print(json.dumps(SAMPLE_PARITY,indent=2))
display(u.groupby("generator_id")["training_sample_size_ratio"].agg(["count","min","max","mean"]))

u.loc[nonparity].to_csv(OUTPUT/"sample_budget_nonparity_rows.csv",index=False)
