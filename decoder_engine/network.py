"""Explicit packet-header features; bounded memory and content-bound file caches.

No payload classification, flow reconstruction, packet deduplication, timestamp
offset fitting, or presumed device identity. See docs/FEATURE_DICTIONARY.md.
"""
from __future__ import annotations
import array, collections, gzip, hashlib, json, struct, time
from pathlib import Path
import numpy as np
import pandas as pd
from .capture_reader import capture_summary
from .telemetry_recovery import file_hash, json_write

COUNTERS = ['ipv4_count','ipv6_count','arp_count','tcp_count','udp_count','icmp_count',
            'tcp_syn_count','tcp_fin_count','tcp_rst_count','http_port_packets',
            'https_port_packets','dns_port_packets','mqtt_port_packets']
PORTS = {'http_port_packets':{80},'https_port_packets':{443},
         'dns_port_packets':{53},'mqtt_port_packets':{1883,8883}}
SUPPORTED_LINKTYPES = {1,101,113,228,229,276}

class HeaderError(ValueError): pass

def decode_headers(data, linktype):
    """Return outer-network counters, IP addresses, and diagnostic counters.

    Transport identification uses the outer IP protocol/next-header chain.
    Noninitial fragments have no interpreted transport ports or TCP flags.
    """
    if linktype not in SUPPORTED_LINKTYPES:
        raise RuntimeError(f'Unsupported link type {linktype}; no silent partial decode is allowed.')
    d=memoryview(data);n=len(d);counts=collections.Counter();src=dst=None
    def need(p,k):
        if p+k>n:raise HeaderError('Truncated packet header')
    if linktype==1:
        need(0,14);typ=struct.unpack_from('!H',d,12)[0];p=14
        for _ in range(4):
            if typ not in (0x8100,0x88a8,0x9100):break
            need(p,4);typ=struct.unpack_from('!H',d,p+2)[0];p+=4
        if typ in (0x8100,0x88a8,0x9100):raise HeaderError('More than four VLAN headers')
        if typ<=1500:
            need(p,3)
            if bytes(d[p:p+3])==b'\xaa\xaa\x03':
                need(p,8)
                if bytes(d[p+3:p+6])==b'\0\0\0':typ=struct.unpack_from('!H',d,p+6)[0];p+=8
    elif linktype==113:
        need(0,16);typ=struct.unpack_from('!H',d,14)[0];p=16
    elif linktype==276:
        need(0,20);typ=struct.unpack_from('!H',d,0)[0];p=20
    else:
        need(0,1);p=0;version=d[0]>>4
        typ=0x800 if version==4 else (0x86dd if version==6 else 0)
        if linktype in (228,229) and version!={228:4,229:6}[linktype]:raise HeaderError('Raw IP version/link mismatch')
        if typ==0:raise HeaderError('Invalid raw IP version')
    if linktype in (113,276):
        for _ in range(4):
            if typ not in (0x8100,0x88a8,0x9100):break
            need(p,4);typ=struct.unpack_from('!H',d,p+2)[0];p+=4
        if typ in (0x8100,0x88a8,0x9100):raise HeaderError('More than four VLAN headers')
    if typ==0x806:counts['arp_count']=1;return counts,src,dst
    if typ not in (0x800,0x86dd):counts['_other_network_protocol']=1;return counts,src,dst
    fragmented=False
    if typ==0x800:
        need(p,20);ihl=(d[p]&15)*4
        if d[p]>>4!=4 or ihl<20:raise HeaderError('Invalid IPv4 header')
        need(p,ihl);total=struct.unpack_from('!H',d,p+2)[0]
        if total<ihl:raise HeaderError('IPv4 total length below header length')
        n=min(n,p+total);proto=d[p+9];frag=struct.unpack_from('!H',d,p+6)[0]
        fragmented=bool(frag&0x1fff);counts['_ip_fragments']=int(bool(frag&0x3fff))
        src=bytes(d[p+12:p+16]);dst=bytes(d[p+16:p+20]);p+=ihl;counts['ipv4_count']=1
    else:
        need(p,40)
        if d[p]>>4!=6:raise HeaderError('Invalid IPv6 header')
        plen=struct.unpack_from('!H',d,p+4)[0];proto=d[p+6]
        src=bytes(d[p+8:p+24]);dst=bytes(d[p+24:p+40]);p+=40
        if plen:n=min(n,p+plen)
        else:counts['_ipv6_zero_payload_length']=1
        counts['ipv6_count']=1
        for _ in range(16):
            if proto not in (0,43,44,51,60):break
            need(p,2);nxt=d[p]
            if proto==44:
                need(p,8);fragmented=bool(struct.unpack_from('!H',d,p+2)[0]&0xfff8)
                counts['_ip_fragments']=1;size=8
            elif proto==51:size=(d[p+1]+2)*4
            else:size=(d[p+1]+1)*8
            need(p,size);p+=size;proto=nxt
            if fragmented:break
        else:raise HeaderError('IPv6 extension chain exceeds 16 headers')
    if proto==6:counts['tcp_count']=1
    elif proto==17:counts['udp_count']=1
    elif proto in (1,58):counts['icmp_count']=1
    if fragmented or proto not in (6,17):return counts,src,dst
    need(p,20 if proto==6 else 8)
    sport,dport=struct.unpack_from('!HH',d,p)
    if proto==6:
        size=(d[p+12]>>4)*4
        if size<20:raise HeaderError('Invalid TCP data offset')
        need(p,size);flags=d[p+13]
        for name,flag in [('tcp_syn_count',2),('tcp_fin_count',1),('tcp_rst_count',4)]:counts[name]=int(bool(flags&flag))
    for name,ports in PORTS.items():counts[name]=int(sport in ports or dport in ports)
    return counts,src,dst

