"""TON_IoT public preparation and evaluation."""
from __future__ import annotations
import hashlib, json, os, platform, re, shutil, sys, time, traceback, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from .telemetry_recovery import Recovery, file_hash, json_write, HISTORICAL_HASHES
from .network import file_cache, merge_group

ROOT=Path(__file__).resolve().parent.parent
PREPARATION_RULES={
 'version':'reconstruction-2.0.0','step_seconds':5,'bin_origin':'Unix epoch, UTC coordinate',
 'bin_interval':'left closed, right open','numeric_aggregation':'arithmetic mean of available filtered records',
 'telemetry_duplicate_policy':'retain all supplied filtered records; original logs verify values and date repair only',
 'fridge_repair':'Only 0?4 Apr 201 in fridge part 3; require exact rowwise measurement and original GMT agreement',
 'network_byte_basis':'original wire length; population standard deviation ddof=0',
 'network_endpoint_pair':'directed outer source/destination IP pair; no ports, no assumed device mapping',
 'interarrival':'sort every complete packet timestamp within each group/bin across files; positive differences only; seconds; ddof=0; undefined means/std are missing',
 'port_rules':{'http':[80],'https':[443],'dns':[53],'mqtt':[1883,8883]},
 'duplicate_packets':'retain records; identical input files rejected; equal timestamps are not proof of duplicate packets',
 'missing_values':'preimputation NaN and explicit observation masks; canonical zero fill, never forward/backward interpolation',
 'empty_network_bins':'unobserved; do not infer zero measured traffic from an empty bin',
 'session_gap_seconds':60,
 'analysis_interval':'longest intersection of general and IoT-named packet sessions and telemetry occupied-bin spans (gaps >60 s); ties choose earliest; exclude first/last bins not fully inside that coordinate interval; bin occupancy does not prove acquisition continuity',
 'incomplete_capture_policy':'complete-record prefixes allowed as a new conditional dataset; incomplete record omitted; its entire bin masked; if header incomplete mask last complete-record bin',
 'malformed_capture_policy':'stop before evaluation; keep earlier per-file caches and error report',
 'clock_policy':'zero offset; no performance/overlap-optimised alignment; UTC coordinates do not prove physical clock synchronization',
 'historical_identity':'new dataset; no historical byte-identical reconstruction claim',
}

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def code_manifest():
    return {p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted((ROOT/'external_rebuild').rglob('*')) if p.is_file() and p.suffix in ('.py','.json')}
def csv_write(frame,path,index=False):
    path=Path(path);tmp=path.with_name(path.name+'.tmp')
    frame.to_csv(tmp,index=index,compression={'method':'gzip','mtime':0} if path.name.endswith('.gz') else None)
    tmp.replace(path)
def sessions(first,last=None,gap_ns=60_000_000_000):
    first=np.asarray(first,dtype=np.int64);last=first if last is None else np.asarray(last,dtype=np.int64)
    order=np.argsort(first,kind='stable');out=[]
    for i in order:
        lo,hi=int(first[i]),int(last[i])
        if not out or lo-out[-1][1]>gap_ns:out.append([lo,hi])
        else:out[-1][1]=max(out[-1][1],hi)
    return out
def intersect_intervals(a,b):
    out=[]
    for l,r in a:
        for x,y in b:
            if max(l,x)<=min(r,y):out.append([max(l,x),min(r,y)])
    return sorted(out)
def epoch_ns(index):
    return pd.DatetimeIndex(index).as_unit('ns').asi8

