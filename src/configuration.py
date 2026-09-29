from pathlib import Path
import json, os
ROOT=Path(__file__).resolve().parents[1]
def load_config(path):
    path=Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Copy config/example.json to {path} and set your paths first.')
    c=json.loads(path.read_text())
    required={'profile','public_python','residential_python','residential_parquet','toniot_data_root','run_root','workers','budget_hours'}
    if set(c)!=required:raise ValueError('Configuration keys must be exactly: '+', '.join(sorted(required)))
    if c['profile'] not in {'records','full'}:raise ValueError('Use records or full.')
    if not isinstance(c['workers'],int) or c['workers']<1 or c['budget_hours']<=0:raise ValueError('Invalid operational settings.')
    for k in ['public_python','residential_python','residential_parquet','toniot_data_root','run_root']:
        q=Path(os.path.expandvars(c[k])).expanduser()
        c[k]=os.path.abspath(q if q.is_absolute() else ROOT/q)
    return c
