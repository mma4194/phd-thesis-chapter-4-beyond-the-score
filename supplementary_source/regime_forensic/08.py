
# ============================================================
# 5. Read every completed KT10 P0 utility row
# ============================================================
UTILITY=[]
for fs in FIXTURE_SEEDS:
    cpdir=FULL/"checkpoints"/"p0"/"regime_unstable"/f"fixture{fs}"
    for p in sorted(cpdir.glob("*.utility.csv")):
        x=pd.read_csv(p,low_memory=False)
        if len(x):
            x["fixture_seed"]=fs
            UTILITY.append(x)

P0U=pd.concat(UTILITY,ignore_index=True)
P0U=P0U[
    P0U["capability"].astype(str).eq(EXPECTED_KT10_CAPABILITY)
    & P0U["suite"].astype(str).eq("contemporaneous")
].copy()

for c in ["synthetic_loss","reference_loss","naive_loss","loss_ratio","log_loss_ratio",
          "synthetic_skill_gain","reference_skill_gain","synthetic_r2","reference_r2"]:
    P0U[c]=pd.to_numeric(P0U[c],errors="coerce")

print("P0 utility rows:",len(P0U))
display(P0U.groupby(["fixture_seed","p0_phase","p0_anchor"]).agg(
    n=("log_loss_ratio","size"),
    median_log_loss_ratio=("log_loss_ratio","median"),
    median_reference_skill_gain=("reference_skill_gain","median"),
    median_reference_r2=("reference_r2","median"),
    median_reference_loss=("reference_loss","median"),
    median_naive_loss=("naive_loss","median"),
).reset_index())

P0U.to_csv(FORENSIC_ROOT/"tables"/"KT10_all_P0_utility_rows.csv",index=False)
