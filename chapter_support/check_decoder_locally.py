"""Offline independent decoder check on the original 15 full captures; no model fitting."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,platform,shutil,sys,traceback,zipfile
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def run(a):
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 result={'status':'STARTED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'scope':'First 10000 packets per each of 15 full original captures; no full-payload validation or model fits','input_files':[]}
 try:
  if a.tshark:
   if not a.tshark.is_file():raise FileNotFoundError('TShark executable missing: '+str(a.tshark))
   os.environ['PATH']=str(a.tshark.resolve().parent)+os.pathsep+os.environ.get('PATH','')
  candidate=shutil.which('tshark')
  if not candidate and Path(r'C:\Program Files\Wireshark\tshark.exe').is_file():candidate=r'C:\Program Files\Wireshark\tshark.exe'
  if not candidate:
   result.update(status='BLOCKED_DEPENDENCY',reason='TShark is unavailable on this computer. Install locally; do not rerun model fitting.');return 2
  expected=json.loads((ROOT/'evidence/decoder_code_hashes.json').read_text())
  result['decoder_code_hashes']={name:sha(ROOT/'decoder_engine'/name) for name in expected}
  if result['decoder_code_hashes']!=expected:raise ValueError('Decoder code bytes differ from the bundled Falcon implementation')
  protocol=json.loads((ROOT/'evidence/preparation_protocol.json').read_text())
  captures={};files=[r for r in protocol['input_files'] if r['role']!='telemetry']
  if len(files)!=15:raise ValueError('Expected exactly 15 reference captures')
  if not a.captures.is_dir():raise FileNotFoundError('Capture directory missing: '+str(a.captures))
  available=list(a.captures.rglob('*'))
  for i,r in enumerate(files,1):
   name=Path(r['name']).name
   hits=[p for p in available if p.is_file() and p.name==name]
   if len(hits)!=1:raise ValueError(f'Expected one {name}, found {len(hits)}. Supply full original files, not converted samples.')
   path=hits[0];print(f'Hashing original capture {i}/15: {name}',flush=True)
   actual=sha(path);row={'name':name,'bytes':path.stat().st_size,'sha256':actual,'expected_sha256':r['sha256'],'matched':actual==r['sha256']};result['input_files'].append(row)
   if not row['matched']:raise ValueError('Capture identity differs: '+name)
   captures[path.stem]=path
  sys.path.insert(0,str(ROOT))
  from decoder_engine.crosscheck import run as crosscheck
  result['check']=crosscheck(SimpleNamespace(out=out,captures=captures),limit=10000)
  result['status']=result['check']['status']
  if result['status']=='PASS' and (len(result['check']['files'])!=15 or any(r['packets_compared']!=10000 or r['difference_count'] for r in result['check']['files'])):raise ValueError('Incomplete sampled coverage')
  return 0 if result['status']=='PASS' else 2
 except Exception as exc:
  result.update(status='ERROR',reason=str(exc));(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8');return 1
 finally:
  result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  (out/'local_decoder_receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
  archive=out/'LOCAL_DECODER_CHECK.zip'
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for p in sorted(out.iterdir()):
    if p.is_file() and p.suffix in {'.json','.txt'}:z.write(p,p.name)
  print('Status:',result['status']);print('Return this file:',archive)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--captures',required=True,type=Path);p.add_argument('--output',required=True,type=Path,help='New folder; will not overwrite earlier evidence');p.add_argument('--tshark',type=Path);raise SystemExit(run(p.parse_args()))
