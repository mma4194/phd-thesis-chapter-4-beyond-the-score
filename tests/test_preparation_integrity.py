import json, tempfile, unittest
from pathlib import Path
from artifact.common import sha, write_json
from artifact.preparation_integrity import TABLES, REPORTS, freeze, verify

class PreparationIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prep = self.root / 'preparation'; self.prep.mkdir()
        for name in TABLES:
            (self.prep / name).write_bytes(b'immutable table ' + name.encode())
        write_json(self.prep / 'prepared_files.json', {n: sha(self.prep/n) for n in TABLES})
        for name in REPORTS:
            data = []
            if name.startswith('input_identity'): data = [{'match': True}] * 16
            if name.startswith('telemetry_member'): data = [{'match': True}] * 42
            if name.startswith('prepared_content'): data = {'status': 'PASS', 'checked_files': 6}
            write_json(self.root / name, data)
        freeze(self.prep, self.root, 'same-data')

    def test_evaluation_progress_does_not_invalidate_preparation(self):
        before = verify(self.prep, 'same-data')
        for name in ['latest_status.json','artifact_workflow.json','progress.json','latest_configuration.json']:
            write_json(self.root/name, {'phase':'EVALUATION_RETURNED','completed':72})
        write_json(self.prep/'preparation_status.json', {'evaluation_completed':True})
        # The live report can change; the frozen preparation report cannot.
        write_json(self.root/'prepared_content_comparison.json', {'later_run':True})
        self.assertEqual(before, verify(self.prep, 'same-data'))
        self.assertEqual(before, freeze(self.prep, self.root, 'same-data'))

    def test_production_evaluation_wrapper_preserves_preparation(self):
        from types import SimpleNamespace
        from artifact.toniot import evaluate
        run=self.root/'evaluation'/'new_run';run.mkdir(parents=True)
        def evaluate_job():
            write_json(self.root/'latest_status.json',{'Evaluation':'COMPLETE'})
            write_json(run/'progress.json',{'completed_source_jobs':72})
            return {'execution_status':'PLANNED_JOBS_COMPLETED'}
        p=SimpleNamespace(out=self.root,prep=self.prep,prep_id='same-data',
                          runtime={'RUN':run},evaluate=evaluate_job,
                          phase=lambda name,fn:fn())
        before=verify(self.prep,'same-data')
        self.assertEqual(evaluate(p)['execution_status'],'PLANNED_JOBS_COMPLETED')
        self.assertEqual(verify(self.prep,'same-data'),before)
        self.assertEqual(json.loads((self.root/'artifact_workflow.json').read_text())['phase'],'EVALUATION_RETURNED')

    def test_table_corruption_rejected(self):
        (self.prep/TABLES[0]).write_bytes(b'changed')
        with self.assertRaises(RuntimeError): verify(self.prep)

    def test_copied_report_corruption_rejected(self):
        (self.prep/'verified_input_checks'/REPORTS[0]).write_text('[]')
        with self.assertRaises(RuntimeError): verify(self.prep)
        with self.assertRaises(RuntimeError): freeze(self.prep,self.root,'same-data')

    def test_missing_table_rejected(self):
        (self.prep/TABLES[1]).unlink()
        with self.assertRaises(RuntimeError): verify(self.prep)

    def test_changed_preparation_identity_rejected(self):
        with self.assertRaises(RuntimeError): verify(self.prep, 'different-data')

    def test_manifest_corruption_rejected(self):
        write_json(self.prep/'prepared_files.json',{})
        with self.assertRaises(RuntimeError): verify(self.prep)

    def test_receipt_corruption_rejected(self):
        p=self.prep/'preparation_verified.json'
        d=json.loads(p.read_text());d['files'].pop(TABLES[0]);write_json(p,d)
        with self.assertRaises(RuntimeError): verify(self.prep)
