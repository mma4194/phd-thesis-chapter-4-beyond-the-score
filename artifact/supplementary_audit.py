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
    status={'execution_status':'COMPLETED','evidence_type':'New arithmetic from archived feature/seed records; no model fitting',
            'median_population_discrepancy':True,'table_s14_original_canonical_matches':bool(df[df.source.eq('canonical_manuscript')].matched_at_six_decimals.all()),
            'table_s14_newer_reference_mismatches':len(mismatch),'strict_supplementary_agreement':'DIFFERENT',
            'reference_files_modified':False,'populations':populations}
    write_json(out/'status.json',status)
    lines=['# Supplementary discrepancies','',
           'These are newly recalculated comparisons of archived records, not newly fitted classifier results. No expected value, tolerance, or decision threshold has been changed.','',
           '## Wasserstein median population','',
           f"At severity one, the all-feature population contains {len(e)} feature/seed rows (nine features across three seeds). The mean of the within-seed feature medians is {populations[0]['mean_of_seed_medians']:.12f}, which prints as 0.269. Excluding zero-IQR features leaves 24 rows (eight features across three seeds). Its mean is {populations[1]['mean_of_seed_means']:.12f} (2.805), but its mean of within-seed medians is {populations[1]['mean_of_seed_medians']:.12f} (0.134). The statement that both 2.805 and 0.269 describe the excluded population is incorrect.",'',
           'Suggested wording: Excluding features with zero reference IQR gives a mean endpoint response of 2.805 and a mean within-seed median feature response of 0.134. The corresponding median summary over all features is 0.269.','',
           'The all-feature endpoint mean is 1463.912775650032, which rounds to 1463.913. This reproduces the arithmetic. It does not make the sparse-feature-dominated quantity a typical effect size.','',
           '## Table S14: two archived result snapshots','',
           'All 20 printed endpoints match the original canonical seed-level table in the finalisation evidence archive. Three printed classifier values differ from the newer controlled reproduction reference bundled with the executable artifact. These are differences between documented snapshots, not three unsupported values in the original table. A software-version explanation has not been established by this record-only comparison.','',
           '| Endpoint | Manuscript and canonical record | Newer controlled reference |','|---|---:|---:|']
    for row in mismatch.to_dict('records'):
        lines.append(f"| {row['perturbation']}, severity {row['severity']} | {row['paper_printed']} | {row['record_printed']} |")
    lines+=['','The changes are below 0.0001 AUC. They still fail exact six-decimal agreement and must remain visible. Preserve the canonical values when reporting that original experiment, or explicitly identify the newer run and use its values consistently. The master notebook checks newly executed fits against their own frozen reference and compares manuscript precision separately.']
    (out/'DISCREPANCIES.md').write_text('\n'.join(lines)+'\n')
    return out
