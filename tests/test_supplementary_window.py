import tempfile, unittest
from pathlib import Path
import numpy as np
import pandas as pd
from artifact.supplementary import temporal_window

class TemporalWindowEquivalence(unittest.TestCase):
    def test_window_matches_full_canonical_conversion(self):
        # Deliberately unordered chronology, nonfinite values and float32 overflow.
        raw=pd.DataFrame({'sec':[3,0,5,1,4,2], 'second':[3.,np.nan,5.,np.inf,1e40,-np.inf],
                          'unused':range(6), 'first':[.1,.2,.3,.4,.5,.6]})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.parquet';raw.to_parquet(path,index=False)
            actual,selection=temporal_window(path,{'feature_scopes':{'protocol_value_v3':['first','second']}},
                                             {'test_start':1,'test_end':6},cap=4)
            with np.errstate(over='ignore',invalid='ignore'):
                expected=raw.sort_values('sec',kind='stable')[['second','first']].astype(np.float32).iloc[1:5]
            expected=expected.replace([np.inf,-np.inf],np.nan).fillna(0).reset_index(drop=True)
            pd.testing.assert_frame_equal(actual,expected,check_exact=True)
            self.assertEqual(selection['test_stop'],5)
            self.assertEqual(selection['columns'],['second','first'])

    def test_missing_second_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.parquet'
            pd.DataFrame({'sec':[0,1,3],'x':[1.,2.,3.]}).to_parquet(path,index=False)
            with self.assertRaises(ValueError):
                temporal_window(path,{'feature_scopes':{'protocol_value_v3':['x']}},{'test_start':0,'test_end':3})
