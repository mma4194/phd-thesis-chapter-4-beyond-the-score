
def hydrate_exact_canonical_data_context():
    """Execute canonical CELL 3 verbatim after binding frozen v7.14.5 globals."""
    if "CANON_DF" in globals():
        print("CANON_DF already hydrated:",CANON_DF.shape)
        return

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Residential source dataset not found at {DATASET_PATH}. "
            "Set TIOT_DATASET_PARQUET to the exact canonical parquet path/copy."
        )

    # Exact cell requires these helpers/globals.
    globals()["MODE"]="real"
    globals()["ROW_LIMIT"]=0
    globals()["SEED0"]=int(SEEDS[0])
    globals()["DATASET_PATH"]=DATASET_PATH
    globals()["RUN_FINGERPRINT"]={}
    globals()["TIME_GRID_ELIGIBLE"]=True

    # Dataset hashing is unnecessary for this post-hoc diagnostic and can be expensive;
    # scientific split/schema parameters remain frozen.
    CFG["hash_dataset"]=False

    src = "".join(CANON_CODE[4].get("source", []))  # canonical CELL 3; +1 skips bootstrap
    exec(src, globals(), globals())

    # Verify exact frozen schema rather than silently accepting drift.
    current_scopes={k:sorted(v) for k,v in FEATURE_SCOPES.items()}
    frozen_scopes={k:sorted(v) for k,v in SCHEMA_MANIFEST["feature_scopes"].items()}
    mismatches={}
    for k in frozen_scopes:
        if current_scopes.get(k)!=frozen_scopes[k]:
            mismatches[k]={
                "current_n":len(current_scopes.get(k,[])),
                "frozen_n":len(frozen_scopes[k]),
            }
    if mismatches:
        raise RuntimeError(f"Hydrated schema differs from frozen manifest: {mismatches}")

    print("Hydrated exact canonical context:",CANON_DF.shape)
    print("Primary split sizes:", {k:len(v) for k,v in PRIMARY_SPLIT.items() if isinstance(v,np.ndarray)})
    print("Active tiers:",sorted(ACTIVE_TIERS))

if RUN_NEW_EXPERIMENTS:
    hydrate_exact_canonical_data_context()
else:
    print("Skipped canonical data hydration because RUN_NEW_EXPERIMENTS=False")
