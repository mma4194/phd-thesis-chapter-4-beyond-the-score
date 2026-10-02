from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def validate_decoder(receipt):
 if receipt.get('status')!='PASS':raise ValueError('Local decoder has not passed')
 expected=json.loads((ROOT/'evidence/decoder_code_hashes.json').read_text())
 if receipt.get('decoder_code_hashes')!=expected:raise ValueError('Different decoder implementation')
 protocol=json.loads((ROOT/'evidence/preparation_protocol.json').read_text())
 expected_files={Path(r['name']).name:r['sha256'] for r in protocol['input_files'] if r['role']!='telemetry'}
 inputs=receipt.get('input_files',[])
 if len(inputs)!=15 or {r['name']:r['sha256'] for r in inputs}!=expected_files:raise ValueError('Different or missing raw input identities')
 check=receipt.get('check',{});files=check.get('files',[])
 if check.get('status')!='PASS' or not check.get('tshark_version'):raise ValueError('Missing independent-check provenance')
 if len(files)!=15 or {r['file'] for r in files}!={Path(n).stem for n in expected_files}:raise ValueError('Missing/duplicate capture results')
 if any(r['packets_compared']!=10000 or r['difference_count']!=0 or r['differences'] for r in files):raise ValueError('Incomplete or differing packet comparison')
 return dict(status='PASS',tshark_version=check['tshark_version'],captures=15,packets=150000,scope=check['scope'],evidence_type='Separate local execution; original Falcon decoder status remains unchanged')
