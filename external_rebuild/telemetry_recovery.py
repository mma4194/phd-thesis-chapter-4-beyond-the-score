"""TON_IoT timestamp recovery: auditable input preparation, zero model fitting.

This is a new implementation, not a claim to have recovered the lost historical
preparation. Filtered measurements are preserved; only source-verified malformed
fridge dates may change. Capture analysis reads timestamps, not packet features.
"""
from __future__ import annotations
import collections, contextlib, datetime as dt, gzip, hashlib, html, io, json
import os, platform, re, struct, sys, time, traceback, uuid, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

VERSION = '1.1.0'
COMPATIBLE_COMPLETE_CACHE_SHA256 = {'c0a439b55c0e47ca4048b2196296435c1a6ec848ec5226dc1f6d963a5effe181'}
ENGINE_SHA256 = globals().get('ENGINE_SHA256') or (
    hashlib.sha256(Path(__file__).read_bytes()).hexdigest() if '__file__' in globals() else 'source-unavailable')
FAMILIES = ('fridge','Garage_door','GPS_Tracker','modbus','Motion_Light','Thermostat','weather')
# Filtered columns are positional because upstream names vary between parts.
SCHEMA = {
 'fridge': [('temperature_mean','Fridge_Temperature','number'),('condition_high_fraction','Temp_Condition','high')],
 'Garage_door': [('door_open_fraction','door state','open'),('smartphone_signal_true_fraction','sphone signal','bool')],
 'GPS_Tracker': [('latitude_mean','lat','number'),('longitude_mean','long','number')],
 'modbus': [(f'register_{i+1}_mean',i,'number') for i in range(4)],
 'Motion_Light': [('motion_true_fraction','Motion Detected','bool'),('light_on_fraction','Lights Condition','on')],
 'Thermostat': [('temperature_mean','current temperature','number'),('status_true_fraction','AC_state','bool')],
 'weather': [('temperature_mean','temperature','number'),('pressure_mean','pressure','number'),('humidity_mean','humidity','number')],
}
SLUG={'Garage_door':'garage','GPS_Tracker':'gps','Motion_Light':'motion_light','Thermostat':'thermostat'}
HISTORICAL_HASHES={'canonical':'4fd1d7225202e111c20e521f19afd56b0c319059d21037d929a2257a3b3a5692',
 'preimputation':'e9ceacc4d8638ef1f7e56c8bc8d2004430f1de413bd677d124a9ffb6b893968d'}


def json_write(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,default=str,allow_nan=False), encoding='utf-8');tmp.replace(path)


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def strict_csv_time(frame):
    """Explicit observed source formats; no ambiguous month/day inference."""
    days=frame.iloc[:,0].astype(str).str.strip()
    parsed={}
    for s in days.unique():
        value=pd.NaT
        for pattern,fmt in [(r'\d{1,2} [A-Za-z]{3} \d{4}','%d %b %Y'),
                            (r'\d{1,2}-[A-Za-z]{3}-\d{2}','%d-%b-%y'),
                            (r'\d{1,2}/\d{1,2}/\d{4}','%d/%m/%Y')]:
            if re.fullmatch(pattern,s):
                try:value=pd.Timestamp(dt.datetime.strptime(s,fmt),tz='UTC')
                except ValueError:pass
                break
        parsed[s]=value
    base=pd.to_datetime(days.map(parsed),utc=True)
    times=frame.iloc[:,1].astype(str).str.strip()
    seconds=pd.Series(np.nan,index=frame.index)
    for ampm,fmt in [(False,'%H:%M:%S'),(True,'%I:%M:%S %p')]:
        mask=times.str.contains(r'(?i)\b(?:AM|PM)$',regex=True)==ampm
        v=pd.to_datetime(times.loc[mask],format=fmt,errors='coerce')
        seconds.loc[mask]=v.dt.hour*3600+v.dt.minute*60+v.dt.second
    return base+pd.to_timedelta(seconds,unit='s')


def numeric_channel(values,kind):
    s=pd.Series(values).reset_index(drop=True)
    if kind=='number':return pd.to_numeric(s,errors='coerce').astype(float)
    words=s.astype(str).str.strip().str.lower()
    choices={'bool':{'true':1.,'false':0.,'1':1.,'0':0.},
             'high':{'high':1.,'low':0.},
             'open':{'open':1.,'closed':0.,'true':1.,'false':0.},
             'on':{'on':1.,'off':0.,'true':1.,'false':0.}}
    return words.map(choices[kind]).astype(float)


def written_precision_match(tokens,a,b,kind):
    """Check numeric log values against half of the CSV token's last decimal unit.

    This checks compatibility with decimal rounding, not scientific equivalence.
    Boolean/state channels require exact agreement, including missingness.
    """
    if kind!='number':return (a==b)|(np.isnan(a)&np.isnan(b))
    s=pd.Series(tokens).astype(str).str.strip().str.lower()
    mantissa=s.str.split('e').str[0]
    exponent=pd.to_numeric(s.str.extract(r'e([+-]?\d+)$',expand=False),errors='coerce').fillna(0)
    decimals=mantissa.str.partition('.')[2].str.len()
    quantum=np.power(10.,(exponent-decimals).to_numpy())
    roundoff=8*np.finfo(float).eps*np.maximum(1.,np.abs(b))
    return (np.abs(a-b)<=0.5*quantum+roundoff)|(np.isnan(a)&np.isnan(b))


def bounded_files(root,depth=3,extensions=None):
    """No symlink traversal; a limited walk of explicitly selected roots."""
    root=Path(root)
    if not root.is_dir():return []
    found=[]
    for base,dirs,files in os.walk(root,followlinks=False):
        rel=Path(base).relative_to(root)
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not Path(base,d).is_symlink()
                       and not d.startswith('run_') and d not in {'cache','node_modules','verified_results'})
        if len(rel.parts)>=depth:dirs[:]=[]
        for name in sorted(files):
            p=Path(base,name)
            if not p.is_symlink() and (extensions is None or p.suffix.lower() in extensions):found.append(p)
    return found


