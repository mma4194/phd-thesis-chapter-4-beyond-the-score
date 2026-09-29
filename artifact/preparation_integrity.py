"""Freeze preparation evidence independently of live workflow/progress reports.

Only immutable prepared files and copies of input-check reports are bound. The
receipt is never refreshed when evaluation updates its status or progress.
"""
from pathlib import Path
import json
from .common import sha, digest, write_json

TABLES = (
    'TON_IoT_normal_5s_canonical_rebuilt.csv.gz',
    'TON_IoT_normal_5s_preimputation_rebuilt.csv.gz',
    'TON_IoT_normal_5s_observed_mask.csv.gz',
    'general_5s_features.csv.gz', 'iot_named_5s_features.csv.gz',
    'telemetry_observed_counts.csv.gz',
)
REPORTS = (
    'input_identity_comparison.json', 'telemetry_member_comparison.json',
    'capture_audit_comparison.csv', 'software_checks.json',
    'prepared_table_comparison.json', 'prepared_content_comparison.json',
)
RECEIPT = 'preparation_verified.json'

def contained(root, rel):
    root = Path(root).resolve()
    p = (root / rel).resolve()
    if not p.is_relative_to(root) or p == root:
        raise ValueError('Preparation path escapes its directory: ' + str(rel))
    return p

def immutable_manifest(prep):
    prep = Path(prep)
    manifest = json.loads((prep / 'prepared_files.json').read_text())
    if not set(TABLES).issubset(manifest):
        raise RuntimeError('Prepared table manifest is incomplete.')
    for rel, expected in manifest.items():
        if Path(rel).name in {'latest_status.json', 'progress.json', 'artifact_workflow.json', 'preparation_status.json'}:
            raise RuntimeError('Legacy mutable preparation manifest. Reprepare with the current code.')
        p = contained(prep, rel)
        if not p.is_file() or sha(p) != expected:
            raise RuntimeError('Prepared file changed or missing: ' + rel)
    return manifest

def freeze(prep, output_root, preparation_id):
    prep, output_root = Path(prep), Path(output_root)
    if (prep / RECEIPT).exists():
        return verify(prep, preparation_id)
    immutable_manifest(prep)
    copies = prep / 'verified_input_checks'
    copies.mkdir(exist_ok=True)
    for name in REPORTS:
        source = output_root / name
        if not source.is_file():
            raise FileNotFoundError('Missing input-check report: ' + name)
        target = copies / name
        data = source.read_bytes()
        if target.exists() and target.read_bytes() != data:
            raise RuntimeError('Existing frozen input-check report differs: ' + name)
        target.write_bytes(data)
    paths = list(TABLES) + ['prepared_files.json'] + ['verified_input_checks/' + n for n in REPORTS]
    content = {'schema': 1, 'preparation_id': preparation_id,
               'files': {p: sha(contained(prep, p)) for p in paths},
               'scope': 'Immutable prepared tables and copied input checks only'}
    write_json(prep / RECEIPT, {**content, 'receipt_digest': digest(content)})
    return verify(prep, preparation_id)

def verify(prep, preparation_id=None):
    prep = Path(prep)
    receipt = json.loads((prep / RECEIPT).read_text())
    content = {k: v for k, v in receipt.items() if k != 'receipt_digest'}
    if digest(content) != receipt.get('receipt_digest') or receipt.get('schema') != 1:
        raise RuntimeError('Preparation receipt changed or unsupported.')
    if preparation_id is not None and receipt['preparation_id'] != preparation_id:
        raise RuntimeError('Preparation identity differs.')
    required = set(TABLES) | {'prepared_files.json'} | {'verified_input_checks/' + n for n in REPORTS}
    if set(receipt['files']) != required:
        raise RuntimeError('Preparation receipt coverage differs.')
    for rel, expected in receipt['files'].items():
        path = contained(prep, rel)
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError('Frozen preparation evidence changed or missing: ' + rel)
    immutable_manifest(prep)
    checks = prep / 'verified_input_checks'
    for name, field in [('input_identity_comparison.json', 'match'), ('telemetry_member_comparison.json', 'match')]:
        rows = json.loads((checks / name).read_text())
        expected_n = 16 if name.startswith('input_') else 42
        if len(rows) != expected_n or not all(r.get(field) is True for r in rows):
            raise RuntimeError('Input identity check did not pass: ' + name)
    content_check = json.loads((checks / 'prepared_content_comparison.json').read_text())
    if content_check.get('status') != 'PASS' or content_check.get('checked_files') != 6:
        raise RuntimeError('Prepared-content check did not pass.')
    return {'status': 'PASS', 'preparation_id': receipt['preparation_id'],
            'receipt_digest': receipt['receipt_digest'], 'immutable_files': len(receipt['files']),
            'mutable_progress_files_hashed': False}