class Project:
    def __init__(self,data_root,output_root=None,telemetry_input=None,pcap_root=None,n_jobs=4,budget_hours=6):
        self.data_root=Path(data_root).expanduser().resolve()
        self.out=Path(output_root).expanduser().resolve() if output_root else ROOT/'TON_IoT'
        self.telemetry_input=Path(telemetry_input).expanduser().resolve() if telemetry_input else self.data_root/'TON_IOT_IOT_DATA.zip'
        self.pcap_root=Path(pcap_root).expanduser().resolve() if pcap_root else self.data_root/'pcap_files'
        self.n_jobs=max(1,int(n_jobs));self.budget_hours=None if budget_hours is None else float(budget_hours)
        self.out.mkdir(parents=True,exist_ok=True);self.status={};self.prep=None;self.runtime=None
        self.configuration={'data_root':str(self.data_root),'output_root':str(self.out),'telemetry_input':str(self.telemetry_input),
                            'pcap_root':str(self.pcap_root),'n_jobs':self.n_jobs,'budget_hours':self.budget_hours}
        json_write(self.out/'latest_configuration.json',self.configuration)
    def phase(self,name,fn):
        print(f'\n{name} ...',flush=True);start=time.monotonic()
        try:r=fn()
        except BaseException as exc:
            self.status[name]={'status':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'ERROR','error':repr(exc),'traceback':traceback.format_exc()}
            json_write(self.out/'latest_status.json',self.status)
            try:self.export()
            except Exception as export_error:print('Report export also failed:',repr(export_error),flush=True)
            raise
        self.status[name]={'status':'COMPLETE','seconds':round(time.monotonic()-start,3)}
        json_write(self.out/'latest_status.json',self.status);print(f'{name}: complete ({time.monotonic()-start:.1f} s)',flush=True);return r
    def inventory(self):
        if not self.data_root.is_dir():raise FileNotFoundError(f'DATA_ROOT is not a folder: {self.data_root}')
        if not self.telemetry_input.is_file():raise FileNotFoundError(f'Telemetry ZIP required: {self.telemetry_input}')
        if not self.pcap_root.is_dir():raise FileNotFoundError(f'Capture folder required: {self.pcap_root}')
        # Explicit names avoid pulling attack captures, old outputs or duplicate copies into the run.
        expected=[f'normal_{i}' for i in range(1,14)]+['normal_IoT_2','normal_IoT_3'];found={x:[] for x in expected};ignored=[]
        for p in self.pcap_root.rglob('*'):
            if p.is_file() and p.suffix.lower() in ('.pcap','.pcapng'):
                if p.stem in found:found[p.stem].append(p.resolve())
                else:ignored.append(str(p))
        bad={k:[str(p) for p in v] for k,v in found.items() if len(v)!=1}
        if bad:raise FileNotFoundError('Each expected normal capture must appear exactly once. Missing or ambiguous names: '+json.dumps(bad))
        self.captures={k:v[0] for k,v in found.items()}
        rows=[{'role':'telemetry','name':self.telemetry_input.name,'path':str(self.telemetry_input),'bytes':self.telemetry_input.stat().st_size}]
        rows += [{'role':'iot_named' if '_IoT_' in k else 'general','name':p.name,'path':str(p),'bytes':p.stat().st_size} for k,p in self.captures.items()]
        csv_write(pd.DataFrame(rows),self.out/'input_inventory.csv');json_write(self.out/'ignored_capture_paths.json',ignored)
        free=shutil.disk_usage(self.out).free
        print(f'Found 15 normal captures and telemetry ZIP. Output drive has {free/2**30:.1f} GiB free.',flush=True)
        if free<4*2**30:raise RuntimeError('At least 4 GiB free output space is required; 10 GiB or more is preferable for arrays/checkpoints.')
        return pd.DataFrame(rows)
    def prepare(self):
        if not hasattr(self,'captures'):self.inventory()
        self.codes=code_manifest();inputs=[];caches={'general':[],'iot_named':[]};seen={};capture_progress=[];comparisons=[]
        prior=json.loads((ROOT/'external_rebuild'/'reference_capture_audit.json').read_text(encoding='utf-8'))['captures']
        json_write(self.out/'preparation_plan.json',{'rules':PREPARATION_RULES,'source_manifest':self.codes})
        thash=file_hash(self.telemetry_input)
        inputs.append({'role':'telemetry','name':self.telemetry_input.name,'sha256':thash,'bytes':self.telemetry_input.stat().st_size})
        tkey=digest({'input':thash,'engine':self.codes['external_rebuild/telemetry_recovery.py']})
        tc=self.out/'cache'/'telemetry'/tkey;checkpoint=tc/'verified.json'
        if checkpoint.exists():
            record=json.loads(checkpoint.read_text(encoding='utf-8'));telemetry_dir=tc/record['directory']
            for rel,h in record['files'].items():
                if file_hash(telemetry_dir/rel)!=h:raise RuntimeError('Changed telemetry checkpoint: '+rel)
            print('Reusing verified telemetry preparation.',flush=True)
        else:
            recovery=Recovery({'input_root':str(self.data_root),'telemetry_input':str(self.telemetry_input),'output_root':str(tc)})
            recovery.locate();recovery.telemetry();telemetry_dir=recovery.out
            record={'directory':telemetry_dir.relative_to(tc).as_posix(),'repair_count':recovery.repair_count,
                    'files':{p.relative_to(telemetry_dir).as_posix():file_hash(p) for p in telemetry_dir.rglob('*') if p.is_file()}}
            json_write(checkpoint,record)
        self.telemetry_dir=telemetry_dir
        for name,path in self.captures.items():
            try:meta,folder=file_cache(path,self.out/'cache'/'network')
            except Exception as exc:
                json_write(self.out/'capture_error.json',{'file':str(path),'error':repr(exc),'traceback':traceback.format_exc()});raise
            capture_progress.append(meta);json_write(self.out/'capture_progress.json',capture_progress)
            old=prior.get(path.name);same=bool(old and old['sha256']==meta['sha256'])
            fields=['bytes','packets','first_ns','last_ns','integrity_status','backward_steps']
            agrees=all(old[k]==meta[k] for k in fields) if same else None
            comparisons.append({'file':path.name,'same_bytes_as_prior_audit':same,'timestamp_audit_reproduced':agrees,'status':'MATCH' if agrees else ('NEW_INPUT_BYTES' if not same else 'DISAGREEMENT')})
            csv_write(pd.DataFrame(comparisons),self.out/'capture_audit_comparison.csv')
            if same and not agrees:raise RuntimeError('Timestamp/count results differ from the prior audit of identical bytes: '+path.name)
            if meta['sha256'] in seen:raise RuntimeError(f'Identical capture bytes in {name} and {seen[meta["sha256"]]}; select the correct distinct input files')
            seen[meta['sha256']]=name;role='iot_named' if '_IoT_' in name else 'general';caches[role].append((meta,folder))
            inputs.append({'role':role,'name':path.name,'sha256':meta['sha256'],'bytes':meta['bytes']})
        identity={'rules':PREPARATION_RULES,'input_files':inputs,'code_files':self.codes}
        self.prep_id=digest(identity);self.prep=self.out/'preparation'/('prep_'+self.prep_id[:16]);self.prep.mkdir(parents=True,exist_ok=True)
        json_write(self.prep/'preparation_protocol.json',identity)
        shutil.copytree(telemetry_dir/'tables',self.prep/'telemetry_audit',dirs_exist_ok=True)
        frames={};metadata=[]
        for role,files in caches.items():
            frame,meta=merge_group(files);frames[role]=frame;metadata.extend([{**m,'role':role} for m in meta])
            csv_write(frame,self.prep/(role+'_5s_features.csv.gz'),index=True)
        json_write(self.prep/'capture_metadata.json',metadata)
        telemetry=pd.read_csv(telemetry_dir/'prepared_telemetry'/'telemetry_5s_preimputation.csv.gz',parse_dates=['timestamp_utc_coordinate']).set_index('timestamp_utc_coordinate')
        telemetry.index=pd.to_datetime(telemetry.index,utc=True);tns=epoch_ns(telemetry.index)
        candidates=sessions(tns,tns+4_999_999_999)
        for role,frame in frames.items():candidates=intersect_intervals(candidates,sessions(frame['_first_ns'],frame['_last_ns']))
        if not candidates:raise RuntimeError('No shared recorded-time session across telemetry and both capture groups')
        lo,hi=sorted(candidates,key=lambda x:(-(x[1]-x[0]),x[0]))[0]
        # Retain only whole 5-second bins within the intersection. No target historical row count.
        first=(lo+4_999_999_999)//5_000_000_000;stop=hi//5_000_000_000
        bins=np.arange(first,stop,dtype=np.int64)
        if len(bins)<18000:raise RuntimeError(f'Only {len(bins)} whole 5 s bins in the longest common session; insufficient for this fixed evaluation design')
        idx=pd.to_datetime(bins*5_000_000_000,utc=True);idx.name='timestamp_utc_coordinate'
        assets=json.loads((ROOT/'external_rebuild'/'recovered'/'historical_assets.json').read_text(encoding='utf-8'))
        features=sorted(set(sum(assets['external']['c2st']['scopes'].values(),[])))
        pre=telemetry.reindex(idx).copy();coverage=[]
        for role,frame in frames.items():
            frame=frame.reindex(bins);frame.index=idx
            for col in features:
                prefix='router__'+role+'__'
                if col.startswith(prefix):
                    name=col[len(prefix):]
                    if name not in frame:raise RuntimeError('Missing constructed network feature: '+name)
                    pre[col]=frame[name].mask(frame['_incomplete_boundary'].fillna(0).astype(bool))
            coverage.append({'group':role,'occupied_bin_fraction':float(frame.packet_count.notna().mean()),
                             'masked_incomplete_boundary_bins':int(frame['_incomplete_boundary'].fillna(0).sum()),
                             'header_decode_error_bins':int(frame.get('_header_decode_errors',pd.Series(0,index=idx)).fillna(0).gt(0).sum())})
        if set(features)-set(pre):raise RuntimeError('Required features not prepared')
        values=pre[features].copy();values.replace([np.inf,-np.inf],np.nan,inplace=True)
        observed=values.notna();canon=values.fillna(0);seconds=(bins-bins[0])*5
        for data in (values,canon,observed):data.insert(0,'sec',seconds)
        counts=pre[[c for c in pre if c.endswith('__observed_count')]].fillna(0).astype(np.int64)
        csv_write(values,self.prep/'TON_IoT_normal_5s_preimputation_rebuilt.csv.gz',index=True)
        csv_write(canon,self.prep/'TON_IoT_normal_5s_canonical_rebuilt.csv.gz',index=True)
        csv_write(observed,self.prep/'TON_IoT_normal_5s_observed_mask.csv.gz',index=True)
        csv_write(counts,self.prep/'telemetry_observed_counts.csv.gz',index=True)
        csv_write(pd.DataFrame(coverage),self.prep/'network_coverage_diagnostics.csv')
        csv_write(pd.DataFrame([{'feature':c,'observed_rows':int(observed[c].sum()),'observed_fraction':float(observed[c].mean()),'canonical_zero_fraction':float((canon[c]==0).mean())} for c in features]),self.prep/'feature_availability.csv')
        incomplete=[Path(m['file']).name for m in metadata if m['integrity_status']!='COMPLETE_RECORD_STREAM']
        self.prep_report={'preparation_id':self.prep_id,'rows':len(bins),'value_features':len(features),'start':str(idx[0]),'end':str(idx[-1]),
            'fridge_dates_repaired':record['repair_count'],'complete_packet_records':sum(m['packets'] for m in metadata),
            'incomplete_captures':incomplete,'scientific_status':'CONDITIONAL_COMPLETE_RECORD_PREFIX' if incomplete else 'RECONSTRUCTED_NEW_DATASET',
            'historical_raw_to_canonical_reproduction':'NOT_ESTABLISHED','historical_expected_hashes':HISTORICAL_HASHES,
            'candidate_shared_sessions_ns':candidates,'clock_synchronization':'NOT_INDEPENDENTLY_ESTABLISHED',
            'source_data_modified':False,'whole_bins_only':True,'evaluation_completed':False}
        json_write(self.prep/'preparation_status.json',self.prep_report)
        json_write(self.prep/'preparation_record.json',self.prep_report)
        files={p.relative_to(self.prep).as_posix():file_hash(p) for p in self.prep.rglob('*') if p.is_file() and p.name not in {'prepared_files.json','preparation_status.json','preparation_verified.json'} and 'verified_input_checks' not in p.parts}
        json_write(self.prep/'prepared_files.json',files);json_write(self.out/'latest_preparation.json',{'path':self.prep.relative_to(self.out).as_posix(),'id':self.prep_id})
        return self.prep_report
    def load_prepared(self):
        if self.prep is None:
            pointer=json.loads((self.out/'latest_preparation.json').read_text(encoding='utf-8'));self.prep=self.out/pointer['path'];self.prep_id=pointer['id']
        for name,h in json.loads((self.prep/'prepared_files.json').read_text(encoding='utf-8')).items():
            if file_hash(self.prep/name)!=h:raise RuntimeError('Prepared file changed: '+name)
        self.prep_report=json.loads((self.prep/'preparation_record.json').read_text(encoding='utf-8'))
        def read(kind):
            d=pd.read_csv(self.prep/f'TON_IoT_normal_5s_{kind}_rebuilt.csv.gz',parse_dates=['timestamp_utc_coordinate'])
            d['timestamp_utc_coordinate']=pd.to_datetime(d['timestamp_utc_coordinate'],utc=True);return d
        c,p=read('canonical'),read('preimputation');cols=[x for x in c if x.startswith(('iot__','router__'))]
        times=c.timestamp_utc_coordinate
        if not times.equals(p.timestamp_utc_coordinate) or times.isna().any() or times.duplicated().any() or not (np.diff(epoch_ns(times))==5_000_000_000).all():raise RuntimeError('Invalid or unequal prepared time axes')
        sec=(epoch_ns(times)-int(epoch_ns(times)[0]))/1e9
        if not np.array_equal(sec,c.sec) or not np.array_equal(sec,p.sec):raise RuntimeError('Elapsed time mismatch')
        if not np.array_equal(c[cols].to_numpy(),p[cols].fillna(0).to_numpy()):raise RuntimeError('Canonical values differ from the declared zero imputation')
        return c[cols],np.isfinite(p[cols].to_numpy(float)),sec,{'preparation':self.prep_id,'canonical':file_hash(self.prep/'TON_IoT_normal_5s_canonical_rebuilt.csv.gz'),'preimputation':file_hash(self.prep/'TON_IoT_normal_5s_preimputation_rebuilt.csv.gz')}
    def software_checks(self):
        from .evaluation import runtime
        ns=runtime(self)
        with ns['threadpool_limits'](limits=1):checks=ns['run_software_checks']()
        json_write(self.out/'software_checks.json',checks)
        return pd.DataFrame(checks)
    def evaluate(self):
        from .evaluation import run
        return run(self)
    def export(self):
        if self.prep is not None:
            try:
                from .reporting import create
                create(self)
            except Exception as exc:
                json_write(self.out/'report_render_error.json',{'error':repr(exc)})
        if self.runtime and self.runtime.get('RUN'):
            root=self.runtime['RUN']
            manifest=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in sorted(root.rglob('*')) if p.is_file() and p.name!='result_file_manifest.csv']
            csv_write(pd.DataFrame(manifest),root/'result_file_manifest.csv')
        dest=self.out/'TIOT_EXTERNAL_REBUILD_RESULTS_TO_SHARE.zip';tmp=dest.with_suffix('.tmp.zip');included=[]
        roots=[self.prep] if self.prep else []
        if self.runtime and self.runtime.get('RUN'):roots.append(self.runtime['RUN'])
        top=[p for p in self.out.glob('*') if p.is_file() and p.suffix in ('.json','.csv')]
        selected=list(top)
        for root in roots:
            selected.extend(p for p in root.rglob('*') if p.is_file() and 'arrays' not in p.relative_to(root).parts and (not p.name.endswith('.csv.gz') or p.name=='fridge_date_repair_all_rows.csv.gz'))
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(set(selected)):
                rel=p.relative_to(self.out).as_posix();z.write(p,rel);included.append({'path':rel,'bytes':p.stat().st_size,'sha256':file_hash(p)})
            for p in sorted((ROOT/'external_rebuild').rglob('*')):
                if p.is_file() and p.suffix in ('.py','.json'):z.write(p,'calculation_source/'+p.relative_to(ROOT/'external_rebuild').as_posix())
            z.writestr('SHARED_FILE_MANIFEST.json',json.dumps(included,indent=2))
            z.writestr('READ_ME.txt','New reconstruction, not restoration of the old canonical bytes. Raw captures, telemetry values and prediction/generated arrays stay local. Every local evaluation array has a separate hash manifest. Send this ZIP for review, including when execution fails. Inspect scientific_status and execution_status separately.')
        tmp.replace(dest);print('Send this file back:',dest,flush=True);return dest
