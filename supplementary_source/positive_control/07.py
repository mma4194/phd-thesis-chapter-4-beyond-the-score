
# Exact utility evaluation; retain only the suite appropriate to the role.
utility=[]
for role in ["contemporaneous","temporal"]:
    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            src=POS_SOURCES[(role,label,seed)]
            spec=GeneratorSpec(
                generator_id=f"positive_control_{role}_{label}",
                family="posthoc_positive_control",
                cost_kind="posthoc",
                order_preserving=(role=="temporal"),
                release_eligible=False,
                required_for_core=False,
                params={"role":role,"sigma_iqr":sigma,"anchor":"real_resample" if role=="contemporaneous" else "real_block"}
            )
            u=evaluate_utility(
                src,spec,PRIMARY_SPLIT,int(seed),
                force_all_suites=False,
                evaluation_axis="future",
                task_models=VALID_TASK_MODELS,
            )
            u=apply_p0_licences(u,spec)
            u=u[u["suite"].eq(role)].copy()
            u["positive_control"]=label
            u["positive_control_role"]=role
            u["sigma_iqr"]=sigma
            utility.append(u)

POS_UTILITY=pd.concat(utility,ignore_index=True)
POS_UTILITY.to_csv(OUT/"POSCTRL_V41_utility.csv",index=False)

status=POS_UTILITY.groupby(["positive_control_role","positive_control","status"]).size().rename("n").reset_index()
display(status)

errors=POS_UTILITY[POS_UTILITY["status"].astype(str).str.startswith("error")]
print("Error rows:",len(errors))
if len(errors):
    display(errors[["positive_control_role","positive_control","task_id","model_id","error"]].head(50))
