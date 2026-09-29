
def block_permute_frame(frame: pd.DataFrame, block_rows: int, seed: int) -> pd.DataFrame:
    rng=np.random.default_rng(seed)
    n=len(frame)
    blocks=[np.arange(i,min(i+block_rows,n)) for i in range(0,n,block_rows)]
    order=rng.permutation(len(blocks))
    idx=np.concatenate([blocks[i] for i in order])
    return frame.iloc[idx].reset_index(drop=True)

def within_block_shuffle_frame(frame: pd.DataFrame, block_rows: int, seed: int) -> pd.DataFrame:
    rng=np.random.default_rng(seed)
    idx=np.arange(len(frame))
    for start in range(0,len(frame),block_rows):
        stop=min(start+block_rows,len(frame))
        idx[start:stop]=rng.permutation(idx[start:stop])
    return frame.iloc[idx].reset_index(drop=True)

if RUN_NEW_EXPERIMENTS:
    # Use a fixed chronological TEST segment. No threshold or block-size tuning on outcomes.
    test=CANON_DF.iloc[PRIMARY_SPLIT["test"]].reset_index(drop=True)
    cols=list(FEATURE_SCOPES["protocol_value_v3"])
    n=min(len(test),70000)
    base=test.iloc[:n][cols].reset_index(drop=True)

    temp_rows=[]
    for seed in SEEDS:
        conditions={
            "identity":base.copy(),
            "within_block_shuffle":within_block_shuffle_frame(base,TEMP_BLOCK_ROWS,int(seed)),
            "block_permutation":block_permute_frame(base,TEMP_BLOCK_ROWS,int(seed)),
            "global_row_shuffle":base.iloc[np.random.default_rng(int(seed)).permutation(len(base))].reset_index(drop=True),
        }
        for name,syn in conditions.items():
            tp=temporal_profile(base,syn,cols,lags=list(CFG["acf_lags"]),max_len=min(n,65536))
            temp_rows.append({"condition":name,"seed":seed,"block_rows":TEMP_BLOCK_ROWS,**tp})

    TEMPCTRL=pd.DataFrame(temp_rows)
    TEMPCTRL.to_csv(OUT/"TEMPCTRL1_temporal_instruments.csv",index=False)
    display(TEMPCTRL.groupby("condition")[
        ["acf_abs_error_mean","spectral_l1_mean","transition_rate_mae"]
    ].agg(["mean","std"]))
else:
    print("Skipped TEMPCTRL evaluation")
