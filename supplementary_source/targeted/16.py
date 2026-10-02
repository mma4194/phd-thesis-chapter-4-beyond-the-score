
def make_near_reference_positive_control(
    train: pd.DataFrame,
    columns: Sequence[str],
    sigma_iqr: float,
    seed: int,
) -> pd.DataFrame:
    """New post-hoc positive control; chronology and masks are preserved exactly.

    Continuous/non-binary value features receive zero-mean Gaussian jitter scaled
    by frozen TRAIN IQR. Values are projected back to empirical TRAIN support using
    the exact canonical support-projection function.
    """
    rng=np.random.default_rng(seed)
    out=train[list(columns)].copy().reset_index(drop=True)

    # Preserve all observability masks and discrete/binary-like features.
    for c in columns:
        if c.endswith("__nonfinite_mask"):
            continue
        x=out[c].to_numpy(dtype=float,copy=True)
        finite=x[np.isfinite(x)]
        if len(finite)<20:
            continue
        uniq=np.unique(finite[:min(len(finite),100000)])
        binary=bool(len(uniq)<=2 and set(uniq.tolist()).issubset({0.0,1.0}))
        integer_like=bool(np.mean(np.isclose(finite,np.round(finite),atol=1e-6))>=0.995)
        iqr=robust_iqr(finite)
        # Jitter only genuinely continuous, variable features.
        if binary or integer_like or iqr<=1e-9:
            continue
        x += rng.normal(0.0, sigma_iqr*iqr, size=len(x))
        out[c]=x

    # Exact canonical empirical-support projection.
    out=project_frame_to_train_support(out, train[list(columns)], columns)
    return out

if RUN_NEW_EXPERIMENTS:
    train=CANON_DF.iloc[PRIMARY_SPLIT["train"]].reset_index(drop=True)
    gen_cols=list(FEATURE_SCOPES["generator_v2"])
    n=int(CFG["generation_rows"])
    # Use the first n chronological TRAIN rows as the reference substrate; no row reordering.
    substrate=train.iloc[:min(n,len(train))][gen_cols].reset_index(drop=True)

    POS_SOURCES={}
    for label,sigma in POSCTRL_SIGMA_IQR.items():
        for seed in SEEDS:
            POS_SOURCES[(label,seed)] = make_near_reference_positive_control(
                substrate,gen_cols,sigma_iqr=sigma,seed=int(seed)
            )
    print("Constructed",len(POS_SOURCES),"positive-control frames")
else:
    print("Skipped POSCTRL source generation")
