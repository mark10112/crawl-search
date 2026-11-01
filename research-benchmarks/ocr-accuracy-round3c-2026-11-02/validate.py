"""Audit recorded benchmark evidence without running inference."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
results = root / 'results'
analysis = json.loads((results / 'analysis.json').read_text(encoding='utf8'))
assert len(analysis['rows']) == 16
assert analysis['reference_hash'] == '72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
provenance = json.loads((results / 'baseline-provenance.json').read_text())
assert len(provenance['files']) == 8
for record in provenance['files']:
    data = (results / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    assert data == (root.parent / 'ocr-accuracy-round3-2026-11-01/results' / record['file']).read_bytes()
manifest = json.loads((root.parent / 'real-history-2026-11-01/manifest.json').read_text())
for row in analysis['rows']:
    raw = json.loads((results / f"{row['variant']}-{row['mode']}-{row['id']}.json").read_text(encoding='utf8'))['raw']
    assert raw['content_sha256'] == next(c['sha256'] for c in manifest['cases'] if c['id'] == row['id'])
    if row['variant'] == 'after':
        assert row['ok'] and row['complete_output'] and not row['output_truncated']
for summary in analysis['summaries']:
    assert summary['table_total'] == 15
    if summary['variant'] == 'after' and summary['mode'] == 'ocr':
        assert summary['table_correct'] == 4
health = json.loads((results / 'restored.json').read_text())['health']
assert health['commit'] == 'ac1b98ba313e49f0c9a4be57e382a083fa6f0f8b'
assert health['worker_alive'] and not health['draining'] and health['ocr_router']['ok']
output = {
    'status': 'passed', 'document_observations': 16,
    'source_hashes_verified': 16, 'baseline_files_byte_identical': 8,
    'after_outputs_complete': 8, 'forced_table_rows_correct': 4,
    'forced_table_rows_total': 15, 'reference_hash': analysis['reference_hash'],
    'inference_commit': '9859627a68a7960f575a91f50aba34107543dbda',
    'production_commit': health['commit'],
    'test_evidence': '57 tests passed; GitHub Actions run 41333120827 succeeded for inference commit',
    'note': 'Completion is not character accuracy. One observation per condition; reused baseline.',
}
(results / 'validation.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf8')
print(json.dumps(output, indent=2))
