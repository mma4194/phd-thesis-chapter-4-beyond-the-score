
# Compact scientific summary for valid, P0-licensed utility rows.
ok=POS_UTILITY[
    POS_UTILITY["status"].eq("ok") &
    POS_UTILITY["p0_licensed"].fillna(False).astype(bool) &
    POS_UTILITY["loss_ratio"].notna()
].copy()

summ=[]
for (role,ctl),g in ok.groupby(["positive_control_role","positive_control"]):
    lr=pd.to_numeric(g["loss_ratio"],errors="coerce")
    ni=pd.to_numeric(g["noninferior"],errors="coerce")
    summ.append({
        "role":role,
        "control":ctl,
        "n_ok_licensed":len(g),
        "geometric_mean_loss_ratio":float(np.exp(np.nanmean(np.log(lr)))),
        "median_loss_ratio":float(np.nanmedian(lr)),
        "noninferior_rate":float(np.nanmean(ni)),
        "n_unique_capabilities":int(g["capability"].nunique()),
        "n_unique_task_families":int(g["task_family"].nunique()),
    })
SUMMARY=pd.DataFrame(summ)
display(SUMMARY)
SUMMARY.to_csv(OUT/"POSCTRL_V41_summary.csv",index=False)

gate={
    "utility_error_rows":int(POS_UTILITY["status"].astype(str).str.startswith("error").sum()),
    "c2st_rows":int(len(POS_C2ST)),
    "utility_rows":int(len(POS_UTILITY)),
    "ready_for_scientific_interpretation":bool(
        POS_UTILITY["status"].astype(str).str.startswith("error").sum()==0
    ),
}
write_json(OUT/"POSCTRL_V41_gate.json",gate)
print(json.dumps(gate,indent=2))
