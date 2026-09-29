
# ============================================================
# 1. Minimal infrastructure + exact canonical definitions
# ============================================================
RUN_FINGERPRINT={}
TIER_ALIASES=dict(CFG.get("tier_aliases",{}))
CACHE_STATS={"hit":0,"miss":0,"seconds_saved":0.0}
DIRS={
    "root":OUT, "manifests":OUT/"manifests", "tables":OUT/"tables",
    "figures":OUT/"figures", "cache":OUT/"cache", "logs":OUT/"logs",
    "job_state":OUT/"job_state"
}
for d in DIRS.values():
    d.mkdir(parents=True,exist_ok=True)

def stable_hash(value):
    return hashlib.sha256(
        json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    ).hexdigest()

def write_json(path,payload):
    Path(path).write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")

def log_event(event: str, **payload):
    p=OUT/"logs"/"posctrl_v42_events.jsonl"
    with p.open("a",encoding="utf-8") as f:
        f.write(json.dumps({
            "event":event,
            "timestamp_utc":pd.Timestamp.utcnow().isoformat(),
            **payload
        },default=str)+"\n")

def callable_fingerprint(fn):
    try: return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
    except Exception: return hashlib.sha256(repr(fn).encode()).hexdigest()

def cached(namespace):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args,_key=None,**kwargs):
            if _key is None:
                return fn(*args,**kwargs)
            key=stable_hash({"namespace":namespace,"function":callable_fingerprint(fn),"key":_key})
            p=DIRS["cache"]/namespace/f"{key}.pkl"
            if p.exists():
                try: return pickle.loads(p.read_bytes())["value"]
                except Exception: p.unlink(missing_ok=True)
            val=fn(*args,**kwargs)
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(pickle.dumps({"value":val}))
            return val
        return wrapper
    return deco

CANON_NB=json.loads(CANONICAL_NOTEBOOK.read_text(encoding="utf-8"))
CANON_CODE=[c for c in CANON_NB["cells"] if c.get("cell_type")=="code"]

def extract_defs(source,wanted):
    tree=ast.parse(source)
    lines=source.splitlines()
    out=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.name in wanted:
            start=min([node.lineno]+[d.lineno for d in getattr(node,"decorator_list",[])])-1
            out.append((node.name,"\n".join(lines[start:node.end_lineno])))
    return out

# Only definitions needed for anchor generation, support projection, and direct C2ST.
wanted_by_logical_cell={
    2:{
        "deterministic_subsample_indices","robust_iqr",
        "_valid_group_split","_c2st_auc_once","_permute_labels_within_groups","c2st_profile",
    },
    3:{
        "read_dataset","column_prefix","infer_tier","family_key","signal_class",
        "contiguous_indices","split_signature","rolling_folds",
    },
    5:{
        "sample_rows","block_length_for_output","real_resample_generator","real_block_generator",
        "infer_column_support","project_to_empirical_train_support","project_frame_to_train_support",
    },
}

audit=[]
for logical,wanted in wanted_by_logical_cell.items():
    src="".join(CANON_CODE[logical+1].get("source",[]))  # +1 skips canonical bootstrap/import cell
    defs=extract_defs(src,wanted)
    found={n for n,_ in defs}
    missing=wanted-found
    if missing:
        raise RuntimeError(f"Missing canonical defs in CELL {logical}: {sorted(missing)}")
    for name,piece in defs:
        exec(piece,globals(),globals())
        audit.append({
            "canonical_cell":logical,
            "name":name,
            "sha256":hashlib.sha256(piece.encode()).hexdigest(),
            "lines":len(piece.splitlines())
        })

DEFINITION_AUDIT=pd.DataFrame(audit).sort_values(["canonical_cell","name"])
display(DEFINITION_AUDIT)
DEFINITION_AUDIT.to_csv(OUT/"tables"/"canonical_definition_audit_v42.csv",index=False)
print("Loaded exact canonical definitions:",len(DEFINITION_AUDIT))
