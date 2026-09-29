"""Install only requested isolated environments in home; never alter the caller's environment."""
from pathlib import Path
import argparse,subprocess,sys,os
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--only',choices=['public','residential','both'],default='both')
p.add_argument('--base-dir',type=Path,default=Path.home()/'venvs/beyond-the-score')
p.add_argument('--recorded-locks',action='store_true',help='Use the recorded Linux Python 3.12 dependency closure; requires Python 3.12.')
a=p.parse_args()
if sys.version_info<(3,11):raise SystemExit('Use a Python 3.11 or 3.12 interpreter.')
if a.recorded_locks and sys.version_info[:2]!=(3,12):raise SystemExit('Recorded lock files require Python 3.12. Omit --recorded-locks on Python 3.11.')
for group in ['public','residential']:
    if a.only not in ['both',group]:continue
    folder=(a.base_dir.expanduser()/group).resolve()
    if folder==Path(sys.prefix).resolve():raise SystemExit('Refusing to modify the current environment.')
    subprocess.run([sys.executable,'-m','venv',str(folder)],check=True)
    python=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    req=ROOT/'environment'/(group+'-py312-recorded.lock.txt' if a.recorded_locks else group+'.in')
    subprocess.run([str(python),'-m','pip','install','--no-cache-dir','-r',str(req)],check=True)
    subprocess.run([str(python),'-m','pip','check'],check=True)
    subprocess.run([str(python),str(ROOT/'tools/check_environment.py'),'--group',group,'--output',str(folder/'verified-environment.json')],check=True)
    (folder/'installed-packages.lock.txt').write_text(subprocess.check_output([str(python),'-m','pip','freeze'],text=True))
    print(group.upper()+'_PYTHON =',python)
