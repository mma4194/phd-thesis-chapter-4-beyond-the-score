
# ============================================================
# 2. Atomic freezing, logging, cache and checkpoint infrastructure
# ============================================================
def normalise_json(v):
    if isinstance(v,dict): return {str(k):normalise_json(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,set)): return [normalise_json(x) for x in v]
    if isinstance(v,Path): return str(v)
    if isinstance(v,np.integer): return int(v)
    if isinstance(v,np.floating): return None if not np.isfinite(v) else float(v)
    if isinstance(v,np.bool_): return bool(v)
    if isinstance(v,float) and not np.isfinite(v): return None
    return v

def stable_hash(v): return hashlib.sha256(json.dumps(normalise_json(v),sort_keys=True,separators=(",",":")).encode()).hexdigest()
def atomic_text(path,text):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+f".tmp-{os.getpid()}"); tmp.write_text(text,encoding="utf-8"); tmp.replace(path)
def write_json(path,payload): atomic_text(path,json.dumps(normalise_json(payload),indent=2,sort_keys=True))
def read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def freeze_bytes(path,payload):
    path=Path(path); digest=hashlib.sha256(payload).hexdigest()
    if path.exists() and path.read_bytes()!=payload:
        raise RuntimeError(f"Frozen file differs: {path}. Use a new experiment version.")
    if not path.exists(): path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(payload)
    atomic_text(path.with_suffix(path.suffix+".sha256"),digest+"\n")
    return digest
def freeze_json(path,payload): return freeze_bytes(path,(json.dumps(normalise_json(payload),indent=2,sort_keys=True)+"\n").encode())
def freeze_csv(path,frame): return freeze_bytes(path,frame.to_csv(index=False,lineterminator="\n").encode())
def log_event(event,**payload):
    rec={"timestamp_utc":pd.Timestamp.utcnow().isoformat(),"event":event,"profile":RUN_PROFILE,**normalise_json(payload)}
    with (PROFILE_ROOT/"logs"/"events.jsonl").open("a",encoding="utf-8") as f: f.write(json.dumps(rec,sort_keys=True)+"\n")

def checkpoint(*parts,suffix=".json"):
    p=PROFILE_ROOT/"checkpoints"
    for x in parts[:-1]: p=p/str(x)
    p.mkdir(parents=True,exist_ok=True); return p/(str(parts[-1])+suffix)
def load_cp(path,protocol_hash):
    if not Path(path).exists(): return None
    x=read_json(path)
    if x.get("protocol_hash")!=protocol_hash: raise RuntimeError(f"Stale checkpoint: {path}")
    return x
def save_cp(path,protocol_hash,payload): write_json(path,{"protocol_hash":protocol_hash,**normalise_json(payload)})

CACHE_STATS={"hit":0,"miss":0}
def callable_fingerprint(fn):
    try: return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
    except Exception: return hashlib.sha256(repr(fn).encode()).hexdigest()
def cached(namespace):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args,_key=None,**kwargs):
            if _key is None: return fn(*args,**kwargs)
            key=stable_hash({"namespace":namespace,"function":callable_fingerprint(fn),"execution":EXECUTION_BINDING,"key":_key,"profile":RUN_PROFILE})
            p=PROFILE_ROOT/"cache"/namespace/(key+".pkl")
            if p.exists():
                try: CACHE_STATS["hit"]+=1; return pickle.loads(p.read_bytes())["value"]
                except Exception: p.unlink(missing_ok=True)
            value=fn(*args,**kwargs); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(pickle.dumps({"value":value})); CACHE_STATS["miss"]+=1; return value
        return wrapper
    return deco
