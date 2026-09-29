"""Portable preparation checks against SHA256-anchored original CSV content.

Only packet-length standard deviations allow an adjacent IEEE-754 float64
value (one ULP). All other CSV fields, row order, headers, missingness and
zero-valued standard deviations must agree exactly. No data are rewritten.
"""
import csv,gzip,hashlib,io,json
from pathlib import Path
import numpy as np
from .common import ROOT,write_json

def check_table(path,reference):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as f:
        reader=csv.reader(f);header=next(reader);rows=list(reader)
    result={'file':Path(path).name,'rows':len(rows),'expected_rows':reference['rows']}
    if header!=reference['columns'] or len(rows)!=reference['rows'] or any(len(row)!=len(header) for row in rows):
        return {**result,'passed':False,'reason':'Header, row count, order of columns or row width differs.'}
    indices={header.index(c):c for c in reference['std_reference']}
    values={c:[] for c in indices.values()}
    text=io.StringIO(newline='');writer=csv.writer(text,lineterminator='\n');writer.writerow(header)
    for row in rows:
        for i,c in indices.items():
            try:values[c].append(float(row[i]) if row[i] else np.nan)
            except ValueError:return {**result,'passed':False,'reason':'Invalid standard-deviation value.'}
            row[i]='<STD>'
        writer.writerow(row)
    result['exact_fields_match']=hashlib.sha256(text.getvalue().encode('utf-8')).hexdigest()==reference['exact_fields_sha256']
    result['standard_deviations']=[]
    for c,v in values.items():
        x=np.asarray(v,dtype=np.float64);y=np.asarray([np.nan if q is None else q for q in reference['std_reference'][c]],dtype=np.float64)
        exact=(x==y)|(np.isnan(x)&np.isnan(y));finite=np.isfinite(x)&np.isfinite(y)
        one_step=finite&(y>0)&(x>=np.nextafter(y,-np.inf))&(x<=np.nextafter(y,np.inf))
        valid=exact|one_step
        result['standard_deviations'].append({'column':c,'passed':bool(valid.all()),'one_ulp_differences':int((~exact&valid).sum()),'rejected_values':int((~valid).sum()),'max_absolute_difference':float(np.max(np.abs(x[finite]-y[finite]))) if finite.any() else 0.})
    result['passed']=result['exact_fields_match'] and all(v['passed'] for v in result['standard_deviations'])
    return result

def verify_prepared(preparation,report_path):
    original=json.loads((ROOT/'reference/toniot/prepared_files.json').read_text())
    refs=json.loads((ROOT/'protocols/toniot_prepared_content.json').read_text())
    required={n for n in original if n.endswith('.csv.gz') and n.startswith(('TON_IoT','general_','iot_named_','telemetry_observed'))}
    if set(refs['files'])!=required:raise RuntimeError('Prepared content reference coverage differs.')
    checks=[]
    for name,ref in refs['files'].items():
        if ref['source_sha256']!=original[name]:raise RuntimeError('Prepared content reference provenance differs: '+name)
        checks.append(check_table(Path(preparation)/name,ref))
    result={'status':'PASS' if all(c['passed'] for c in checks) else 'DIFFERENT','policy':refs['policy'],'checked_files':len(checks),'files':checks,'data_modified':False}
    write_json(report_path,result)
    if result['status']!='PASS':raise ValueError('Prepared content differs beyond the documented formatting/one-ULP rule. Inspect '+str(report_path))
    return result
