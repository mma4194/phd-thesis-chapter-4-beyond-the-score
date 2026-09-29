"""Standard-library notebook controller. Scientific stages run in pinned children."""
from pathlib import Path
import hashlib, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parent
STAGE_ENV={
 'preflight':'public','history':'public','records':'public','supplementary_audit':'public',
 'controlled':'public','thresholds':'residential','fixture_audit':'residential',
 'canonical_metrics':'residential','classifier_capacity':'public',
 'input_verification':'residential','residential':'residential','temporal_controls':'residential',
 'positive_controls':'residential','positive_diagnostics':'residential',
 'telemetry':'public','prepare':'public','decoder':'public','external':'public','report':'public',
}

def default_python(name):
    folder=ROOT/('.venv-'+name)
    return str(folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))

class Workflow:
    def __init__(self, config):
        self.config=dict(config)
        self.run_root=Path(config['run_root']).expanduser().resolve()
        self.run_root.mkdir(parents=True,exist_ok=True)
        self.path=self.run_root/'master_config.json'
        self.path.write_text(json.dumps(self.config,indent=2))
        self.status_root=self.run_root/'master_status';self.status_root.mkdir(exist_ok=True)

    def run(self, stage):
        if stage not in STAGE_ENV:raise ValueError(stage)
        env_name=STAGE_ENV[stage]
        python=Path(self.config[env_name+'_python']).expanduser()
        if not python.is_file():
            raise FileNotFoundError(f'{env_name} Python is missing: {python}. Run tools/setup_environments.py or set its existing interpreter path.')
        log=self.run_root/'logs'/f'{stage}.log';log.parent.mkdir(exist_ok=True)
        env=os.environ.copy()
        env.update({k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']})
        env['MPLBACKEND']='Agg';env['PYTHONUNBUFFERED']='1'
        cmd=[str(python),'-m','artifact.stages','--config',str(self.path),'--stage',stage]
        print(f'{stage}: {python}',flush=True)
        with log.open('w',encoding='utf-8') as stream:
            proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            try:
                for line in proc.stdout:
                    stream.write(line);stream.flush();print(line,end='',flush=True)
                code=proc.wait()
            except BaseException:
                proc.terminate()
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
                raise
        report=self.status_root/(stage+'.json')
        status=json.loads(report.read_text()) if report.is_file() else {'execution_status':'MISSING_STATUS'}
        if code and status.get('execution_status')=='COMPLETED' and status.get('comparison')=='DIFFERENT':
            print(f'{stage}: computation completed, strict comparison DIFFERENT. See {log}.',flush=True)
            return status
        if code:raise RuntimeError(f'{stage} did not complete successfully. Inspect {log}. Status: {status.get("execution_status")}. Rerun this cell to resume a budget pause.')
        return status

    def statuses(self):
        return [json.loads(p.read_text()) for p in sorted(self.status_root.glob('*.json'))]
