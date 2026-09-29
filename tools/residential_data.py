"""Download the existing Chapter 3 release asset, or verify a local shared copy."""
from pathlib import Path
import argparse,json,hashlib,urllib.request
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--download',action='store_true');a=p.parse_args()
d=json.loads((ROOT/'datasets/residential/dataset.json').read_text());dest=a.output.expanduser().resolve()
if a.download and not dest.exists():
    dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_name(dest.name+'.download')
    with urllib.request.urlopen(d['download_url']) as response,temp.open('wb') as f:
        for block in iter(lambda:response.read(8*1024*1024),b''):f.write(block)
    candidate=temp
else:candidate=dest
if not candidate.is_file():raise SystemExit('File is missing. Add --download or select the existing shared Parquet.')
h=hashlib.sha256()
with candidate.open('rb') as f:
    for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
if candidate.stat().st_size!=d['bytes'] or h.hexdigest()!=d['sha256']:raise SystemExit('Input identity mismatch. Existing data were not overwritten.')
if candidate!=dest:candidate.replace(dest)
print(json.dumps({'passed':True,'path':str(dest),'sha256':h.hexdigest(),'bytes':dest.stat().st_size},indent=2))
