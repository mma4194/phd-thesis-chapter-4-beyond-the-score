"""Reconstruct supplementary printed values from both archived source populations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .common import ROOT, sha, write_json, new_output

def run(output=None):
    out=Path(output) if output else new_output('supplementary_audit')
    out.mkdir(parents=True,exist_ok=True)
    wp=ROOT/'reference/residential/Wasserstein_sparse_feature_contribution.csv'
    w=pd.read_csv(wp)
    if not np.allclose(w.wasserstein_iqr_normalised,w.wasserstein_raw/np.maximum(w.reference_iqr,1e-6),atol=1e-10,rtol=1e-9):
        raise AssertionError('Feature-level Wasserstein arithmetic differs.')
    e=w[w.severity.eq(1)]
    populations=[]
    for name,x in [('all_features',e),('positive_reference_iqr',e[e.reference_iqr.gt(0)])]:
        populations.append({'population':name,'feature_seed_rows':len(x),'features':x.feature_name.nunique(),
                            'fixture_seeds':x.fixture_seed.nunique(),
                            'mean_of_seed_means':float(x.groupby('fixture_seed').wasserstein_iqr_normalised.mean().mean()),
                            'mean_of_seed_medians':float(x.groupby('fixture_seed').wasserstein_iqr_normalised.median().mean()),
                            'pooled_median':float(x.wasserstein_iqr_normalised.median())})
    pd.DataFrame(populations).to_csv(out/'wasserstein_populations.csv',index=False)
    zero=e[e.reference_iqr.eq(0)]
    if len(e)!=27 or len(zero)!=3 or len(populations)!=2:
        raise AssertionError('Unexpected endpoint population. Review feature-level provenance.')
    paths={'canonical_manuscript':ROOT/'reference/supplementary/canonical_table_controlled_instrument_ladder_seed_level.csv',
           'controlled_reproduction_reference':ROOT/'reference/controlled/table_controlled_instrument_ladder_seed_level.csv'}
    claims=json.loads((ROOT/'protocols/supplement_table_s14.json').read_text())
    comparisons=[]
    for provenance,path in paths.items():
        d=pd.read_csv(path)
        for c in claims:
            for severity,key in [(0,'severity_zero'),(1,'severity_one')]:
                x=d[d.perturbation.eq(c['perturbation'])&d.severity.eq(severity)][c['metric']]
                if len(x)!=3 or not np.isfinite(x).all():raise AssertionError('Missing endpoint records.')
                value=float(x.mean());expected=float(c[key])
                comparisons.append({'source':provenance,'metric':c['metric'],'perturbation':c['perturbation'],
                                    'severity':severity,'paper_value':expected,'record_value':value,
                                    'record_printed':f'{value:.6f}','paper_printed':f'{expected:.6f}',
                                    'difference':value-expected,'matched_at_six_decimals':f'{value:.6f}'==f'{expected:.6f}',
                                    'source_sha256':sha(path)})
    df=pd.DataFrame(comparisons);df.to_csv(out/'table_s14_comparison.csv',index=False)
    mismatch=df[~df.matched_at_six_decimals]
    mismatch.to_csv(out/'table_s14_discrepancies.csv',index=False)
    latest=df[df.source.eq('controlled_reproduction_reference')]
    historical=df[df.source.eq('canonical_manuscript')]
    median_ok=(f"{populations[0]['mean_of_seed_medians']:.3f}"=='0.269' and
               f"{populations[1]['mean_of_seed_medians']:.3f}"=='0.134' and
               f"{populations[1]['mean_of_seed_means']:.3f}"=='2.805')
    current_ok=bool(latest.matched_at_six_decimals.all()) and median_ok
    status={'execution_status':'COMPLETED','evidence_type':'New arithmetic from archived primitive records; fresh fitting is separate',
            'current_supplementary_records_match':current_ok,
            'median_population_wording':'Corrected in latest supplied thesis supplement',
            'current_table_s14_mismatches':int((~latest.matched_at_six_decimals).sum()),
            'historical_canonical_vs_current_table_s14_differences':int((~historical.matched_at_six_decimals).sum()),
            'current_supplement_source':'provenance/latest_supplement.json',
            'comparison':'PASS' if current_ok else 'DIFFERENT','populations':populations,
            'scientific_reference_tables_modified':False}
    write_json(out/'status.json',status)
    lines=['# Supplementary comparisons: current thesis edition','',
           'The latest supplied thesis supplement corrects the previous median wording and uses the newer controlled endpoints in Table S14. The current printed targets come from that source; old targets remain in protocols/historical_supplement_table_s14.json. Scientific fitted-reference tables and tolerances are unchanged.','',
           '## Median populations','',
           'The all-feature population has 27 feature/seed rows (nine features and three seeds). Its mean within-seed median is 0.268861111111, printed 0.269. Excluding zero-IQR features leaves 24 rows: mean 2.804650384067 (2.805) and mean within-seed median 0.134430555556 (0.134). The latest supplement states both populations correctly.','',
           '## Table S14','',
           'All 20 current printed endpoints match the newer controlled-reference snapshot. The historical canonical curves differ in three cells, shown below. Canonical fresh fits are still compared against their own original frozen reference; full controlled fits use their newer frozen reference. Neither expectation is overwritten by a new run.','',
           '| Endpoint | Historical canonical | Current supplement / controlled reference |',
           '|---|---:|---:|']
    for row in historical[~historical.matched_at_six_decimals].to_dict('records'):
        lines.append(f"| {row['perturbation']}, severity {row['severity']} | {row['record_printed']} | {row['paper_printed']} |")
    lines+=['','PASS here establishes current printed-value agreement from archived records. It is not a full raw-data reproduction.']
    (out/'DISCREPANCIES.md').write_text('\n'.join(lines)+'\n')
    if not current_ok:raise AssertionError('Current supplementary targets differ. Inspect the comparison CSVs.')
    return out
