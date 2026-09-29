
def p0_seed_summary(raw):
    valid = raw[(raw["status"] == "ok") & raw["log_loss_ratio"].notna()].copy()
    fam = valid.groupby(
        ["p0_phase","p0_pair_id","seed","p0_anchor","suite","capability","task_family"],
        dropna=False
    ).agg(
        log_loss_ratio=("log_loss_ratio","median"),
        noninferior=("noninferior","mean"),
    ).reset_index()
    cap = fam.groupby(
        ["p0_phase","p0_pair_id","seed","p0_anchor","suite","capability"],
        dropna=False
    ).agg(
        log_loss_ratio=("log_loss_ratio","mean"),
        noninferiority_rate=("noninferior","mean"),
    ).reset_index()
    return cap.rename(columns={"p0_pair_id":"pair_id"})

S = p0_seed_summary(P0_UTILITY)

def pivot(phase, suite, capability, value):
    x = S[(S.p0_phase==phase) & (S.suite==suite) & (S.capability==capability)]
    return x.pivot_table(index=["pair_id","seed"], columns="p0_anchor", values=value, aggfunc="first").reset_index()

def hierarchical_q(df, q=.9):
    if df.empty:
        return np.nan
    mat = df.pivot_table(index="pair_id", columns="seed", values="value", aggfunc="first").to_numpy(float)
    if mat.size == 0:
        return np.nan
    per_pair = np.nanquantile(mat, q, axis=1)
    per_pair = per_pair[np.isfinite(per_pair)]
    return float(np.quantile(per_pair, q)) if len(per_pair) else np.nan

rows=[]
for _, r in P0_MARGINS.iterrows():
    cap = r.capability
    # contemporaneous raw margin
    xs = pivot("calibration","contemporaneous",cap,"log_loss_ratio")
    if {"real_block_a","real_block_b"}.issubset(xs.columns):
        d = xs[["pair_id","seed"]].copy()
        d["value"] = np.abs(xs["real_block_a"] - xs["real_block_b"])
        raw_xs = hierarchical_q(d.dropna(), float(r.calibration_quantile))
    else:
        raw_xs = np.nan

    # temporal raw ratio
    tp = pivot("calibration","temporal",cap,"log_loss_ratio")
    if {"real_block_a","real_block_b"}.issubset(tp.columns):
        d = tp[["pair_id","seed"]].copy()
        d["value"] = 0.5*(tp["real_block_a"]+tp["real_block_b"])
        raw_log = hierarchical_q(d.dropna(), float(r.calibration_quantile))
        raw_tp = float(np.exp(raw_log)) if np.isfinite(raw_log) else np.nan
    else:
        raw_tp = np.nan

    rows.append({
        "capability":cap,
        "raw_xs_margin":raw_xs,
        "applied_xs_margin":r.contemporaneous_log_margin,
        "xs_binding":"floor" if np.isfinite(raw_xs) and raw_xs < r.xs_floor else ("ceiling" if np.isfinite(raw_xs) and raw_xs > r.xs_ceiling else "none"),
        "raw_temporal_ratio":raw_tp,
        "applied_temporal_ratio":r.temporal_loss_ratio_max,
        "temporal_binding":"floor" if np.isfinite(raw_tp) and raw_tp < r.temporal_floor else ("ceiling" if np.isfinite(raw_tp) and raw_tp > r.temporal_ceiling else "none"),
    })

RAW = pd.DataFrame(rows)

# Reconstruct raw-vs-applied capability decisions from already frozen qualification CIs.
out=[]
for cap in RAW.capability:
    rr = RAW[RAW.capability==cap].iloc[0]
    lic = P0_LICENSES[P0_LICENSES.capability==cap]
    for suite in ["contemporaneous","temporal"]:
        lr = lic[lic.suite==suite]
        if lr.empty or not bool(lr.iloc[0].eligible):
            continue
        applied = bool(lr.iloc[0].licensed)
        h = P0_HARNESS[(P0_HARNESS.capability==cap)&(P0_HARNESS.suite==suite)]
        ident = h[h.criterion=="identity_equivalence"]
        identity_ok = bool(ident.iloc[0].passed) if len(ident) else False
        if suite=="contemporaneous":
            q = h[h.criterion=="matched_block_resample_equivalence"]
            if len(q) and np.isfinite(rr.raw_xs_margin):
                raw_property_ok = (
                    float(q.iloc[0].ci_lo) >= -rr.raw_xs_margin and
                    float(q.iloc[0].ci_hi) <= rr.raw_xs_margin
                )
                raw_licensed = bool(identity_ok and raw_property_ok)
            else:
                raw_licensed = False
        else:
            q = h[h.criterion=="matched_block_temporal_transfer"]
            order = h[h.criterion=="row_resample_order_destruction"]
            if len(q) and np.isfinite(rr.raw_temporal_ratio):
                ni = q.iloc[0].noninferiority_rate
                raw_block_ok = (
                    float(q.iloc[0].ci_hi) <= rr.raw_temporal_ratio and
                    np.isfinite(ni) and float(ni) >= 0.75
                )
                order_ok = bool(order.iloc[0].passed) if len(order) else False
                raw_licensed = bool(identity_ok and raw_block_ok and order_ok)
            else:
                raw_licensed = False
        out.append({
            "capability":cap,"suite":suite,
            "applied_licensed":applied,
            "raw_licensed":raw_licensed,
            "changed":applied!=raw_licensed
        })

RAW_DECISIONS = pd.DataFrame(out)
display(RAW)
display(RAW_DECISIONS)

print("State changes:", int(RAW_DECISIONS.changed.sum()))
RAW.to_csv(OUTPUT/"p0_raw_vs_applied_margins.csv",index=False)
RAW_DECISIONS.to_csv(OUTPUT/"p0_raw_vs_applied_decisions.csv",index=False)
