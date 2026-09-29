"""Check this interpreter against the scientific versions; no installation."""
from pathlib import Path
import argparse,json,sys,importlib.metadata as m
p=argparse.ArgumentParser();p.add_argument('--group',choices=['public','residential'],required=True);p.add_argument('--output');a=p.parse_args()
expected=json.loads((Path(__file__).resolve().parents[1]/'protocols/expected_environments.json').read_text())[a.group]
rows=[]
for name,want in expected.items():
    try:have=m.version(name)
    except m.PackageNotFoundError:have='NOT INSTALLED'
    rows.append({'package':name,'required':want,'installed':have,'match':have==want})
d={'interpreter':sys.executable,'python':sys.version,'group':a.group,'passed':all(x['match'] for x in rows),'packages':rows}
print(json.dumps(d,indent=2))
if a.output:Path(a.output).write_text(json.dumps(d,indent=2)+'\n')
raise SystemExit(0 if d['passed'] else 1)