class TelemetrySource:
    def __init__(self,path):
        self.path=Path(path).expanduser().resolve();self.zip=None;self.members={}
        if self.path.is_file() and zipfile.is_zipfile(self.path):
            self.zip=zipfile.ZipFile(self.path)
            for n in self.zip.namelist():
                if n.endswith('/'):continue
                name=Path(n).name
                if re.fullmatch(r'IoT_normal_.+_[123]\.(csv|log)',name):
                    if name in self.members:raise ValueError('Ambiguous duplicate telemetry basename: '+name)
                    self.members[name]=n
        elif self.path.is_dir():
            for p in bounded_files(self.path,4,{'.csv','.log'}):
                if re.fullmatch(r'IoT_normal_.+_[123]\.(csv|log)',p.name):
                    if p.name in self.members:raise ValueError('Multiple copies: set TELEMETRY_INPUT to one dataset folder.')
                    self.members[p.name]=p
        else:raise FileNotFoundError(f'TELEMETRY_INPUT must be a ZIP or extracted dataset folder: {self.path}')
        expected={f'IoT_normal_{fam}_{part}.{ext}' for fam in FAMILIES for part in (1,2,3) for ext in ('csv','log')}
        missing=sorted(expected-self.members.keys())
        if missing:raise FileNotFoundError('Both normal folders are needed. Missing: '+', '.join(missing))

    def read(self,name):
        return self.zip.read(self.members[name]) if self.zip else Path(self.members[name]).read_bytes()

    def close(self):
        if self.zip:self.zip.close()


class HashReader:
    def __init__(self,path):self.f=open(path,'rb',buffering=1024*1024);self.h=hashlib.sha256();self.n=0
    def read(self,n):
        b=self.f.read(n);self.h.update(b);self.n+=len(b);return b
    def exact(self,n):
        b=self.read(n)
        if len(b)!=n:raise ValueError(f'Truncated capture at byte {self.n}; needed {n} bytes, received {len(b)}')
        return b
    def close(self):self.f.close()


