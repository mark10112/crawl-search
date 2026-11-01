"""Render measured A/B without omitting failures."""
import json
from pathlib import Path
P=Path(__file__).parent
A=json.loads((P/'results/analysis.json').read_text(encoding='utf8'))
S=json.loads((P/'results/started.json').read_text())
lines=['# รอบสองผลสุดท้าย: ตัดวงจรวนซ้ำและส่งผลครบอย่างตรงไปตรงมา','',f"Before `{S['before_sha']}`; after `{S['after_sha']}`",'',
'เอกสารเดิม 4 ไฟล์ ไฟล์ละ 3 หน้า: auto และ forced OCR รวม 16 คำขอ timed ปิด result cache ทั้งหมด รีเซ็ต MLX/อุ่นเครื่องแบบเดิมก่อนแต่ละรุ่น ไม่มี Firecrawl ไม่ขึ้น main','',
'Before เป็น candidate 8,192 โทเคนของรอบแรก ไม่ใช่ production 4,096 รุ่นเก่า ใช้ baseline สดทั้ง 8 งานจากรอบสองใน turn เดียวกันโดยเก็บไฟล์เดิมทุก byte; after วัดใหม่หลัง probe และรีเซ็ต MLX จึงเป็น reused-baseline follow-up ไม่ใช่ fully paired A/B ใหม่','',
'After ส่ง repetition_penalty=1.0/context=64 และ serialize requests พร้อม stream guard ตามเกณฑ์ซ้ำเดิม โดยยังใช้ 8192 โทเคน ไม่ลบข้อความซ้ำ ไม่ผ่อน completion checks และลด presentation attributes ใน HTML ตารางโดยคงข้อความ/เซลล์/rowspan/colspan ส่วน API เพิ่ม max_chars=0 เพื่อส่งครบ และ output_complete สำหรับแยก preview','',
'Primary A/B ยังคง max_chars=40000 ทั้งสองฝั่ง การส่งครบในผลนี้จึงต้องเกิดภายในงบเท่ากัน ไม่ใช่เพิ่มเพดานเฉพาะ after','']
for mode,title in [('auto','เส้นทางอัตโนมัติ'),('ocr','บังคับ OCR')]:
    lines+=['## '+title,'','| เอกสาร | ก่อน วินาที | หลัง วินาที | ส่งครบก่อน / หลัง | sampled CER ก่อน / หลัง | แถวตรงก่อน / หลัง | length stops ก่อน / หลัง |','|---|---:|---:|---|---|---|---|']
    for ident in ['thai-gazette','thai-royal','us-census','us-preservation']:
        b=next(r for r in A['rows'] if r['variant']=='before' and r['mode']==mode and r['id']==ident)
        a=next(r for r in A['rows'] if r['variant']=='after' and r['mode']==mode and r['id']==ident)
        def cer(r):return f"{r['accepted_cer_pct']:.2f}%" if r['ok'] else 'ปฏิเสธผล'
        def complete(r):return 'ครบตามเกณฑ์จบ' if r['complete_output'] else 'ถูกตัด' if r['ok'] else 'ปฏิเสธ'
        lines.append(f"| {ident} | {b['seconds']:.2f} | {a['seconds']:.2f} | {complete(b)} / {complete(a)} | {cer(b)} / {cer(a)} | {b['table_correct']}/{b['table_total']} / {a['table_correct']}/{a['table_total']} | {b['length_stops']} / {a['length_stops']} |")
lines+=['','## สรุปและหน่วยความจำ','','| รุ่น / โหมด | reader ok | ส่งครบ | median วินาทีรวม failures | penalty-inclusive CER | แถวตรง | native RSS peak GiB |','|---|---:|---:|---:|---:|---|---:|']
for s in A['summaries']:
    lines.append(f"| {s['variant']} / {s['mode']} | {s['ok']}/{s['n']} | {s['complete_output']}/{s['n']} | {s['median_seconds']:.2f} | {s['delivery_penalty_pct']:.2f}% | {s['table_correct']}/{s['table_total']} | {s['native_rss_peak']/2**30:.2f} |")
lines+=['','## การตรวจผล','','| รุ่น / โหมด / ไฟล์ | chars ส่งจริง | API ตัด | normal pages | regions ต่อหน้าที่สังเกต | งบส่งจริง | penalty ส่งจริง |','|---|---:|---|---:|---|---|---|']
for r in A['rows']:
    lines.append(f"| {r['variant']} / {r['mode']} / {r['id']} | {r['chars']} | {r['output_truncated']} | {r['normal_pages']} | {r['region_counts']} | {r['sent_limits']} | {r['sent_penalties']} |")
lines+=['','## ขอบเขตการแปลผล','',
'ส่งครบตามเกณฑ์จบหมายถึง reader ok ไม่มีการตัดตัวอักษร และ OCR ผ่าน completion checks; ไม่ได้รับประกันว่าถอดทุกคำถูกหรือ layout ตรวจพบทุกบริเวณ เก็บ page/region provenance ใน telemetry และเทียบจำนวนบริเวณประกอบ ผล reject ไม่ถูกนับเป็น transcript ผ่าน','',
'sampled CER คือ 24 ช่วงข้อความอ้างอิงเดิม ใช้ normalization/edlib HW เดิม ไม่ใช่ CER ทั้งเอกสารหรือคะแนนตรวจ hallucination ทุกจุด ตารางใช้ strict row tuples 15 แถวเดิม ไม่มีการเปลี่ยนเฉลยตามผลทดลอง ผลที่ reader ปฏิเสธมี penalty 100% ส่วน output ที่ถูก API ตัดคงแสดงคะแนนของข้อความที่ส่งจริงและทำเครื่องหมายไม่ครบ','',
'Auto อังกฤษใช้ text layer จึงไม่ใช่ความเร็ว recognition ใหม่ Median รวม failures; accepted CER เปรียบเทียบได้เฉพาะเอกสารเดียวกัน ไม่ใช้ค่าเฉลี่ยคนละ subset สรุปว่าดีขึ้น','',
'เป็น A/B ครั้งเดียวต่อเอกสาร/โหมด ไม่ใช่ข้อสรุปทางสถิติ MLX region batching มีความแปรผันแม้ temperature=0 Native RSS ไม่ใช่ Metal allocation ทั้งหมดหรือ RAM เฉพาะโมเดล และ host memory มี background apps','',
'compaction-replay.json เป็นการพิสูจน์แยกบน Census ของรอบแรกว่า plain text และโครงสร้างตารางไม่เปลี่ยนจากการตัด presentation attributes ไม่ใช่การอนุมานใหม่หรือเอาผลเก่ามาแทนผล benchmark','',
'ยังไม่ขึ้น main ระหว่างการทดลอง ต้องประเมินคุณภาพจากหลักฐานก่อน Production คืนรุ่นเดิมตาม restored.json','',
'ไฟล์หลัก: METHOD.md, run_ab.py, observe_worker.py, analyze.py, results/*.json, telemetry.jsonl, memory.jsonl; reference-lock.json ล็อกเฉลยเดิม']
(P/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(P/'REPORT.md')
