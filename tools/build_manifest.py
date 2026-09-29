"""Rebuild the repository inventory after intentional source/document changes."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for f in sorted(ROOT.rglob('*')):
    if not f.is_file():continue
    rel=f.relative_to(ROOT)
    if any(p in {'.git','__pycache__','.ipynb_checkpoints','runs','data','.venv-public','.venv-residential'} for p in rel.parts):continue
    if rel.as_posix() in {'MANIFEST.json','config/local.json'} or f.suffix=='.pyc':continue
    rows.append({'path':rel.as_posix(),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(ROOT/'MANIFEST.json').write_text(json.dumps({'schema_version':1,'files':rows},indent=2)+'\n')
print('Indexed',len(rows),'files')
