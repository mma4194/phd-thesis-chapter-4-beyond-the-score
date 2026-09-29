from pathlib import Path
import json,subprocess,sys
from .common import ROOT,sha,environment,write_json,new_output

def run(out=None):
 manifest=json.loads((ROOT/'MANIFEST.json').read_text());errors=[]
 for r in manifest['files']:
  if r['path'].endswith('.ipynb'): continue  # editable configuration/output documents
  p=ROOT/r['path']
  if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:errors.append(r['path'])
 out=Path(out) if out else new_output('preflight');out.mkdir(parents=True,exist_ok=True);write_json(out/'integrity.json',{'files':len(manifest['files']),'changed_or_missing':errors,'environment':environment()})
 if errors:raise ValueError('Artifact files changed or missing: '+str(errors[:12]))
 result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],cwd=ROOT,text=True,capture_output=True)
 (out/'tests.txt').write_text(result.stdout+result.stderr,encoding='utf-8');print(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError('Software contract checks failed. See '+str(out/'tests.txt'))
 return out
