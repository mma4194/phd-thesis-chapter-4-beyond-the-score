"""Standard-library integrity check. No datasets or scientific packages required."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parent
def verify():
    m=json.loads((ROOT/'MANIFEST.json').read_text());bad=[]
    for row in m['files']:
        f=ROOT/row['path']
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=row['sha256']:bad.append(row['path'])
    supplement=list((ROOT/'supplementary').iterdir())
    if len(supplement)!=1 or supplement[0].name!='Beyond_the_Score_Supplement.pdf':bad.append('supplementary must contain only its PDF')
    print(json.dumps({'files_checked':len(m['files']),'changed_or_missing':bad,'passed':not bad},indent=2))
    return not bad
if __name__=='__main__':raise SystemExit(0 if verify() else 1)
