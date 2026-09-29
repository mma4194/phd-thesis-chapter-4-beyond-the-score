"""Rebuild strict comparisons for the selected run; never substitutes archived PASS reports."""
import argparse
from src.configuration import load_config
from master_workflow import Workflow
p=argparse.ArgumentParser();p.add_argument('--config',default='config/local.json');a=p.parse_args()
Workflow(load_config(a.config)).run('report')
