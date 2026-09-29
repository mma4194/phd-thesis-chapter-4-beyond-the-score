import csv,gzip,hashlib,io,tempfile,unittest
from pathlib import Path
import numpy as np
from artifact.prepared_content import check_table

class PreparedContentContracts(unittest.TestCase):
    def reference(self):
        rows=[['bin','packet_count','packet_length_std','observed'],['1','3','<STD>','True'],['2','0','<STD>','False']]
        s=io.StringIO(newline='');csv.writer(s,lineterminator='\n').writerows(rows)
        return {'rows':2,'columns':rows[0],'exact_fields_sha256':hashlib.sha256(s.getvalue().encode()).hexdigest(),'std_reference':{'packet_length_std':[1.,None]}}
    def check(self,rows,ending='\n'):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.csv.gz'
            with gzip.open(p,'wt',encoding='utf-8',newline='') as f:csv.writer(f,lineterminator=ending).writerows([self.reference()['columns']]+rows)
            return check_table(p,self.reference())['passed']
    def test_format_and_one_ulp_only(self):
        for ending in ['\n','\r\n']:
            self.assertTrue(self.check([['1','3',repr(float(np.nextafter(1.,np.inf))),'True'],['2','0','','False']],ending))
        two=float(np.nextafter(np.nextafter(1.,np.inf),np.inf))
        self.assertFalse(self.check([['1','3',repr(two),'True'],['2','0','','False']]))
    def test_counts_masks_and_missingness_fail(self):
        for rows in [[['1','4','1.0','True'],['2','0','','False']],[['1','3','1.0','False'],['2','0','','False']],[['1','3','1.0','True'],['2','0','0.0','False']]]:
            self.assertFalse(self.check(rows))
    def test_row_and_column_structure_fail(self):
        self.assertFalse(self.check([['2','0','','False'],['1','3','1.0','True']]))
        self.assertFalse(self.check([['1','3','1.0','True']]))
        self.assertFalse(self.check([['1','3','1.0'],['2','0','','False']]))