class Bucket:
    def __init__(self):
        self.n=0;self.length_sum=0;self.length_square_sum=0;self.lo=None;self.hi=0
        self.counts=collections.Counter();self.src=set();self.dst=set();self.pairs=set();self.times=array.array('q')
    def add(self,ns,caplen,wirelen,data,link):
        self.n+=1;self.length_sum+=wirelen;self.length_square_sum+=wirelen*wirelen
        self.lo=wirelen if self.lo is None else min(self.lo,wirelen);self.hi=max(self.hi,wirelen)
        self.times.append(ns);self.counts['_snaplen_shortened_packets']+=int(caplen<wirelen)
        try:c,s,d=decode_headers(data,link)
        except HeaderError:self.counts['_header_decode_errors']+=1;return
        self.counts.update(c)
        if s is not None:self.src.add(s);self.dst.add(d);self.pairs.add((s,d))
    def serial(self,k):
        return {'bin':k,'n':self.n,'length_sum':self.length_sum,'length_square_sum':self.length_square_sum,
                'lo':self.lo,'hi':self.hi,'counts':dict(self.counts),'src':[x.hex() for x in sorted(self.src)],
                'dst':[x.hex() for x in sorted(self.dst)],'pairs':[[x.hex(),y.hex()] for x,y in sorted(self.pairs)]}
    def merge(self,row,times):
        self.n+=row['n'];self.length_sum+=row['length_sum'];self.length_square_sum+=row['length_square_sum']
        self.lo=row['lo'] if self.lo is None else min(self.lo,row['lo']);self.hi=max(self.hi,row['hi'])
        self.counts.update(row['counts']);self.src.update(bytes.fromhex(x) for x in row['src']);self.dst.update(bytes.fromhex(x) for x in row['dst'])
        self.pairs.update((bytes.fromhex(x),bytes.fromhex(y)) for x,y in row['pairs']);self.times.frombytes(np.asarray(times,dtype=np.int64).tobytes())
    def features(self,k):
        times=np.frombuffer(self.times,dtype=np.int64).copy();times.sort();diff=np.diff(times);positive=diff[diff>0]/1e9
        mean=self.length_sum/self.n;variance=max(0.,self.length_square_sum/self.n-mean*mean)
        row={'bin':k,'packet_count':self.n,'byte_count':self.length_sum,'packet_length_min':self.lo,
             'packet_length_max':self.hi,'packet_length_mean':mean,'packet_length_std':variance**.5,
             'unique_src_ip_count':len(self.src),'unique_dst_ip_count':len(self.dst),'unique_endpoint_pair_count':len(self.pairs),
             'interarrival_positive_mean':float(positive.mean()) if len(positive) else np.nan,
             'interarrival_positive_std':float(positive.std(ddof=0)) if len(positive) else np.nan,
             '_positive_interarrival_count':len(positive),'_duplicate_timestamp_differences':int((diff==0).sum()),
             '_first_ns':int(times[0]),'_last_ns':int(times[-1]),**{c:self.counts[c] for c in COUNTERS},
             **{c:v for c,v in self.counts.items() if c.startswith('_')}}
        if self.counts['_header_decode_errors']:
            for c in COUNTERS+['unique_src_ip_count','unique_dst_ip_count','unique_endpoint_pair_count']:row[c]=np.nan
        return row

