
# Minimal infrastructure expected by exact canonical functions.
RUN_FINGERPRINT={}
TIER_ALIASES=dict(CFG.get("tier_aliases",{}))
CACHE_STATS={"hit":0,"miss":0,"seconds_saved":0.0}
DIRS={
    "root":OUT, "manifests":OUT/"manifests", "tables":OUT/"tables",
    "figures":OUT/"figures", "cache":OUT/"cache", "logs":OUT/"logs",
    "job_state":OUT/"job_state"
}
for d in DIRS.values(): d.mkdir(parents=True,exist_ok=True)

def stable_hash(value):
    payload=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(payload).hexdigest()

def write_json(path,payload):
    Path(path).write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")

def log_event(event: str, **payload):
    """Lightweight event logger expected by canonical CELL 3."""
    p = DIRS["logs"] / "posctrl_v41_events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "timestamp_utc": pd.Timestamp.utcnow().isoformat(),
        **payload,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")

def callable_fingerprint(fn):
    try: return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
    except Exception: return hashlib.sha256(repr(fn).encode()).hexdigest()

def cached(namespace):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args,_key=None,**kwargs):
            if _key is None: return fn(*args,**kwargs)
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

CANON_NB=json.loads(CANONICAL_NOTEBOOK.read_text())
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

wanted_by_logical_cell={
    2:{
        "deterministic_subsample_indices","robust_iqr","safe_corr","marginal_profile",
        "autocorrelation","temporal_profile","coupling_profile_from_pairs",
        "_valid_group_split","_c2st_auc_once","_permute_labels_within_groups",
        "c2st_profile","build_controlled_iot_fixture","perturb_fixture","rank_correlation",
    },
    3:{
        "read_dataset","column_prefix","infer_tier","family_key","signal_class",
        "contiguous_indices","split_signature","rolling_folds",
    },
    4:{
        "TaskCard","TaskModelCard","task_family_key","capability_key",
        "_forward_window_indicator","_forward_window_any","_forward_window_onset",
        "build_task_frame","train_threshold","model_for","fit_predict",
        "calibration_error","task_loss_and_diagnostics",
    },
    5:{
        "GeneratorSpec","sample_rows","block_length_for_output",
        "real_resample_generator","real_block_generator",
        "infer_column_support","project_to_empirical_train_support",
        "project_frame_to_train_support",
    },
    6:{
        "_reference_task_result","reference_task_result","evaluate_utility",
        "summarize_utility_rows",
    },
    8:{"apply_p0_licences"},
}

audit=[]
for logical,wanted in wanted_by_logical_cell.items():
    src="".join(CANON_CODE[logical+1].get("source",[]))  # +1 skips bootstrap imports
    defs=extract_defs(src,wanted)
    found={n for n,_ in defs}
    miss=wanted-found
    if miss: raise RuntimeError(f"Missing canonical defs in CELL {logical}: {sorted(miss)}")
    for name,piece in defs:
        exec(piece,globals(),globals())
        audit.append({"canonical_cell":logical,"name":name,"sha256":hashlib.sha256(piece.encode()).hexdigest()})

AUDIT=pd.DataFrame(audit)
display(AUDIT)
AUDIT.to_csv(OUT/"canonical_definition_audit_v41.csv",index=False)
print("Loaded exact canonical definitions:",len(AUDIT))
