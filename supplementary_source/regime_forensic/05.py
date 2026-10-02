
# ============================================================
# 3. Reconstruct only the four KT10 fixtures, exactly
# ============================================================
# Frozen full-mode constants from KT-v1.
KT_TIME_STEP_SECONDS=6
KT_P0_BLOCK_ROWS=3600
KT_P0_CANDIDATE_BLOCKS=20
KT_P0_PAIRS=10
KT_TRAIN_ROWS,KT_VAL_ROWS,KT_TEST_ROWS=72000,24000,24000

# Obtain embargo length from canonical effective configuration.
if FINAL_ROOT:
    cfg_path=FINAL_ROOT/"02_ARTIFACT"/"artifact"/"manifests"/"effective_config.json"
    BASE_CFG=json.loads(cfg_path.read_text(encoding="utf-8"))
else:
    fzip=find_file(["TIOT_FINALISATION(1).zip","TIOT_FINALISATION.zip"])
    with zipfile.ZipFile(fzip) as z:
        BASE_CFG=json.loads(z.read("02_ARTIFACT/artifact/manifests/effective_config.json"))
KT_EMBARGO_ROWS=int(BASE_CFG["embargo_steps"])
KT_TOTAL_ROWS=KT_TRAIN_ROWS+KT_EMBARGO_ROWS+KT_VAL_ROWS+KT_EMBARGO_ROWS+KT_TEST_ROWS

# Execute only the exact functions required for reconstruction.
exec(SRC_build_controlled_iot_fixture,globals(),globals())
exec(SRC_primary_split,globals(),globals())
PRIMARY_SPLIT_TEMPLATE=primary_split()
exec(SRC_ar_noise,globals(),globals())
exec(SRC_make_fixture,globals(),globals())

DGP_ROWS=[]
BLOCK_ROWS=[]
FIXTURES={}

for fs in FIXTURE_SEEDS:
    frame,truth,times=make_fixture(fs,"regime_unstable")
    FIXTURES[fs]=(frame,truth,times)
    split=PRIMARY_SPLIT_TEMPLATE
    tr=split["train"]
    p=frame["router__packets"].to_numpy(float)
    o=frame["ota24__frames"].to_numpy(float)
    y=frame["iot__power"].to_numpy(float)
    reg=frame["iot__regime"].to_numpy(float)
    mp=float(np.quantile(p[tr],.995))
    mo=float(np.quantile(o[tr],.995))

    a=20+3.2*p+1.5*o
    b=20+3.2*np.maximum(0,mp-p)+1.5*np.maximum(0,mo-o)
    pred=np.where(reg<.5,a,b)
    residual=y-pred

    for r in [0,1]:
        idx=np.where(reg[tr]==r)[0]
        absidx=tr[idx]
        X=np.c_[p[absidx],o[absidx]]
        lr=LinearRegression().fit(X,y[absidx])
        corr_p=float(np.corrcoef(p[absidx],y[absidx])[0,1])
        corr_o=float(np.corrcoef(o[absidx],y[absidx])[0,1])
        DGP_ROWS.append({
            "fixture_seed":fs,"regime":r,"n_train_rows":len(absidx),
            "router_packets_slope":float(lr.coef_[0]),
            "ota_frames_slope":float(lr.coef_[1]),
            "intercept":float(lr.intercept_),
            "corr_router_packets_power":corr_p,
            "corr_ota_frames_power":corr_o,
            "r2_within_regime_ols":float(lr.score(X,y[absidx])),
            "mp_train_q995":mp,"mo_train_q995":mo,
            "formula_residual_mean":float(np.mean(residual[absidx])),
            "formula_residual_sd":float(np.std(residual[absidx])),
        })

    # Six-hour candidate blocks: blocks 0-9 are pre-change, 10-19 post-change.
    for bi in range(KT_P0_CANDIDATE_BLOCKS):
        idx=np.arange(bi*KT_P0_BLOCK_ROWS,(bi+1)*KT_P0_BLOCK_ROWS)
        BLOCK_ROWS.append({
            "fixture_seed":fs,"block":bi,
            "start_row":int(idx[0]),"end_row_exclusive":int(idx[-1]+1),
            "regime_fraction":float(reg[idx].mean()),
            "mean_power":float(y[idx].mean()),
            "corr_router_packets_power":float(np.corrcoef(p[idx],y[idx])[0,1]),
            "corr_ota_frames_power":float(np.corrcoef(o[idx],y[idx])[0,1]),
        })

DGP_AUDIT=pd.DataFrame(DGP_ROWS)
BLOCK_AUDIT=pd.DataFrame(BLOCK_ROWS)
display(DGP_AUDIT)
display(BLOCK_AUDIT.groupby(["fixture_seed","regime_fraction"]).agg(
    n_blocks=("block","size"),
    corr_router_mean=("corr_router_packets_power","mean"),
    corr_ota_mean=("corr_ota_frames_power","mean")
).reset_index())

DGP_AUDIT.to_csv(FORENSIC_ROOT/"tables"/"KT10_DGP_regime_audit.csv",index=False)
BLOCK_AUDIT.to_csv(FORENSIC_ROOT/"tables"/"KT10_block_regime_audit.csv",index=False)
