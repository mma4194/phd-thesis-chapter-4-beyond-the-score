
# Hydrate the exact canonical real-data context.
if not DATASET_PATH.exists():
    raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

globals()["MODE"]="real"
globals()["ROW_LIMIT"]=0
globals()["SEED0"]=SEED0
globals()["DATASET_PATH"]=DATASET_PATH
globals()["RUN_FINGERPRINT"]={}
globals()["TIME_GRID_ELIGIBLE"]=True
CFG["hash_dataset"]=False

src="".join(CANON_CODE[4].get("source",[]))  # canonical CELL 3
exec(src,globals(),globals())

current_scopes={k:sorted(v) for k,v in FEATURE_SCOPES.items()}
frozen_scopes={k:sorted(v) for k,v in SCHEMA_MANIFEST["feature_scopes"].items()}
mismatches={k:(len(current_scopes.get(k,[])),len(v)) for k,v in frozen_scopes.items() if current_scopes.get(k)!=v}
if mismatches: raise RuntimeError(f"Schema drift: {mismatches}")

print("Hydrated:",CANON_DF.shape)
print("Primary split:",{k:len(v) for k,v in PRIMARY_SPLIT.items() if isinstance(v,np.ndarray)})
