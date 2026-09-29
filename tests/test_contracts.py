import unittest,tempfile,struct,json
from pathlib import Path
import numpy as np
import pandas as pd
from artifact.common import residential_namespace,public_namespace
from artifact.recalculate import Audit
from external_rebuild.capture_reader import capture_summary
from external_rebuild.network import decode_headers
class ScientificContracts(unittest.TestCase):
 def test_missing_labels_and_join_embargo(self):
  n=residential_namespace();n['MASK_MAP']={};self.assertEqual(len(n['software_checks']()),8)
 def test_full_support_not_prefix(self):
  n=residential_namespace();a=np.r_[np.zeros(100000),np.full(5000,.303)].astype(np.float32)
  self.assertFalse(n['infer_column_support'](a)['binary']);b=n['empirical_hurdle_draw'](a,10000,np.random.default_rng(1337))
  self.assertTrue((b>=a.min()).all() and (b<=a.max()).all() and (b>0).any())
  self.assertTrue(n['infer_column_support'](np.array([0.,1.]))['binary'])
 def test_public_model_and_mask_contracts(self):
  ns=public_namespace();checks=ns['run_software_checks']();self.assertTrue(len(checks)>0 and all(c['passed'] for c in checks))
 def test_pcaps_both_endian_and_incomplete_tail(self):
  for endian in ['<','>']:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'capture.pcap';head=struct.pack(endian+'IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)
    a=struct.pack(endian+'IIII',1554220325,2,4,4)+b'abcd';b=struct.pack(endian+'IIII',1554220330,3,4,4)+b'ab'
    p.write_bytes(head+a+b);seen=[];meta,bins=capture_summary(p,packet_callback=lambda *args:seen.append(args))
    self.assertEqual(meta['packets'],1);self.assertEqual(len(seen),1);self.assertEqual(meta['first_ns'],1554220325000002000);self.assertEqual(meta['integrity_status'],'INCOMPLETE_EOF');self.assertEqual(meta['incomplete_record']['missing_bytes_in_declared_record'],2)
    p.write_bytes(head+struct.pack(endian+'IIII',1,0,8,4)+b'12345678')
    with self.assertRaises(ValueError):capture_summary(p)
 def test_ethernet_ipv4_tcp_dns(self):
  eth=b'\x00'*12+b'\x08\x00';ip=bytearray(20);ip[0]=0x45;ip[2:4]=struct.pack('!H',40);ip[9]=6;ip[12:20]=bytes([10,0,0,1,10,0,0,2]);tcp=bytearray(20);tcp[:4]=struct.pack('!HH',2000,53);tcp[12]=0x50;tcp[13]=2
  counts,src,dst=decode_headers(eth+ip+tcp,1);self.assertEqual(counts['dns_port_packets'],1);self.assertEqual(counts['tcp_syn_count'],1);self.assertEqual(counts['ipv4_count'],1)
 def test_comparison_rejects_missing_duplicate_and_changed_rows(self):
  ref=pd.DataFrame({'id':[1,2],'value':[.3,.8]})
  for bad in [ref.iloc[:1],pd.concat([ref,ref.iloc[:1]]),ref.assign(value=[.3,.9])]:
   with tempfile.TemporaryDirectory() as d:
    a=Audit(Path(d));a.compare('deliberate_fault',bad,ref,['id']);self.assertTrue(any(not c['passed'] for c in a.checks))
 def test_new_incomplete_run_cannot_reuse_old_pass(self):
  from artifact.finish import result_paths
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base=root/'runs/controlled';old=base/'old/full';new=base/'new/full';old.mkdir(parents=True);new.mkdir(parents=True)
   (old/'artifact_status.json').write_text(json.dumps({'paper_comparison':'PASS'}));(base/'latest_full.json').write_text(json.dumps({'path':'new/full'}))
   paths=result_paths(root);self.assertEqual(paths['controlled'],new/'artifact_status.json');self.assertFalse(paths['controlled'].is_file())
 def test_skill_is_per_task_not_aggregate_identity(self):
  real=np.array([1.,2.]);syn=np.array([2.,2.]);naive=np.array([4.,4.]);rat=syn/real;skill=1-real/naive
  np.testing.assert_allclose(1-syn/naive,1-rat*(1-skill))
  self.assertFalse(np.isclose((1-syn/naive).mean(),1-np.exp(np.log(rat).mean())*(1-skill.mean())))
if __name__=='__main__':unittest.main(verbosity=2)
