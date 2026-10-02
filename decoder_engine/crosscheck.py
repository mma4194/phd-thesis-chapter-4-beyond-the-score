"""Optional independent TShark check of the first 10,000 packets per file.

No capture is modified. Absence of TShark is recorded, not treated as validation.
"""
import decimal, ipaddress, shutil, subprocess
from pathlib import Path
from .capture_reader import capture_summary
from .network import decode_headers, HeaderError
from .telemetry_recovery import json_write

FIELDS=['frame.time_epoch','frame.len','ip.version','ip.src','ip.dst','ip.proto','ip.frag_offset',
        'tcp.srcport','tcp.dstport','tcp.flags','udp.srcport','udp.dstport']

def run(project,limit=10000):
    candidate=shutil.which('tshark')
    if not candidate:
        p=Path(r'C:\Program Files\Wireshark\tshark.exe')
        if p.is_file():candidate=str(p)
    if not candidate:
        result={'status':'NOT_RUN','reason':'TShark is not installed or not found. Constructed decoder tests remain available; no independent real-packet cross-check is claimed.'}
        json_write(project.out/'independent_decoder_check.json',result);return result
    version=subprocess.run([candidate,'--version'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30).stdout.splitlines()[0]
    rows=[]
    class Enough(Exception):pass
    for name,path in project.captures.items():
        ours=[]
        def accept(ns,caplen,wirelen,payload,link):
            try:c,s,d=decode_headers(payload,link);entry={'ns':ns,'wire':wirelen,'counts':c,'src':s,'dst':d,'header_error':False}
            except HeaderError:entry={'ns':ns,'wire':wirelen,'header_error':True}
            ours.append(entry)
            if len(ours)>=limit:raise Enough()
        try:capture_summary(path,packet_callback=accept)
        except Enough:pass
        cmd=[candidate,'-n','-r',str(path),'-c',str(limit),'-T','fields','-E','separator=\t','-E','occurrence=f']
        for field in FIELDS:cmd+=['-e',field]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
        if result.returncode:raise RuntimeError(f'TShark failed on {name}: {result.stderr[-1500:]}')
        records=[line.split('\t') for line in result.stdout.splitlines()]
        if len(records)!=len(ours):raise RuntimeError('Independent decoder packet count differs: '+name)
        checks=0;ipv4_checked=0;errors=[]
        for i,(a,vals) in enumerate(zip(ours,records)):
            q=dict(zip(FIELDS,vals));ns=int(decimal.Decimal(q['frame.time_epoch'])*10**9)
            checks+=2
            if ns!=a['ns'] or int(q['frame.len'])!=a['wire']:errors.append({'packet_1based':i+1,'field':'timestamp_or_wire_length'})
            if a['header_error'] or a['counts'].get('ipv4_count')!=1:continue
            if q['ip.version']!='4':errors.append({'packet_1based':i+1,'field':'outer_ipv4_version'});continue
            ipv4_checked+=1;checks+=2
            if ipaddress.ip_address(q['ip.src']).packed!=a['src'] or ipaddress.ip_address(q['ip.dst']).packed!=a['dst']:errors.append({'packet_1based':i+1,'field':'outer_ip_addresses'})
            proto=int(q['ip.proto']);checks+=2
            if int(proto==6)!=a['counts']['tcp_count'] or int(proto==17)!=a['counts']['udp_count']:errors.append({'packet_1based':i+1,'field':'transport_protocol'})
            if q['ip.frag_offset'] not in ('','0') or proto not in (6,17):continue
            prefix='tcp' if proto==6 else 'udp';ports={int(q[prefix+'.'+p]) for p in ['srcport','dstport'] if q.get(prefix+'.'+p)}
            if len(ports)==0:continue
            for metric,expected in [('http_port_packets',{80}),('https_port_packets',{443}),('dns_port_packets',{53}),('mqtt_port_packets',{1883,8883})]:
                checks+=1
                if a['counts'][metric]!=int(bool(ports&expected)):errors.append({'packet_1based':i+1,'field':metric})
            if proto==6 and q.get('tcp.flags'):
                flags=int(q['tcp.flags'],16)
                for metric,bit in [('tcp_syn_count',2),('tcp_fin_count',1),('tcp_rst_count',4)]:
                    checks+=1
                    if a['counts'][metric]!=int(bool(flags&bit)):errors.append({'packet_1based':i+1,'field':metric})
        rows.append({'file':name,'packets_compared':len(ours),'ipv4_headers_compared':ipv4_checked,'field_comparisons':checks,'differences':errors[:20],'difference_count':len(errors)})
        json_write(project.out/'independent_decoder_check.json',{'status':'IN_PROGRESS','tshark_version':version,'files':rows})
        if errors:raise RuntimeError(f'Independent decoder disagreement in {name}; inspect independent_decoder_check.json before evaluation')
        print(f'TShark cross-check: {name}, {len(ours):,} packets, no tested-field differences.',flush=True)
    result={'status':'PASS','tshark_version':version,'scope':'First packets per file; timestamps and lengths for every sampled packet, simple outer IPv4 addresses/protocols/ports. Not exhaustive payload or whole-file validation.','files':rows}
    json_write(project.out/'independent_decoder_check.json',result);return result
