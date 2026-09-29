"""Reviewable outputs, retaining unsuccessful and non-estimable outcomes."""
import html, json
from pathlib import Path
import numpy as np
import pandas as pd

def create(project):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures=project.prep/'figures';figures.mkdir(exist_ok=True)
    availability=pd.read_csv(project.prep/'feature_availability.csv')
    a=availability.sort_values('feature');y=np.arange(len(a))
    fig,ax=plt.subplots(figsize=(9,14));ax.barh(y,a.observed_fraction,color='#2467a8');ax.barh(y,1-a.observed_fraction,left=a.observed_fraction,color='#d6dce2')
    ax.set_yticks(y,a.feature.str.replace('router__','net__',regex=False),fontsize=7);ax.set_xlim(0,1);ax.invert_yaxis();ax.set_xlabel('Observed fraction before zero imputation');fig.tight_layout()
    for ext in ['png','pdf']:fig.savefig(figures/('feature_availability.'+ext),dpi=160)
    plt.close(fig)
    status=project.prep_report;sections=[]
    sections.append('<h2>Preparation</h2><pre>'+html.escape(json.dumps(status,indent=2))+'</pre>')
    sections.append('<img src="figures/feature_availability.png" alt="Observed fraction for each feature"><h2>Network availability</h2>'+pd.read_csv(project.prep/'network_coverage_diagnostics.csv').to_html(index=False))
    if project.runtime and project.runtime.get('RUN'):
        run=project.runtime['RUN'];status_file=run/'run_status.json'
        if status_file.exists():sections.append('<h2>Evaluation execution</h2><pre>'+html.escape(status_file.read_text(encoding='utf-8'))+'</pre>')
        for name,title in [('source_checks','All source fits'),('instrument_checks','Metric instrument checks'),('primary_qualification','Primary P0 qualification'),('primary_suite_breadth','Primary capability coverage'),('primary_utility_summary','Primary utility'),('primary_transfer_summary','Paired near/future change'),('primary_C2ST_summary','Primary classifier comparisons')]:
            p=run/'tables'/(name+'.csv')
            if not p.exists():continue
            try:d=pd.read_csv(p)
            except pd.errors.EmptyDataError:sections.append('<h2>'+title+'</h2><p>No estimable rows were produced. This is not a pass.</p>');continue
            sections.append('<h2>'+title+'</h2>'+d.to_html(index=False,escape=True))
        notes=run/'tables'/'primary_utility_rows.csv'
        if notes.exists():
            try:
                d=pd.read_csv(notes)
                if 'permission' in d:
                    q=d.groupby(['source','permission'],dropna=False).size().rename('task_seed_period_rows').reset_index();q.to_csv(run/'tables'/'primary_permission_counts.csv',index=False)
                    sections.append('<h2>All primary permissions, including failures</h2>'+q.to_html(index=False))
            except pd.errors.EmptyDataError:pass
    doc='''<!doctype html><html lang="en"><meta charset="utf-8"><title>TON_IoT reconstruction review</title><style>
body{font:16px/1.55 system-ui,sans-serif;margin:36px;max-width:1400px;color:#172b3b}h1,h2{color:#0057b8}table{border-collapse:collapse;font-size:12px;display:block;overflow:auto}td,th{padding:7px;border:1px solid #ccd6df}pre{white-space:pre-wrap;background:#eef4f8;padding:18px}img{max-width:850px;width:100%}.note{color:#0057b8}</style>
<h1>TON_IoT external reconstruction</h1><p class="note">A new preparation and evaluation, not a restoration of the historical canonical bytes. A completed run can contain scientific failures. Do not replace paper results until the exported evidence has been reviewed.</p>
<p>The available capture prefixes and supplied clock coordinates define this conditional study. Seed intervals are conditional on the chosen tasks and protocol; they do not represent independent homes or deployments.</p>'''+''.join(sections)+'</html>'
    target=project.prep/'REBUILD_REVIEW.html';target.write_text(doc,encoding='utf-8');return target
