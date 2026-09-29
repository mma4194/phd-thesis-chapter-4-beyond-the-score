"""Terminal counterpart of the master notebook. Run from a compute allocation."""
import argparse,json,sys
from pathlib import Path
from src.configuration import load_config
from master_workflow import Workflow,STAGE_ENV
RECORDS=['preflight','history','records','supplementary_audit','thresholds','fixture_audit','report']
FULL=['preflight','history','records','supplementary_audit','thresholds','fixture_audit','canonical_metrics','controlled','input_verification','residential','classifier_capacity','temporal_controls','positive_controls','positive_diagnostics','telemetry','prepare','decoder','external','report']
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/local.json');p.add_argument('--stage',choices=list(STAGE_ENV));a=p.parse_args()
c=load_config(a.config);w=Workflow(c)
for stage in ([a.stage] if a.stage else RECORDS if c['profile']=='records' else FULL):
    w.run(stage)
if not a.stage or a.stage=='report':
    s=json.loads((Path(c['run_root'])/'final_report/status.json').read_text())
    if not s['selected_workflow_checks_passed']:raise SystemExit(2)
