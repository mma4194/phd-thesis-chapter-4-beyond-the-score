
# ============================================================
# 2. Hydrate exact residential data/schema/splits
# ============================================================
if not DATASET_PATH.exists():
    raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")
if not V41_UTILITY.exists():
    raise FileNotFoundError(
        f"POSCTRL v4.1 utility output not found: {V41_UTILITY}\n"
        "Copy the completed POSCTRL_V41_utility.csv into TIOT_POSCTRL_V41_OUTPUTS."
    )

globals()["MODE"]="real"
globals()["ROW_LIMIT"]=0
globals()["SEED0"]=SEED0
globals()["DATASET_PATH"]=DATASET_PATH
globals()["RUN_FINGERPRINT"]={}
globals()["TIME_GRID_ELIGIBLE"]=True
CFG["hash_dataset"]=False

# Execute canonical CELL 3 verbatim.
src="".join(CANON_CODE[4].get("source",[]))
exec(src,globals(),globals())

current_scopes={k:sorted(v) for k,v in FEATURE_SCOPES.items()}
frozen_scopes={k:sorted(v) for k,v in SCHEMA_MANIFEST["feature_scopes"].items()}
mismatches={
    k:{"current_n":len(current_scopes.get(k,[])),"frozen_n":len(v)}
    for k,v in frozen_scopes.items()
    if current_scopes.get(k)!=v
}
if mismatches:
    raise RuntimeError(f"Schema drift: {mismatches}")

print("Hydrated:",CANON_DF.shape)
print("Primary split:",{k:len(v) for k,v in PRIMARY_SPLIT.items() if isinstance(v,np.ndarray)})
print("Active tiers:",sorted(ACTIVE_TIERS))
