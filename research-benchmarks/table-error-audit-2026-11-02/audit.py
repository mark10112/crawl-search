"""Replay the frozen 15-row score and audit existing page-region evidence.

No model calls, no reference edits, no runtime corrections. Source boxes below
are manual diagnostic annotations on 200-DPI source renders, not OCR inputs.
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup
from PIL import ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BENCH = HERE.parent / 'ocr-accuracy-round3c-2026-11-02'
RESULTS = BENCH / 'results'
SOURCES = REPO / '.cache/ocr-diagnosis'
LOCK = '72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'

def norm(text):
    text = BeautifulSoup(text, 'html.parser').get_text(' ')
    text = unicodedata.normalize('NFC', text).lower()
    text = ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return ''.join(c for c in text if c.isalnum() or unicodedata.category(c).startswith('M'))

refs = json.loads((HERE.parent / 'real-history-2026-11-01/references.json').read_text(encoding='utf8'))
assert hashlib.sha256(json.dumps(refs, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == LOCK
manifest = json.loads((HERE.parent / 'real-history-2026-11-01/manifest.json').read_text())
analysis = json.loads((RESULTS / 'analysis.json').read_text(encoding='utf8'))
telemetry = [json.loads(line) for line in (RESULTS / 'after-only-telemetry.jsonl').read_text(encoding='utf8').splitlines()]
pages = {ident: [r['result'] for r in telemetry if r['kind'] == 'page' and r['mode'] == 'ocr' and r['id'] == ident]
         for ident in ['thai-gazette', 'us-census', 'us-preservation']}
raws = {ident: json.loads((RESULTS / f'after-ocr-{ident}.json').read_text(encoding='utf8'))['raw'] for ident in pages}
for ident in pages:
    case = next(c for c in manifest['cases'] if c['id'] == ident)
    assert hashlib.sha256((SOURCES / case['filename']).read_bytes()).hexdigest() == case['sha256'] == raws[ident]['content_sha256']

# Source-image labels transcribed for diagnosis, not supplied to any recognizer.
gazette = [
    {'observed_label': 'ประกาศสงกรานต์ ปี๒๐ จัตวาศก', 'digit_box_200': [754, 559, 781, 585], 'row_box_200': [34, 538, 797, 590]},
    {'observed_label': 'ประกาศวางโทษเรื่องทักอ้วนผอม', 'digit_box_200': [735, 977, 780, 1011], 'row_box_200': [34, 957, 797, 1015]},
    {'observed_label': 'ประกาศให้เก็บภาษีหัวเปียรวมอยูโนบ่อน', 'digit_box_200': [780, 337, 828, 369], 'row_box_200': [82, 327, 838, 374]},
    {'observed_label': 'ปรากฏให้ใช้กะแปะอัฐและโสพสที่ทำขึ้นใหม่', 'digit_box_200': [777, 389, 828, 422], 'row_box_200': [82, 377, 838, 425]},
    {'observed_label': 'ประกาศมหาสงกรานต์ ปีกุน เบญจศก', 'digit_box_200': [754, 275, 801, 308], 'row_box_200': [40, 263, 814, 316]},
    {'observed_label': 'ประกาศพิกัดภาษี เรือ ตึก แพง โรง ร้าน', 'digit_box_200': [741, 1076, 802, 1108], 'row_box_200': [40, 1064, 814, 1116]},
]

rows = []
for index, ref in enumerate(refs['table_rows']):
    ident, page = ref['document'], ref['page']
    if ident not in raws:
        continue
    observed_page = pages[ident][page - 1]
    legacy = norm(ref['label'] + ''.join(ref['values'])) in norm(raws[ident]['text'])
    old = next(t for d in analysis['details'] if d['file'] == f'after-ocr-{ident}.json'
               for t in d['tables'] if t['label'] == ref['label'])
    assert legacy == old['correct']
    record = {'index': index + 1, **ref, 'legacy_strict_correct': legacy,
              'evidence_page': f'../ocr-accuracy-round3c-2026-11-02/results/after-ocr-{ident}.json',
              'page_telemetry': '../ocr-accuracy-round3c-2026-11-02/results/after-only-telemetry.jsonl'}
    if ident == 'thai-gazette':
        annotation = gazette[index]
        label = annotation['observed_label']
        assert norm(label) in norm(observed_page['text'])
        digit = norm(ref['values'][0])
        tokens = [norm(t) for t in re.findall(r'\d+', BeautifulSoup(observed_page['text'], 'html.parser').get_text(' '))]
        # Render size is 300 DPI in this frozen run. Test annotated digit center
        # against stored recognition-eligible text/content/table region boxes.
        box = annotation['digit_box_200']
        cx, cy = (box[0] + box[2]) * .75, (box[1] + box[3]) * .75
        cover = [j for j, region in enumerate(observed_page['regions'])
                 if region['block_label'] in {'text', 'content', 'table'}
                 and (b := region['block_bbox'])[0] <= cx <= b[2] and b[1] <= cy <= b[3]]
        record.update(category='missing_page_number', observed_label=label, observed_values=[],
                      same_numeric_token_elsewhere_on_page=digit in tokens,
                      secondary_label_error=norm(label) != norm(ref['label']),
                      digit_center_300=[cx, cy], text_region_indices_covering_digit_center=cover,
                      layout_evidence='inside_recorded_text_region_but_not_transcribed' if cover else 'outside_all_recorded_text_regions',
                      source_annotation_200=annotation, confidence='high_observed_failure; crop_causality_not_proven')
    else:
        candidates = [tr for tr in BeautifulSoup(observed_page['text'], 'html.parser').find_all('tr')
                      if norm(ref['label']) in norm(tr.get_text(' '))]
        assert candidates
        tr = candidates[0]  # First Table 2 occurrence; Table 3 repeats county names.
        cells = [cell.get_text(' ', strip=True) for cell in tr.find_all(['td', 'th'], recursive=False)]
        region_matches = []
        for region_index, region in enumerate(observed_page['regions']):
            if region['block_label'] != 'table':
                continue
            for source_tr in BeautifulSoup(region['block_content'], 'html.parser').find_all('tr'):
                source_cells = [c.get_text(' ', strip=True) for c in source_tr.find_all(['td', 'th'], recursive=False)]
                if source_cells == cells:
                    region_matches.append(region_index)
        assert region_matches
        record.update(observed_html=str(tr), observed_cells=cells,
                      raw_region_matches_final_cells=True, source_region_indices=region_matches)
        if ident == 'us-preservation' and ref['label'] == 'San Diego Sun':
            assert cells[0] == 'Portland Oregonian San Diego Sun'
            assert all(norm(v) in norm(tr.get_text(' ')) for v in ref['values'])
            record.update(category='merged_rows', observed_values=['Oct. 31, 1872', '100', '1'],
                          note='All target values survive, but two source rows are merged cell by cell. Not a mere whitespace/scoring issue.',
                          confidence='high')
        elif ident == 'us-census':
            observed = cells[1:6]
            differences = [{'year': str(1900 - j * 10), 'expected': expected, 'observed': actual}
                           for j, (expected, actual) in enumerate(zip(ref['values'], observed)) if norm(expected) != norm(actual)]
            record.update(category='digit_substitution' if differences else 'correct',
                          observed_values=observed, value_differences=differences,
                          note='Body value sequence aligns with source years. Page 2 also has an unrelated phantom header colspan/empty-column issue.', confidence='high')
            assert legacy == (not differences)
        else:
            assert legacy
            record.update(category='correct', observed_values=cells[1:], confidence='high')
    rows.append(record)

assert len(rows) == 15 and sum(r['legacy_strict_correct'] for r in rows) == 4
counts = {category: sum(r['category'] == category for r in rows) for category in ['missing_page_number', 'digit_substitution', 'merged_rows', 'correct']}
assert counts == {'missing_page_number': 6, 'digit_substitution': 4, 'merged_rows': 1, 'correct': 4}
summary = {'reference_hash': LOCK, 'inference_rerun': False, 'runtime_modified': False,
           'counts': counts, 'wrong_numeric_cells_in_four_census_rows': sum(len(r.get('value_differences', [])) for r in rows),
           'gazette_secondary_label_errors': sum(r.get('secondary_label_error', False) for r in rows),
           'gazette_digit_centers_outside_text_regions': sum(r['category'] == 'missing_page_number' and not r['text_region_indices_covering_digit_center'] for r in rows),
           'limitations': 'Stored parsing boxes are not a capture of every recognizer input crop. No oracle-crop inference or model comparison was run. Recommendations are hypotheses, not measured fixes.',
           'rows': rows}
(HERE / 'audit.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

# Source-only evidence crops. Raw PDFs stay outside Git.
out = HERE / 'evidence'
out.mkdir(exist_ok=True)
def crop(ident, page, box200, filename):
    with pymupdf.open(SOURCES / f'{ident}.pdf') as pdf:
        rect = pymupdf.Rect(*(n * 72 / 200 for n in box200))
        pix = pdf[page - 1].get_pixmap(dpi=300, clip=rect)
        pix.save(out / filename)
for i, ref in enumerate(refs['table_rows'][:6]):
    crop('thai-gazette', ref['page'], gazette[i]['row_box_200'], f'gazette-row-{i+1}.png')
crop('us-census', 2, [203, 380, 922, 428], 'census-adams-alexander.png')
crop('us-census', 2, [203, 678, 922, 716], 'census-cook.png')
crop('us-census', 3, [145, 666, 921, 697], 'census-woodford.png')
crop('us-preservation', 3, [51, 1543, 960, 1603], 'preservation-portland-san-diego.png')
for page in [1, 2, 3]:
    with pymupdf.open(SOURCES / 'thai-gazette.pdf') as pdf:
        im = pdf[page-1].get_pixmap(dpi=150).pil_image().convert('RGB')
    draw = ImageDraw.Draw(im)
    for i, region in enumerate(pages['thai-gazette'][page-1]['regions']):
        if region['block_label'] in {'text', 'content', 'table'}:
            box = [v / 2 for v in region['block_bbox']]
            draw.rectangle(box, outline='#0069b4', width=2)
            draw.text((box[0], box[1]), str(i), fill='#0069b4')
    for i, ref in enumerate(refs['table_rows'][:6]):
        if ref['page'] == page:
            box = [v * .75 for v in gazette[i]['digit_box_200']]
            draw.rectangle(box, outline='#dc2626', width=2)
    im.save(out / f'gazette-p{page}-region-overlay.png')
print(json.dumps({k:v for k,v in summary.items() if k != 'rows'}, ensure_ascii=False, indent=2))
