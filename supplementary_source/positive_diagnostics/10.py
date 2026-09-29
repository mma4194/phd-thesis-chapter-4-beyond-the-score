
# ============================================================
# C1. Exact row-level anchor join
# ============================================================
anchor_map={"contemporaneous":"real_resample","temporal":"real_block"}

pos=POS_UTILITY.copy()
pos["anchor_generator_id"]=pos["positive_control_role"].map(anchor_map)

anchor=FROZEN_UTILITY[
    FROZEN_UTILITY["fold_id"].eq("primary") &
    FROZEN_UTILITY["evaluation_axis"].eq("future") &
    FROZEN_UTILITY["generator_id"].isin(anchor_map.values())
].copy()

# Match exact seed/card/task/model/suite to the corresponding role-specific anchor.
join_keys=["seed","card_id","task_id","model_id","suite"]
anchor_keep=join_keys+[
    "generator_id","status","synthetic_loss","reference_loss","loss_ratio",
    "noninferior","p0_licensed","scientific_status"
]
anchor=anchor[anchor_keep].rename(columns={
    "generator_id":"anchor_generator_id",
    "status":"anchor_status",
    "synthetic_loss":"anchor_synthetic_loss",
    "reference_loss":"anchor_reference_loss",
    "loss_ratio":"anchor_loss_ratio_vs_trtr",
    "noninferior":"anchor_noninferior",
    "p0_licensed":"anchor_p0_licensed",
    "scientific_status":"anchor_scientific_status",
})

joined=pos.merge(
    anchor,
    on=join_keys+["anchor_generator_id"],
    how="left",
    validate="many_to_one",
    indicator=True
)

JOIN_AUDIT=joined["_merge"].value_counts(dropna=False).rename_axis("merge_status").reset_index(name="n")
display(JOIN_AUDIT)
JOIN_AUDIT.to_csv(OUT/"tables"/"POSCTRL_V42_anchor_utility_join_audit.csv",index=False)

joined["pos_synthetic_loss_num"]=pd.to_numeric(joined["synthetic_loss"],errors="coerce")
joined["anchor_synthetic_loss_num"]=pd.to_numeric(joined["anchor_synthetic_loss"],errors="coerce")
joined["anchor_relative_loss_ratio"]=(
    joined["pos_synthetic_loss_num"] /
    joined["anchor_synthetic_loss_num"].where(joined["anchor_synthetic_loss_num"]>1e-12)
)
joined["anchor_relative_loss_delta"]=joined["pos_synthetic_loss_num"]-joined["anchor_synthetic_loss_num"]
joined["pos_no_worse_than_anchor"]=joined["anchor_relative_loss_ratio"]<=1.0

joined.to_csv(OUT/"tables"/"POSCTRL_V42_anchor_relative_utility_rows.csv",index=False)

# Primary interpretable subset: v4.1 row OK, licensed, matched anchor loss finite.
valid=joined[
    joined["status"].eq("ok") &
    joined["p0_licensed"].fillna(False).astype(bool) &
    joined["anchor_relative_loss_ratio"].replace([np.inf,-np.inf],np.nan).notna()
].copy()

UTILITY_ANCHOR_SUMMARY=(
    valid.groupby(["positive_control_role","positive_control"])
    .agg(
        n=("anchor_relative_loss_ratio","size"),
        median_anchor_relative_loss_ratio=("anchor_relative_loss_ratio","median"),
        mean_anchor_relative_loss_ratio=("anchor_relative_loss_ratio","mean"),
        geometric_mean_anchor_relative_loss_ratio=(
            "anchor_relative_loss_ratio",
            lambda s: float(np.exp(np.mean(np.log(s[(s>0)&np.isfinite(s)])))) if np.any((s>0)&np.isfinite(s)) else np.nan
        ),
        median_anchor_relative_loss_delta=("anchor_relative_loss_delta","median"),
        no_worse_than_anchor_rate=("pos_no_worse_than_anchor","mean"),
        n_capabilities=("capability","nunique"),
        n_task_families=("task_family","nunique"),
    )
    .reset_index()
)

display(UTILITY_ANCHOR_SUMMARY)
UTILITY_ANCHOR_SUMMARY.to_csv(OUT/"tables"/"POSCTRL_V42_anchor_relative_utility_summary.csv",index=False)

UTILITY_CAPABILITY=(
    valid.groupby(["positive_control_role","positive_control","capability"])
    .agg(
        n=("anchor_relative_loss_ratio","size"),
        median_anchor_relative_loss_ratio=("anchor_relative_loss_ratio","median"),
        mean_anchor_relative_loss_ratio=("anchor_relative_loss_ratio","mean"),
        no_worse_than_anchor_rate=("pos_no_worse_than_anchor","mean"),
        n_task_families=("task_family","nunique"),
    )
    .reset_index()
)
display(UTILITY_CAPABILITY)
UTILITY_CAPABILITY.to_csv(OUT/"tables"/"POSCTRL_V42_anchor_relative_utility_by_capability.csv",index=False)

# Paired strong-minus-mild on exact task/model/seed rows.
u_pair=(
    valid.pivot_table(
        index=["positive_control_role","seed","card_id","task_id","model_id","suite"],
        columns="positive_control",
        values="anchor_relative_loss_ratio",
        aggfunc="first"
    )
    .reset_index()
)
u_pair["strong_minus_mild_anchor_relative_ratio"]=u_pair["strong"]-u_pair["mild"]
display(
    u_pair.groupby("positive_control_role")["strong_minus_mild_anchor_relative_ratio"]
    .agg(["count","mean","median","min","max"]).reset_index()
)
u_pair.to_csv(OUT/"tables"/"POSCTRL_V42_anchor_utility_mild_vs_strong.csv",index=False)
