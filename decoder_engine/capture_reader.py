"""Recovered capture reader with a complete-packet callback added for reconstruction.
No callback is made for an incomplete capture record.
"""
import collections, struct, time, hashlib
from pathlib import Path

class HashReader:
    def __init__(self,path):self.f=open(path,'rb',buffering=1024*1024);self.h=hashlib.sha256();self.n=0
    def read(self,n):
        b=self.f.read(n);self.h.update(b);self.n+=len(b);return b
    def exact(self,n):
        b=self.read(n)
        if len(b)!=n:raise ValueError(f'Truncated capture at byte {self.n}; needed {n} bytes, received {len(b)}')
        return b
    def close(self):self.f.close()

def capture_summary(path,progress=None,packet_callback=None):
    """Streaming PCAP/PCAPNG timestamps. Does not infer traffic absence or decode payloads.
    PCAP 2.4 micro/nanoseconds, both byte orders. PCAPNG SHB/IDB/EPB/obsolete PB;
    interface resolution and offset honoured; untimestamped SPB counted explicitly.
    """
    r=HashReader(path);bins=collections.Counter();limits={};meta={'file':str(path),'packets':0,
      'untimestamped_packets':0,'backward_steps':0,'truncated_payloads':0,'subnanosecond_timestamps':0,
      'unknown_blocks':0,'interfaces':[],'first_ns':None,'last_ns':None,
      'integrity_status':'COMPLETE_RECORD_STREAM','incomplete_record':None}
    previous=None;last_report=time.monotonic()
    def add(ns,caplen,wirelen,iface,payload,linktype):
        nonlocal previous,last_report
        if ns<0 or ns>=9223372036854775807:raise ValueError('Capture timestamp outside supported datetime range')
        if previous is not None and ns<previous:meta['backward_steps']+=1
        previous=ns
        if packet_callback is not None:packet_callback(ns,caplen,wirelen,payload,linktype)
        meta['packets']+=1;meta['truncated_payloads']+=int(caplen<wirelen)
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
                add(sec*1_000_000_000+fraction*mult,caplen,wirelen,0,data,hdr[5]&0xffff)
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
                        interfaces.append((den,offset,snap,link));meta['interfaces'].append({'linktype':link,'ticks_per_second':den,'offset_seconds':offset})
                    elif kind in (6,2):
                        if len(body)<20:raise ValueError('Truncated timestamped packet block')
                        if kind==6:iface,hi,lo,caplen,wirelen=struct.unpack_from(endian+'IIIII',body)
                        else:iface,_,hi,lo,caplen,wirelen=struct.unpack_from(endian+'HHIIII',body)
                        if iface>=len(interfaces):raise ValueError('Packet references missing interface')
                        den,off,snap,link=interfaces[iface]
                        if caplen>wirelen or (snap and caplen>snap) or 20+(caplen+3)//4*4>len(body):raise ValueError('Invalid captured length')
                        numerator=((hi<<32)|lo)*1_000_000_000
                        meta['subnanosecond_timestamps']+=int(numerator%den!=0)
                        add(numerator//den+off*1_000_000_000,caplen,wirelen,iface,body[20:20+caplen],link)
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