def capture_summary(path,progress=None):
    """Streaming PCAP/PCAPNG timestamps. Does not infer traffic absence or decode payloads.
    PCAP 2.4 micro/nanoseconds, both byte orders. PCAPNG SHB/IDB/EPB/obsolete PB;
    interface resolution and offset honoured; untimestamped SPB counted explicitly.
    """
    r=HashReader(path);bins=collections.Counter();limits={};meta={'file':str(path),'packets':0,
      'untimestamped_packets':0,'backward_steps':0,'truncated_payloads':0,'subnanosecond_timestamps':0,
      'unknown_blocks':0,'interfaces':[],'first_ns':None,'last_ns':None,
      'integrity_status':'COMPLETE_RECORD_STREAM','incomplete_record':None}
    previous=None;last_report=time.monotonic()
    def add(ns,caplen,wirelen,iface):
        nonlocal previous,last_report
        if ns<0 or ns>=9223372036854775807:raise ValueError('Capture timestamp outside supported datetime range')
        if previous is not None and ns<previous:meta['backward_steps']+=1
        previous=ns;meta['packets']+=1;meta['truncated_payloads']+=int(caplen<wirelen)
        meta['first_ns']=ns if meta['first_ns'] is None else min(meta['first_ns'],ns)
        meta['last_ns']=ns if meta['last_ns'] is None else max(meta['last_ns'],ns)
        k=ns//5_000_000_000;bins[k]+=1
        if k in limits:limits[k]=[min(limits[k][0],ns),max(limits[k][1],ns)]
        else:limits[k]=[ns,ns]
        if progress and time.monotonic()-last_report>30:
            progress(f'{Path(path).name}: {meta["packets"]:,} packets, {r.n/1e9:.2f} GB read');last_report=time.monotonic()
    def options(data,endian):
        i=0;out={}
        while i+4<=len(data):
            code,size=struct.unpack_from(endian+'HH',data,i);i+=4
            if code==0:break
            if i+size>len(data):raise ValueError('Truncated PCAPNG option')
            out[code]=data[i:i+size];i+=(size+3)//4*4
        return out
    try:
        magic=r.exact(4)
        magics={b'\xd4\xc3\xb2\xa1':('<',1000),b'\xa1\xb2\xc3\xd4':('>',1000),
                b'\x4d\x3c\xb2\xa1':('<',1),b'\xa1\xb2\x3c\x4d':('>',1)}
        if magic in magics:
            endian,mult=magics[magic];hdr=struct.unpack(endian+'HHiiII',r.exact(20))
            if hdr[:2]!=(2,4) or hdr[4]==0:raise ValueError('Unsupported PCAP version or snap length')
            meta.update(format='pcap',interfaces=[{'linktype':hdr[5]&0xffff,'nanoseconds_per_tick':mult}])
            while True:
                b=r.read(16)
                if not b:break
                if len(b)!=16:
                    meta['integrity_status']='INCOMPLETE_EOF'
                    meta['incomplete_record']={'kind':'packet_header','record_start_byte':r.n-len(b),
                        'expected_bytes':16,'available_bytes':len(b),'missing_bytes_in_declared_record':16-len(b),
                        'interpretation':'Earlier complete records only; missing subsequent records cannot be determined.'}
                    break
                sec,fraction,caplen,wirelen=struct.unpack(endian+'IIII',b)
                if fraction>=1_000_000_000//mult or caplen>wirelen or caplen>hdr[4] or caplen>128*1024*1024:
                    raise ValueError('Invalid PCAP timestamp or packet length')
                payload_start=r.n
                data=r.read(caplen)
                if len(data)!=caplen:
                    meta['integrity_status']='INCOMPLETE_EOF'
                    meta['incomplete_record']={'kind':'packet_payload','record_start_byte':payload_start-16,
                        'payload_start_byte':payload_start,'expected_bytes':caplen,'available_bytes':len(data),
                        'missing_bytes_in_declared_record':caplen-len(data),
                        'excluded_record_timestamp_ns':sec*1_000_000_000+fraction*mult,
                        'interpretation':'Incomplete record excluded; additional missing records cannot be determined.'}
                    break
                add(sec*1_000_000_000+fraction*mult,caplen,wirelen,0)
        elif magic==b'\x0a\x0d\x0d\x0a':
            meta['format']='pcapng';prefix=magic;interfaces=[];endian=None
            while prefix:
                if len(prefix)!=4:raise ValueError('Truncated PCAPNG block type')
                rawlen=r.exact(4)
                if prefix==b'\x0a\x0d\x0d\x0a':
                    bom=r.exact(4)
                    endian={b'\x4d\x3c\x2b\x1a':'<',b'\x1a\x2b\x3c\x4d':'>'}.get(bom)
                    if not endian:raise ValueError('Invalid PCAPNG byte-order magic')
                    size=struct.unpack(endian+'I',rawlen)[0]
                    if size<28 or size%4 or size>128*1024*1024:raise ValueError('Invalid PCAPNG section length')
                    tail=r.exact(size-12);body=bom+tail[:-4]
                    if struct.unpack(endian+'I',tail[-4:])[0]!=size:raise ValueError('PCAPNG block length mismatch')
                    if struct.unpack_from(endian+'HH',body,4)[0]!=1:raise ValueError('Unsupported PCAPNG version')
                    interfaces=[]
                else:
                    size=struct.unpack(endian+'I',rawlen)[0];kind=struct.unpack(endian+'I',prefix)[0]
                    if size<12 or size%4 or size>128*1024*1024:raise ValueError('Invalid PCAPNG block length')
                    rest=r.exact(size-8)
                    if struct.unpack(endian+'I',rest[-4:])[0]!=size:raise ValueError('PCAPNG block length mismatch')
                    body=rest[:-4]
                    if kind==1:
                        if len(body)<8:raise ValueError('Truncated interface block')
                        link,_,snap=struct.unpack_from(endian+'HHI',body);opt=options(body[8:],endian)
                        resolution=opt.get(9,b'\x06')
                        if len(resolution)!=1:raise ValueError('Invalid timestamp resolution')
                        v=resolution[0];den=2**(v&127) if v&128 else 10**v
                        off=opt.get(14,b'\x00'*8)
                        if len(off)!=8:raise ValueError('Invalid timestamp offset')
                        offset=struct.unpack(endian+'q',off)[0]
                        interfaces.append((den,offset,snap));meta['interfaces'].append({'linktype':link,'ticks_per_second':den,'offset_seconds':offset})
                    elif kind in (6,2):
                        if len(body)<20:raise ValueError('Truncated timestamped packet block')
                        if kind==6:iface,hi,lo,caplen,wirelen=struct.unpack_from(endian+'IIIII',body)
                        else:iface,_,hi,lo,caplen,wirelen=struct.unpack_from(endian+'HHIIII',body)
                        if iface>=len(interfaces):raise ValueError('Packet references missing interface')
                        den,off,snap=interfaces[iface]
                        if caplen>wirelen or (snap and caplen>snap) or 20+(caplen+3)//4*4>len(body):raise ValueError('Invalid captured length')
                        numerator=((hi<<32)|lo)*1_000_000_000
                        meta['subnanosecond_timestamps']+=int(numerator%den!=0)
                        add(numerator//den+off*1_000_000_000,caplen,wirelen,iface)
                    elif kind==3:
                        if len(body)<4 or not interfaces:raise ValueError('Invalid simple packet block')
                        meta['untimestamped_packets']+=1
                    else:meta['unknown_blocks']+=1
                prefix=r.read(4)
        else:raise ValueError('Unsupported capture magic; use an uncompressed PCAP/PCAPNG')
        meta['bytes']=r.n;meta['sha256']=r.h.hexdigest()
        ordered=sorted(bins);sessions=[]
        for k in ordered:
            lo,hi=limits[k]
            if not sessions or lo-sessions[-1][1]>60_000_000_000:sessions.append([lo,hi])
            else:sessions[-1][1]=max(sessions[-1][1],hi)
        # Exact >60 s gaps cannot be hidden inside one 5 s bucket. Counts never span files.
        meta['sessions_ns']=sessions
        return meta,[(k,bins[k],*limits[k]) for k in ordered]
    finally:r.close()


class Recovery:
    def __init__(self,config):
        self.config=dict(config);self.start=time.perf_counter();self.checks=[];self.inventory=[];self.pairs=[]
        self.repairs=[];self.original_errors=[];self.bins=None;self.capture_bins={};self.capture_meta=[];self.historical={}
        root=Path(config['output_root']).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
        self.run_id=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
        self.out=root/('run_'+self.run_id);self.out.mkdir()
        self.cache=root/'cache';self.cache.mkdir(exist_ok=True)
        self.table_dir=self.out/'tables';self.table_dir.mkdir()
        self.data_dir=self.out/'prepared_telemetry';self.data_dir.mkdir()
        self.note('no_model_fitting','PASS','This workflow performs no generator, prediction or classifier fits.')
        json_write(self.out/'configuration.json',self.config)
        json_write(self.out/'environment.json',{'python':sys.version,'platform':platform.platform(),
          'numpy':np.__version__,'pandas':pd.__version__,'version':VERSION,'engine_sha256':ENGINE_SHA256})
        source=globals().get('ENGINE_SOURCE')
        if source is None and globals().get('__file__'):
            source=Path(__file__).read_text()
        if source:(self.out/'recovery_engine.py').write_text(source, encoding='utf-8')
        json_write(self.out/'preparation_protocol.json',{
          'declared_before_data_analysis':True,'step_seconds':5,'bin_origin':'Unix epoch UTC',
          'bin_interval':'left-closed, right-open','numeric_aggregation':'arithmetic mean of available records',
          'binary_aggregation':'fraction of observed records in the true state',
          'duplicate_policy':'retain all supplied rows','missing_policy':'NaN values; separate observed counts; no imputation',
          'date_repair_scope':'IoT_normal_fridge_3; only 0?4 Apr 201; validate original GMT dates and every measurement',
          'clock_offsets_applied':[],'capture_session_gap_seconds':60,
          'capture_scope':'per-file chronology only; no network feature reconstruction or pooling',
          'incomplete_capture_policy':'Classic PCAP incomplete EOF: retain complete-record prefix for diagnostics; exclude incomplete record; do not certify capture completeness. Other decoding errors: export and exclude that file; continue others.',
          'scientific_claim':'source-supported timestamp repair; not recovery of the lost script',
          'historical_input_sha256':HISTORICAL_HASHES,'engine_sha256':ENGINE_SHA256})
        print('Output folder:',self.out,flush=True)

    def note(self,name,status,detail):self.checks.append({'check':name,'status':status,'detail':str(detail)})
    def save(self,name,frame):
        frame=pd.DataFrame(frame);frame.to_csv(self.table_dir/(name+'.csv'),index=False);return frame
    def phase(self,name,fn):
        print(name+' ...',flush=True);start=time.perf_counter()
        try:r=fn()
        except Exception as exc:
            self.note(name,'FAIL',repr(exc));json_write(self.out/'execution_error.json',{'phase':name,'error':repr(exc),'traceback':traceback.format_exc()})
            self.finalise();raise
        print(f'{name}: complete ({time.perf_counter()-start:.1f} seconds)',flush=True);return r

    def locate(self):
        explicit=self.config.get('telemetry_input');root=Path(self.config['input_root']).expanduser()
        if explicit:path=Path(explicit).expanduser()
        else:
            candidates=[]
            for parent in [root,Path.cwd(),root/'TIOT_EXTERNAL_VALIDATION'/'TON_IoT']:
                if not parent.is_dir():continue
                candidates.extend(p for p in parent.glob('TON_IOT_IOT_DATA*.zip') if p.is_file())
                candidates.extend(p.parent for p in parent.glob('*/IoT_filtered_normal') if p.is_dir())
                if (parent/'IoT_filtered_normal').is_dir():candidates.append(parent)
            candidates=list(dict.fromkeys(p.resolve() for p in candidates))
            if not candidates:raise FileNotFoundError(f'No telemetry dataset found under {root}. Set TELEMETRY_INPUT to the ZIP or folder containing both IoT normal folders.')
            # Prefer the exact supplied ZIP. Distinct copies are not silently concatenated.
            exact=[p for p in candidates if p.name=='TON_IOT_IOT_DATA.zip']
            if len(exact)==1:path=exact[0]
            elif len(candidates)==1:path=candidates[0]
            else:raise ValueError('Multiple datasets found; set TELEMETRY_INPUT explicitly: '+str(candidates))
        self.source=TelemetrySource(path)
        self.note('input_42_members','PASS','Located all 21 filtered CSVs and 21 original logs in '+str(path))
        if path.is_file():self.inventory.append({'role':'telemetry_archive','file':str(path),'bytes':path.stat().st_size,'sha256':file_hash(path)})
        return pd.DataFrame({'selected_input':[str(self.source.path)],'members':[len(self.source.members)]})

    def telemetry(self):
        all_bins=[];date_formats=[];channel_records=[];source_spans=[]
        for fam in FAMILIES:
            family=[]
            for part in (1,2,3):
                stem=f'IoT_normal_{fam}_{part}';raw=self.source.read(stem+'.csv');orig=self.source.read(stem+'.log')
                for ext,b in [('csv',raw),('log',orig)]:self.inventory.append({'role':'filtered' if ext=='csv' else 'original','file':stem+'.'+ext,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
                d=pd.read_csv(io.BytesIO(raw),dtype=str,keep_default_na=False)
                invalid_original_lines=0
                if orig.lstrip().startswith((b'{',b'[')):
                    try:o=pd.read_json(io.BytesIO(orig),lines=True,convert_dates=False)
                    except ValueError:
                        # A known upstream Modbus log contains a NUL-corrupted line.
                        # Retain its line position as missing and expose its hash; never shift rows.
                        if fam!='modbus':raise
                        records=[]
                        for lineno,line in enumerate(orig.splitlines(),1):
                            try:
                                obj=json.loads(line)
                                if not isinstance(obj,list) or len(obj)!=4:raise ValueError('Expected four registers')
                                records.append(obj)
                            except (ValueError,UnicodeError) as exc:
                                invalid_original_lines+=1;records.append([None]*4)
                                self.original_errors.append({'file':stem+'.log','line_1based':lineno,
                                    'bytes':len(line),'nul_bytes':line.count(b'\x00'),
                                    'line_sha256':hashlib.sha256(line).hexdigest(),'error':str(exc)})
                        o=pd.DataFrame(records)
                        self.note(stem+'_malformed_original','LIMITATION',f'{invalid_original_lines} malformed original log line(s) retained as missing at their original positions. Filtered values are not changed.')
                else:o=pd.read_csv(io.BytesIO(orig),sep='\t',dtype=str,keep_default_na=False)
                if d.shape[1]!=len(SCHEMA[fam])+2:raise ValueError('Unexpected filtered schema: '+stem)
                vals=pd.DataFrame();exact=True;rounding_match=True
                for j,(feature,key,kind) in enumerate(SCHEMA[fam]):
                    name='iot__'+SLUG.get(fam,fam)+'__'+feature
                    vals[name]=numeric_channel(d.iloc[:,j+2],kind)
                    source_missing=d.iloc[:,j+2].astype(str).str.strip().eq('')
                    if (vals[name].isna() & ~source_missing).any() or np.isinf(vals[name]).any():
                        raise ValueError('Unknown value/token in '+stem+' column '+str(j+2))
                    original_key=key
                    if fam=='Motion_Light' and part==1:original_key=o.columns[j+2]
                    a=vals[name].to_numpy();b=numeric_channel(o[original_key],kind).to_numpy()
                    same_n=len(a)==len(b);eq=int(np.sum(a==b)) if same_n else None
                    close=written_precision_match(d.iloc[:,j+2],a,b,kind) if same_n else None
                    exact &= same_n and eq==len(a)
                    rounding_match &= same_n and bool(close.all())
                    channel_records.append({'file':stem,'feature':name,'csv_rows':len(a),'log_rows':len(b),
                      'missing_filtered_values':int(source_missing.sum()),
                      'exact_equal_rows':eq,'within_rounding_tolerance_rows':int(close.sum()) if same_n else None,
                      'max_absolute_difference':float(np.nanmax(np.abs(a-b))) if same_n and (np.isfinite(a)&np.isfinite(b)).any() else None})
                before=strict_csv_time(d);after=before.copy();tc=next((c for c in o if str(c).lower()=='timestamp'),None)
                ot=None
                if tc:
                    # GMT is explicit; reject any other suffix rather than reinterpret local clock time.
                    ot=pd.to_datetime(o[tc],format='%a, %d %b %Y %H:%M:%S GMT',utc=True,errors='coerce')
                    if ot.isna().any():raise ValueError('Unparseable original GMT timestamp in '+stem)
                elif fam=='Motion_Light' and part==1:
                    ot=strict_csv_time(o)
                    if ot.isna().any():raise ValueError('Unparseable original tabular clock in '+stem)
                repair_mask=pd.Series(False,index=d.index)
                if fam=='fridge' and part==3:
                    repair_mask=d.iloc[:,0].str.strip().str.fullmatch(r'0?4 Apr 201')
                    if not exact or ot is None or len(ot)!=len(d):raise ValueError('Fridge repair requires all measurements to match row for row')
                    if not (ot.loc[repair_mask].dt.strftime('%Y-%m-%d')=='2019-04-04').all():raise ValueError('Original log does not support the proposed date repair')
                    clock=d.iloc[:,1].str.strip()
                    if not (clock.loc[repair_mask]==ot.loc[repair_mask].dt.strftime('%H:%M:%S')).all():raise ValueError('Fridge clock values differ')
                    repaired=d.copy();repaired.loc[repair_mask,d.columns[0]]='04 Apr 2019';after=strict_csv_time(repaired)
                    if not after.equals(ot):raise ValueError('Repaired fridge times do not match every original timestamp')
                    rr=pd.DataFrame({'file':stem+'.csv','data_row_1based':np.flatnonzero(repair_mask)+1,
                       'csv_line_1based':np.flatnonzero(repair_mask)+2,'original_log_line_1based':np.flatnonzero(repair_mask)+1,
                       'date_before':d.loc[repair_mask].iloc[:,0].to_numpy(),'date_after':'04 Apr 2019',
                       'time_unchanged':d.loc[repair_mask].iloc[:,1].to_numpy(),'original_timestamp':o.loc[repair_mask,tc].to_numpy(),
                       'temperature_unchanged':d.loc[repair_mask].iloc[:,2].to_numpy(),
                       'condition_unchanged':d.loc[repair_mask].iloc[:,3].to_numpy()})
                    rr.to_csv(self.table_dir/'fridge_date_repair_all_rows.csv.gz',index=False,compression={'method':'gzip','mtime':0})
                    self.repairs.extend(rr.head(12).to_dict('records'));self.repair_count=len(rr)
                    repaired.to_csv(self.data_dir/(stem+'_repaired.csv.gz'),index=False,compression={'method':'gzip','mtime':0})
                    self.note('fridge_repair','PASS',f'{len(rr):,} truncated-year cells replaced from original GMT dates; all {len(d):,} row timestamps match; all measurement values preserved.')
                bad=int(after.isna().sum())
                if bad:raise ValueError(f'{stem}: {bad} invalid timestamps remain; no general heuristic repair is permitted')
                mismatch=int((after!=ot).sum()) if ot is not None and len(ot)==len(d) else None
                if mismatch is not None and mismatch:raise ValueError(f'{stem}: {mismatch} original/filtered timestamp disagreements')
                timestamp_basis='Original GMT log; row correspondence verified' if tc and rounding_match else 'Filtered clock only; UTC coordinate convention is not independent clock validation'
                if fam=='Motion_Light' and part==1:
                    timestamp_basis='Original tabular clock agrees row for row; timezone is unstated'
                if ot is not None and not rounding_match:raise ValueError(stem+': timestamp comparison lacks measurement correspondence')
                if not tc:self.note(stem+'_timestamp_basis','LIMITATION',timestamp_basis)
                if len(d)!=len(o):self.note(stem+'_row_alignment','LIMITATION',f'Filtered rows {len(d):,}; original rows {len(o):,}. No positional timestamp transfer is attempted.')
                for date,n in d.iloc[:,0].str.strip().value_counts().items():date_formats.append({'file':stem,'date_token':date,'rows':int(n)})
                for feature in vals:
                    vals[feature]=vals[feature].astype(float)
                dup_ts=int(after.duplicated().sum());dup_rows=int(pd.concat([after.rename('time'),vals],axis=1).duplicated().sum())
                row={'file':stem,'family':fam,'part':part,'filtered_rows':len(d),'original_rows':len(o),
                     'malformed_original_lines':invalid_original_lines,
                     'exact_measurement_match':exact,'match_within_declared_rounding':rounding_match,
                     'timestamp_basis':timestamp_basis,'invalid_before':int(before.isna().sum()),'repaired_rows':int(repair_mask.sum()),
                     'invalid_after':bad,'original_timestamp_disagreements_after':mismatch,
                     'duplicate_timestamp_rows':dup_ts,'duplicate_time_and_value_rows':dup_rows,
                     'backward_timestamp_steps':int((after.diff().dt.total_seconds()<0).sum()),
                     'first_utc_coordinate':str(after.min()),'last_utc_coordinate':str(after.max())}
                self.pairs.append(row)
                vals.insert(0,'timestamp_utc_coordinate',after);vals.insert(1,'source_file',stem+'.csv')
                vals.insert(2,'source_data_row_1based',np.arange(1,len(vals)+1))
                vals.to_csv(self.data_dir/(stem+'_normalised.csv.gz'),index=False,compression={'method':'gzip','mtime':0})
                family.append(vals)
                print(f'{stem}: {len(d):,} records; {int(repair_mask.sum()):,} date repairs',flush=True)
            f=pd.concat(family,ignore_index=True);valuecols=[c for c in f if c.startswith('iot__')]
            bucket=f['timestamp_utc_coordinate'].dt.floor('5s');group=f[valuecols].groupby(bucket,sort=True)
            means=group.mean();counts=group.count().add_suffix('__observed_count')
            agg=pd.concat([means,counts],axis=1);all_bins.append(agg)
            source_spans.append({'family':fam,'records':len(f),'occupied_5s_bins':len(agg),
               'duplicate_time_value_rows_across_parts':int(f.drop(columns=['source_file','source_data_row_1based']).duplicated().sum()),
               'first_utc_coordinate':str(agg.index.min()),'last_utc_coordinate':str(agg.index.max())})
        self.source.close()
        self.bins=pd.concat(all_bins,axis=1).sort_index();self.bins.index.name='timestamp_utc_coordinate'
        countcols=[c for c in self.bins if c.endswith('__observed_count')]
        self.bins[countcols]=self.bins[countcols].fillna(0).astype('int64')
        self.bins.to_csv(self.data_dir/'telemetry_5s_preimputation.csv.gz',compression={'method':'gzip','mtime':0})
        self.save('telemetry_pairs',self.pairs);self.save('measurement_correspondence',channel_records)
        self.save('malformed_original_lines',self.original_errors)
        self.save('source_date_tokens',date_formats);self.save('telemetry_families',source_spans)
        self.note('aggregation','PASS','UTC-epoch-aligned [t,t+5s) arithmetic means/fractions; duplicate rows retained. Unobserved values stay NaN; no interpolation, fill or gap compression.')
        self.note('replacement_scope','LIMITATION','This is a telemetry reconstruction and timestamp audit, not the 169-column historical multimodal canonical table. Network feature reconstruction is not claimed.')
        return pd.DataFrame(self.pairs)

    def inspect_notebook(self):
        path=self.config.get('reference_notebook')
        if not path:
            found=[]
            for root in [Path(self.config['input_root']),Path.cwd()]:found+=list(root.glob('TON_IoT_ACM_TIoT_FULL_Benchmark_v2_2_RedTeam*.ipynb')) if root.is_dir() else []
            found=list(dict.fromkeys(p.resolve() for p in found));path=found[0] if len(found)==1 else None
        if not path or not Path(path).is_file():
            self.note('reference_notebook','NOT_RUN','Optional v2.2 notebook not found; preparation can continue.');return pd.DataFrame()
        path=Path(path);nb=json.loads(path.read_text());rows=[]
        for i,c in enumerate(nb.get('cells',[])):
            if c.get('cell_type')!='code':continue
            outputs=c.get('outputs',[])
            rows.append({'cell_index_0based':i,'execution_count':c.get('execution_count'),
               'output_count':len(outputs),'saved_errors':sum(o.get('output_type')=='error' for o in outputs),
               'source_sha256':hashlib.sha256(''.join(c.get('source',[])).encode()).hexdigest()})
        self.inventory.append({'role':'reference_notebook','file':str(path),'bytes':path.stat().st_size,'sha256':file_hash(path)})
        self.note('reference_notebook_is_not_preparation','INFO','v2.2 loads canonical_v5 and a frozen protocol; it does not recover the lost raw-to-canonical code. Saved execution metadata are evidence of a prior run, not a rerun here. Unexecuted appended checks do not establish scientific validity.')
        return self.save('reference_notebook_cells',rows)

    def historical_tables(self):
        roots=[Path(self.config['project_root'])];rows=[]
        for role in HISTORICAL_HASHES:
            explicit=self.config.get(role)
            if explicit:candidates=[Path(explicit)]
            else:
                candidates=[p for p in bounded_files(roots[0],4,{'.parquet'}) if
                  ('canonical' in p.name.lower() if role=='canonical' else 'preimput' in p.name.lower() or 'pre_imput' in p.name.lower())]
            matches=[]
            for p in candidates:
                if not p.is_file():continue
                digest=file_hash(p);hit=digest==HISTORICAL_HASHES[role]
                rows.append({'role':role,'file':str(p),'sha256':digest,'expected_sha256':HISTORICAL_HASHES[role],'matches_recorded_input':hit})
                if hit:matches.append(p)
            if len(matches)>0:
                self.historical[role]=matches[0];self.note(role+'_hash','PASS','Found byte-identical historical input: '+str(matches[0]))
            else:self.note(role+'_hash','NOT_RUN','Historical input not located by expected SHA-256. Set its optional path if stored outside PROJECT_ROOT.')
        self.save('historical_input_hashes',rows)
        comparisons=[]
        if 'preimputation' in self.historical:
            try:old=pd.read_parquet(self.historical['preimputation'])
            except ImportError:
                self.note('historical_value_comparison','NOT_RUN','A Parquet engine is required (pyarrow); hashes were still checked.');return pd.DataFrame(rows)
            tc='timestamp_utc_coordinate'
            if tc not in old:raise ValueError('Historical table lacks its recorded timestamp column')
            tt=pd.to_datetime(old[tc],utc=True,errors='raise')
            if tt.duplicated().any():raise ValueError('Historical timestamp column is not unique')
            old=old.copy();old.index=tt
            intersection=old.index.intersection(self.bins.index)
            for c in [c for c in self.bins if not c.endswith('__observed_count') and c in old]:
                a=pd.to_numeric(old.loc[intersection,c],errors='coerce').to_numpy();b=self.bins.loc[intersection,c].to_numpy()
                observed_a=np.isfinite(a);observed_b=np.isfinite(b);joint=observed_a&observed_b
                close=np.isclose(a[joint],b[joint],rtol=1e-6,atol=1e-6)
                comparisons.append({'feature':c,'historical_rows':len(old),'matching_timestamp_rows':len(intersection),
                    'both_observed':int(joint.sum()),'availability_disagreements':int((observed_a!=observed_b).sum()),
                    'value_disagreements_at_1e_6':int((~close).sum()),
                    'max_absolute_difference':float(np.max(np.abs(a[joint]-b[joint]))) if joint.any() else None})
            self.save('historical_telemetry_comparison',comparisons)
            self.note('historical_comparison_scope','INFO','Compared the exact recorded pre-imputation input at literal timestamp coordinates; no offset was fitted. Numerical agreement is not recovery of the old script or proof of network clock synchronisation.')
        return pd.DataFrame(rows)

    def captures(self):
        explicit=self.config.get('pcap_files') or []
        if explicit:paths=[Path(p).expanduser().resolve() for p in explicit]
        else:
            root=self.config.get('pcap_root') or self.config['project_root']
            paths=bounded_files(root,5,{'.pcap','.pcapng','.cap'})
        paths=sorted(set(paths))
        if not paths:
            self.note('pcap_inputs','NOT_RUN','No captures found. Keep PCAPs on Falcon; set PCAP_ROOT to their folder and rerun. Telemetry outputs remain usable.');return pd.DataFrame()
        self.note('pcap_file_scope','INFO',f'{len(paths)} captures found under the explicitly selected project/capture root; filename labels are not independently verified normal-operation labels. Files are never pooled into a traffic-feature stream.')
        table=[];self.capture_errors=[]
        self.capture_expected_files=len(paths)
        bin_export=self.out/'capture_bins';bin_export.mkdir(exist_ok=True)
        for p in paths:
            print('Checking capture:',p,flush=True)
            if not p.is_file():raise FileNotFoundError(p)
            key=hashlib.sha256(str(p).encode()).hexdigest()[:24];cache=self.cache/(key+'.json');bfile=self.cache/(key+'.csv.gz')
            meta=None;cached=False
            if cache.is_file() and bfile.is_file():
                previous=json.loads(cache.read_text())
                if (previous.get('engine_sha256')==ENGINE_SHA256 or
                    (previous.get('engine_sha256') in COMPATIBLE_COMPLETE_CACHE_SHA256 and
                     previous.get('integrity_status','COMPLETE_RECORD_STREAM')=='COMPLETE_RECORD_STREAM')) and previous.get('bytes')==p.stat().st_size:
                    print('Verifying cached capture hash:',p.name,flush=True)
                    if file_hash(p)==previous['sha256'] and file_hash(bfile)==previous.get('bin_sha256'):
                        meta=previous;bins=pd.read_csv(bfile).values.tolist();cached=True
            if meta is None:
                before=p.stat()
                try:
                    meta,bins=capture_summary(p,progress=lambda s:print(s,flush=True))
                except (ValueError,OSError) as exc:
                    error={'file':str(p),'error':str(exc),'integrity_status':'DECODE_ERROR',
                           'bytes':p.stat().st_size,'sha256':file_hash(p)}
                    self.capture_errors.append(error)
                    self.inventory.append({'role':'capture_decode_error','file':str(p),'bytes':error['bytes'],'sha256':error['sha256']})
                    self.note(str(p)+'_decode_error','CAPTURE_INCOMPLETE',str(exc)+'; excluded from overlap statistics; remaining files continue.')
                    self.save('capture_errors',self.capture_errors)
                    self.save('input_inventory',self.inventory)
                    print('DECODE_ERROR:',p.name,str(exc),flush=True)
                    continue
                after=p.stat()
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('Capture changed while being read: '+str(p))
                pd.DataFrame(bins,columns=['bin_5s_epoch','packets','first_ns','last_ns']).to_csv(bfile,index=False,compression={'method':'gzip','mtime':0})
                meta.update(engine_sha256=ENGINE_SHA256,bin_sha256=file_hash(bfile));json_write(cache,meta)
            meta.setdefault('integrity_status','COMPLETE_RECORD_STREAM')
            meta.setdefault('incomplete_record',None)
            if meta['integrity_status']!='COMPLETE_RECORD_STREAM':
                self.note(str(p)+'_incomplete','CAPTURE_INCOMPLETE',json.dumps(meta['incomplete_record'])+' Only complete records are used diagnostically; no bytes are repaired or written to the input.')
            self.capture_meta.append(meta)
            occupied=np.array([int(b[0]) for b in bins],dtype=np.int64);self.capture_bins[str(p)]=occupied
            record={k:v for k,v in meta.items() if k not in {'sessions_ns','interfaces'}};record['cache_verified_and_reused']=cached
            record['first_utc']=str(pd.to_datetime(meta['first_ns'],unit='ns',utc=True)) if meta['first_ns'] is not None else None
            record['last_utc']=str(pd.to_datetime(meta['last_ns'],unit='ns',utc=True)) if meta['last_ns'] is not None else None
            record['occupied_5s_bins']=len(bins);record['sessions_at_60s_gap']=len(meta['sessions_ns']);table.append(record)
            self.inventory.append({'role':'capture','file':str(p),'bytes':meta['bytes'],'sha256':meta['sha256']})
            if meta['untimestamped_packets']:self.note(p.name+'_untimestamped','LIMITATION',str(meta['untimestamped_packets'])+' packets have no timestamps; overlap coverage is incomplete.')
            if meta['backward_steps']:self.note(p.name+'_out_of_order','INFO',str(meta['backward_steps'])+' backwards steps retained; interval summaries use sorted bins.')
            pd.DataFrame(bins,columns=['bin_5s_epoch','packets','first_ns','last_ns']).to_csv(
                bin_export/(key+'.csv.gz'),index=False,compression={'method':'gzip','mtime':0})
            record['bin_evidence_file']='capture_bins/'+key+'.csv.gz'
            json_write(self.out/'capture_metadata.json',self.capture_meta)
            self.save('capture_inventory',table);self.save('input_inventory',self.inventory)
            self.save('audit_checks',self.checks)
            print(f'{p.name}: {meta["packets"]:,} complete timestamped packets; {len(bins):,} occupied bins; {meta["integrity_status"]}',flush=True)
        json_write(self.out/'capture_metadata.json',self.capture_meta)
        self.save('capture_inventory',table)
        # Clock-offset sensitivity is descriptive only. It must never choose the canonical clock.
        rows=[];occupied_telemetry={}
        for fam in FAMILIES:
            cols=[c for c in self.bins if c.startswith('iot__'+SLUG.get(fam,fam)+'__') and c.endswith('__observed_count')]
            mask=(self.bins[cols]>0).any(axis=1);idx=self.bins.index[mask].as_unit('ns').asi8//5_000_000_000;occupied_telemetry[fam]=idx
            for p,pc in self.capture_bins.items():
                for hours in (0,-12,-11,-10,-1,1,10,11,12):
                    count=int(np.isin(idx+hours*720,pc).sum())
                    rows.append({'family':fam,'capture':p,'telemetry_offset_hours_diagnostic_only':hours,
                      'capture_integrity_status':next(m['integrity_status'] for m in self.capture_meta if m['file']==p),
                      'interpretation':'diagnostic overlap; incomplete streams are not complete acquisition',
                      'telemetry_occupied_bins':len(idx),'jointly_occupied_bins':count,
                      'telemetry_bin_overlap_fraction':count/len(idx) if len(idx) else None})
        self.save('clock_overlap_sensitivity',rows)
        self.note('clock_sensitivity','LIMITATION','Overlap is a diagnostic of recorded clock coordinates, not proof of clock synchronisation. No offset is selected or applied. Packet-empty bins are not labelled as measured zero traffic.')
        self.note('network_feature_rebuild','NOT_RUN','Packet timestamps and capture hashes were audited. Historical protocol features, source-tier membership and acquisition masks are not recreated by this notebook.')
        return pd.DataFrame(table)

    def figures(self):
        if self.bins is None:return
        try:import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
        except ImportError:
            self.note('figure','NOT_RUN','Optional matplotlib is unavailable. All numerical tables are still saved.');return
        hourly=[]
        for fam in FAMILIES:
            cols=[c for c in self.bins if c.startswith('iot__'+SLUG.get(fam,fam)+'__') and c.endswith('__observed_count')]
            v=(self.bins[cols]>0).any(axis=1).astype(int).resample('1h').sum()/720
            hourly.append(v.rename(fam))
        density=pd.concat(hourly,axis=1).fillna(0);density.to_csv(self.table_dir/'hourly_observed_bin_fraction.csv')
        fig,ax=plt.subplots(figsize=(11,4));im=ax.imshow(density.T,aspect='auto',vmin=0,vmax=1,cmap='Blues',interpolation='none')
        ax.set_yticks(np.arange(len(FAMILIES)),FAMILIES);ticks=np.linspace(0,len(density)-1,7).astype(int)
        ax.set_xticks(ticks,[density.index[i].strftime('%d %b\n%H:%M') for i in ticks]);ax.set_xlabel('Recorded UTC coordinate (2019)')
        ax.set_title('Telemetry: fraction of five-second bins containing observations')
        fig.colorbar(im,ax=ax,label='Observed bin fraction');fig.tight_layout()
        for ext in ('png','pdf'):fig.savefig(self.out/('telemetry_coverage.'+ext),dpi=180)
        plt.close(fig)

    def finalise(self):
        self.save('audit_checks',self.checks);self.save('input_inventory',self.inventory)
        failures=sum(x['status']=='FAIL' for x in self.checks)
        capture_issues=sum(x['status']=='CAPTURE_INCOMPLETE' for x in self.checks)
        status={'run_id':self.run_id,'version':VERSION,'execution_status':'FAILED' if failures else ('COMPLETED_WITH_CAPTURE_ISSUES' if capture_issues else 'COMPLETED'),
          'capture_integrity_status':'INCOMPLETE' if capture_issues else ('COMPLETE_RECORD_STREAMS_ONLY' if self.capture_meta else 'NOT_RUN'),
          'capture_issue_count':capture_issues,
          'capture_files_expected':getattr(self,'capture_expected_files',0),
          'capture_files_decode_error':len(getattr(self,'capture_errors',[])),
          'scientific_status':'SOURCE_TIMESTAMP_REPAIR_SUPPORTED' if getattr(self,'repair_count',0)>0 and not failures else 'INCOMPLETE',
          'fridge_dates_repaired':getattr(self,'repair_count',0),'telemetry_pairs_audited':len(self.pairs),
          'timestamped_pcap_files_audited':len(self.capture_meta),'historical_input_hash_matches':sorted(self.historical),
          'model_fits':0,'historical_raw_to_canonical_reproduction':'NOT_ESTABLISHED',
          'elapsed_seconds':round(time.perf_counter()-self.start,3),'check_counts':dict(collections.Counter(x['status'] for x in self.checks))}
        json_write(self.out/'RECOVERY_STATUS.json',status)
        md=f'''# TON_IoT timestamp recovery — executed findings\n\nRun: {self.run_id}; implementation {VERSION}.\n\n**Execution: {status['execution_status']}. Scientific status: {status['scientific_status']}.**\n\nThis new reconstruction repairs {status['fridge_dates_repaired']:,} truncated-year cells using row-aligned original GMT records. It does not claim to recover the lost historical script. Filtered measurement values, row multiplicity and clock times are preserved.\n\nThe original and filtered folders are not interchangeable. Some original logs lack timestamps; row counts can differ. Those series retain filtered clock coordinates, with the assumption recorded explicitly. Floating-point differences caused by CSV rounding are diagnosed, not silently substituted.\n\n{len(self.pairs)} file pairs were audited. {len(self.capture_meta)} capture files were scanned here. No model fitting was performed. The recovered telemetry table contains measured values and counts in UTC-epoch-aligned, left-closed five-second bins; unobserved values remain missing. Exact duplicate rows are retained, so observation counts must not be interpreted as independent event counts.\n\n## Capture integrity\n\nCapture integrity: **{status['capture_integrity_status']}**. Issue count: {capture_issues}. An incomplete classic-PCAP final record is excluded; its complete-record prefix is retained only for descriptive timestamp diagnostics. The parser does not invent missing bytes or infer how many later records are absent. Other decode failures are exported and excluded, and remaining files continue. A complete record stream does not prove capture completeness or absence of dropped packets.\n\n## Evidence and next action\n\n- `tables/fridge_date_repair_all_rows.csv.gz`: every changed row, old/new date, original timestamp and unchanged measurements.\n- `tables/telemetry_pairs.csv` and `measurement_correspondence.csv`: row counts, correspondence, chronology and limits.\n- `prepared_telemetry/`: normalised records, corrected fridge CSV and pre-imputation telemetry aggregates. These are newly documented derivatives, not the old 169-column canonical table.\n- `tables/historical_input_hashes.csv`: whether local files match the exact inputs of the recorded external evaluation. If the pre-imputation table is found, literal-coordinate telemetry comparisons are also exported.\n- `tables/capture_inventory.csv` and `clock_overlap_sensitivity.csv` appear only when captures are available. Occupied-bin overlap cannot establish physical synchronisation, normal labels, or acquisition completeness. No offset is fitted or applied. General and IoT-named capture streams are never pooled.\n\nFull raw-to-canonical reproduction is **not established** by a successful timestamp audit. If the exact prepared inputs still exist, preserve them and compare this source-supported repair against them before changing results. If prepared data, observation masks, bin origin or network features change, all affected external task admission, P0 calibration/qualification, generator outputs, predictions, utility summaries and reported conclusions must be recomputed under a new input/protocol identity. Residential results have no dependency on this fridge correction.\n\nThe supplied v2.2 notebook loads a pre-existing canonical dataset and is not a preparation notebook. Its appended collection gates cannot replace protocol-bound scientific checks. Run this recovery notebook first; do not rerun that older full benchmark to validate a date repair.\n\n## Methods and sources\n\nThe date replacement is strictly scoped to `IoT_normal_fridge_3.csv`: after trimming whitespace, `04 Apr 201` or `4 Apr 201` becomes `04 Apr 2019`, only after matching every original fridge measurement and checking each affected original GMT date and unchanged clock value. Every unmodified timestamp must also agree. Other malformed dates fail explicitly.\n\nNumeric correspondence checks half of the last decimal unit written in each CSV token, plus eight machine epsilons scaled by the original magnitude for floating-point conversion. This handles both fixed-decimal and scientific notation. Boolean/state channels require exact equality. The fridge repair requires exact measurement equality, not the rounding tolerance. Optional historical aggregate comparisons use rtol=1e-6 and atol=1e-6 to accommodate stored precision, and expose maximum absolute errors and mask disagreements. None of these numerical tolerances establishes a scientific equivalence margin.\n\nSources: [UNSW TON_IoT dataset description](https://research.unsw.edu.au/projects/toniot-datasets), [PCAP format, work-in-progress specification](https://www.ietf.org/archive/id/draft-ietf-opsawg-pcap-05.html), [PCAPNG format, work-in-progress specification](https://www.ietf.org/archive/id/draft-ietf-opsawg-pcapng-05.html).\n\n## Checks\n\n'''
        md+='\n'.join(f'- **{x["status"]}** — {x["check"]}: {x["detail"]}' for x in self.checks)+'\n'
        (self.out/'FINDINGS.md').write_text(md, encoding='utf-8')
        # Standalone HTML: no scripting or remote assets.
        body='<h1>TON_IoT timestamp recovery</h1><p class="change">'+html.escape(status['scientific_status'])+'</p>'
        body+='<pre>'+html.escape(md)+'</pre>'
        if self.pairs:body+='<h2>Telemetry pairs</h2>'+pd.DataFrame(self.pairs).to_html(index=False,escape=True)
        if (self.out/'telemetry_coverage.png').exists():
            import base64
            body+='<img alt="Observed telemetry coverage" src="data:image/png;base64,'+base64.b64encode((self.out/'telemetry_coverage.png').read_bytes()).decode()+'">'
        (self.out/'FINDINGS.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>TON_IoT timestamp recovery</title><style>body{font:16px/1.5 system-ui;margin:2em;max-width:1300px;color:#153c80}pre{white-space:pre-wrap;font:inherit}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccd;padding:5px}img{max-width:100%}</style>'+body+'</html>', encoding='utf-8')
        # Share only bounded evidence. Large raw inputs, captures and normalised records stay local.
        share_files=[p for p in self.out.rglob('*') if p.is_file() and 'prepared_telemetry' not in p.parts
                     and p.suffix!='.zip' and p.name!='OUTPUT_MANIFEST.csv']
        manifest=[{'file':p.relative_to(self.out).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in sorted(share_files)]
        pd.DataFrame(manifest).to_csv(self.out/'OUTPUT_MANIFEST.csv',index=False)
        target=self.out/'TON_IOT_RECOVERY_RESULTS_TO_SHARE.zip'
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
            for p in share_files+[self.out/'OUTPUT_MANIFEST.csv']:z.write(p,p.relative_to(self.out).as_posix())
        json_write(self.out.parent/'LATEST_RUN.json',{'run_id':self.run_id,'output_dir':str(self.out),'results_zip':str(target)})
        print(json.dumps(status,indent=2),flush=True);print('Send this file back:',target,flush=True)
        return status
