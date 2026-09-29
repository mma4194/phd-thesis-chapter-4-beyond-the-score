
# ============================================================
# Exact canonical function loader
# ============================================================
CANON_NB = json.loads(CANONICAL_NOTEBOOK.read_text(encoding="utf-8"))
CANON_CODE = [c for c in CANON_NB["cells"] if c.get("cell_type") == "code"]

def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

def log_event(event: str, **payload):
    p = DIRS["logs"] / "targeted_v4_events.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event":event, **payload}, default=str) + "\n")

# Lightweight cache infrastructure; scientific functions themselves are loaded verbatim.
CACHE_STATS = {"hit":0, "miss":0, "seconds_saved":0.0}

def callable_fingerprint(fn):
    try:
        return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
    except Exception:
        return hashlib.sha256(repr(fn).encode()).hexdigest()

def cached(namespace: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, _key=None, **kwargs):
            if _key is None:
                return fn(*args, **kwargs)
            key = stable_hash({"namespace":namespace, "function":callable_fingerprint(fn), "key":_key})
            path = DIRS["cache"] / namespace / f"{key}.pkl"
            if path.exists():
                try:
                    CACHE_STATS["hit"] += 1
                    return pickle.loads(path.read_bytes())["value"]
                except Exception:
                    path.unlink(missing_ok=True)
            t0 = time.time()
            value = fn(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pickle.dumps({"value":value, "seconds":time.time()-t0}))
            CACHE_STATS["miss"] += 1
            return value
        return wrapper
    return decorator

def _extract_named_definitions(cell_source: str, wanted: set[str]):
    tree = ast.parse(cell_source)
    lines = cell_source.splitlines()
    srcs = []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in wanted:
            # Include decorators (e.g., @dataclass, @cached), which ast.get_source_segment(node)
            # does not reliably include because node.lineno points at def/class.
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]) - 1
            end = node.end_lineno
            seg = "\n".join(lines[start:end])
            srcs.append(seg)
            names.append(node.name)
    return srcs, names

wanted_by_cell = {
    # canonical CELL 2: metrics / fixtures / C2ST
    2: {
        "deterministic_subsample_indices","robust_iqr","safe_corr","marginal_profile","autocorrelation",
        "temporal_profile","coupling_profile_from_pairs","_valid_group_split","_c2st_auc_once",
        "_permute_labels_within_groups","c2st_profile","build_controlled_iot_fixture","perturb_fixture",
        "rank_correlation",
    },
    # canonical CELL 3: data/schema/splits
    3: {"read_dataset","column_prefix","infer_tier","family_key","signal_class","contiguous_indices","split_signature","rolling_folds"},
    # canonical CELL 4: task schema and utility-frame construction
    4: {"TaskCard","TaskModelCard","task_family_key","capability_key","build_task_frame","model_for","fit_predict","task_loss_and_diagnostics"},
    # canonical CELL 5: source specification/support projection
    5: {
        "GeneratorSpec",
        "infer_column_support",
        "project_to_empirical_train_support",
        "project_frame_to_train_support",
    },
    # canonical CELL 6: exact utility evaluator and TRTR reference
    6: {"_reference_task_result","reference_task_result","evaluate_utility","summarize_utility_rows"},
    # canonical CELL 7: P0 calibration primitives
    7: {"p0_capability_summary","_anchor_pivot","crossed_pair_seed_ci","_hierarchical_calibration_quantile"},
    # canonical CELL 8: P0 permission application
    8: {"apply_p0_licences"},
}

definition_audit = []
loaded = set()
for logical_cell, wanted in wanted_by_cell.items():
    src = "".join(CANON_CODE[logical_cell + 1].get("source", []))  # +1 skips canonical import/bootstrap cell
    pieces, names = _extract_named_definitions(src, wanted)
    missing = wanted - set(names)
    if missing:
        raise RuntimeError(f"Canonical CELL {logical_cell}: missing definitions {sorted(missing)}")
    for piece, name in zip(pieces, names):
        exec(piece, globals(), globals())
        definition_audit.append({
            "canonical_cell":logical_cell,
            "name":name,
            "sha256":hashlib.sha256(piece.encode("utf-8")).hexdigest(),
            "lines":len(piece.splitlines()),
        })
        loaded.add(name)

DEFINITION_AUDIT = pd.DataFrame(definition_audit).sort_values(["canonical_cell","name"])
display(DEFINITION_AUDIT)
DEFINITION_AUDIT.to_csv(OUT/"canonical_definition_audit.csv", index=False)
print("Loaded exact canonical definitions:", len(loaded))
