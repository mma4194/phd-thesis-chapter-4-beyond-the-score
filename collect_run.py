"""Collect actual execution reports and source snapshots for review, excluding raw data and prediction arrays."""
from pathlib import Path
import argparse,hashlib,json,subprocess,zipfile
from src.configuration import load_config,ROOT
p=argparse.ArgumentParser();p.add_argument('--config',default='config/local.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--source-root',type=Path,default=ROOT);a=p.parse_args()
source_root=a.source_root.expanduser().resolve()
if not source_root.is_dir():raise SystemExit('Source directory does not exist.')
c=load_config(a.config);run=Path(c['run_root']);dest=a.output.expanduser().resolve();dest.parent.mkdir(parents=True,exist_ok=True)
if not run.is_dir():raise SystemExit('Run directory does not exist.')
rows=[]
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('configuration.json',json.dumps(c,indent=2))
    for group in ['public','residential']:
        python=c[group+'_python']
        for label,args in [('versions',['-m','pip','freeze']),('python',['-c','import sys,platform;print(sys.version);print(platform.platform())'])]:
            try:text=subprocess.check_output([python,*args],text=True,stderr=subprocess.STDOUT,timeout=60)
            except Exception as e:text=repr(e)
            z.writestr('environment/'+group+'_'+label+'.txt',text)
    for base,prefix in [(run,'run'),(source_root,'source')]:
        for f in sorted(base.rglob('*')):
            if not f.is_file() or f.resolve()==dest:continue
            rel=f.relative_to(base)
            if any(x in rel.parts for x in ['.git','__pycache__','cache','arrays','predictions','prepared_telemetry','jobs','completed_sources','.venv-public','.venv-residential']):continue
            if base==source_root and rel.parts[0] in {'runs','data','validation','reference','provenance'}:continue
            if f.suffix not in {'.json','.csv','.log','.txt','.md','.py','.ipynb','.in','.yml'} or f.stat().st_size>25*2**20:continue
            if base==run and ('preparation' in rel.parts or 'network' in rel.parts) and f.suffix=='.csv':continue
            arc=prefix+'/'+rel.as_posix();data=f.read_bytes();z.writestr(arc,data)
            rows.append({'path':arc,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    z.writestr('COLLECTION_MANIFEST.json',json.dumps({'scope':'Actual available files only; absence does not mean PASS','files':rows},indent=2))
print('Created',dest,'with',len(rows),'files. Review local paths/logs before public sharing.')