def file_cache(path,cache,progress=print):
    path=Path(path);cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    engine=hashlib.sha256((Path(__file__).read_bytes()+Path(__file__).with_name('capture_reader.py').read_bytes())).hexdigest()
    progress(f'Checking input hash: {path.name}',flush=True);before=path.stat();sha=file_hash(path)
    key=hashlib.sha256((sha+engine).encode()).hexdigest();folder=cache/key;meta_path=folder/'meta.json'
    if meta_path.exists():
        m=json.loads(meta_path.read_text(encoding='utf-8'))
        if m['sha256']!=sha or m['engine_sha256']!=engine:raise RuntimeError('Network cache identity mismatch')
        for name,h in m['payload_hashes'].items():
            if not (folder/name).is_file() or file_hash(folder/name)!=h:raise RuntimeError(f'Changed network cache payload: {folder/name}')
        progress(f'Reusing verified network features: {path.name}',flush=True);return m,folder
    bins=collections.defaultdict(Bucket)
    def accept(ns,caplen,wirelen,data,link):bins[ns//5_000_000_000].add(ns,caplen,wirelen,data,link)
    meta,_=capture_summary(path,progress=lambda x:progress(x,flush=True),packet_callback=accept)
    after=path.stat()
    if meta['sha256']!=sha or before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise RuntimeError('Input changed while reading; no cache committed')
    if meta['untimestamped_packets']:raise RuntimeError('Untimestamped packet blocks prevent a complete 5 s value view')
    if not bins:raise RuntimeError(f'No timestamped complete packets in {path}')
    folder.mkdir(exist_ok=True);keys=sorted(bins);offsets=np.r_[0,np.cumsum([bins[k].n for k in keys])]
    times=np.empty(int(offsets[-1]),dtype=np.int64)
    with gzip.open(folder/'buckets.jsonl.gz','wt',encoding='utf-8') as f:
        for i,k in enumerate(keys):
            times[offsets[i]:offsets[i+1]]=np.frombuffer(bins[k].times,dtype=np.int64)
            f.write(json.dumps(bins[k].serial(k),sort_keys=True)+'\n')
    np.savez_compressed(folder/'timestamps.npz',bins=keys,offsets=offsets,times=times)
    meta.update(engine_sha256=engine,payload_hashes={x:file_hash(folder/x) for x in ['buckets.jsonl.gz','timestamps.npz']})
    json_write(meta_path,meta);progress(f'{path.name}: {meta["packets"]:,} complete packets; {meta["integrity_status"]}',flush=True)
    return meta,folder

def merge_group(caches):
    """Pool by 5 s timestamp, including files whose record times are out of order."""
    bins=collections.defaultdict(Bucket);bad_bins=set();meta=[]
    for m,folder in caches:
        meta.append(m)
        if m['integrity_status']!='COMPLETE_RECORD_STREAM':
            cut=m.get('incomplete_record') or {};ns=cut.get('excluded_record_timestamp_ns',m['last_ns'])
            bad_bins.add(int(ns)//5_000_000_000)
        with np.load(folder/'timestamps.npz',allow_pickle=False) as a, gzip.open(folder/'buckets.jsonl.gz','rt',encoding='utf-8') as f:
            times=a['times'];offsets=a['offsets'];keys=a['bins']
            for i,line in enumerate(f):
                row=json.loads(line);k=int(row['bin'])
                if k!=int(keys[i]):raise RuntimeError('Cache timestamp/bin alignment mismatch')
                bins[k].merge(row,times[offsets[i]:offsets[i+1]])
    rows=[]
    for k in sorted(bins):
        row=bins.pop(k).features(k);row['_incomplete_boundary']=int(k in bad_bins);rows.append(row)
    frame=pd.DataFrame(rows).set_index('bin');return frame,meta
