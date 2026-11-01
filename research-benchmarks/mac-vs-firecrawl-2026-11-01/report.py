import json,statistics
from pathlib import Path
R=Path(__file__).resolve().parent
data=json.loads((R/'results/analysis.json').read_text());rows=data['rows'];summaries=data['summaries']
def sec(value):return f'{value/1000:.2f}'
def cer(row):return f"{row['accepted_cer_pct']:.2f}%" if row['ok'] else 'ปฏิเสธผล'
def gib(value):return f'{value/1024**3:.2f}' if value is not None else 'วัดไม่ได้'
def find(provider,phase,ident):return next(r for r in rows if (r['provider'],r['phase'],r['id'])==(provider,phase,ident))
lines=['# Benchmark Mac mini M4 เทียบ Firecrawl — เอกสารประวัติศาสตร์ชุดเดิม',
'','ทดสอบ 1 พฤศจิกายน 2026: PDF เดิม 4 ไฟล์ × 3 หน้า รวม 12 หน้า ตรวจ SHA-256 ตรงกับ manifest ทุกคำขอ Mac ใช้ PaddleOCR-VL 1.6 ผ่าน MLX/Metal และ text layer เดิมตาม production router ไม่มีการปรับโมเดลระหว่างรัน เฉลย/ตัวอย่างตารางชุดเดิมไม่เปลี่ยน',
'','## อ่านสด ปิดแคชผลลัพธ์',
'','| เอกสารสามหน้า | Mac วินาที | Mac สถานะ / sampled CER ↓ | Firecrawl วินาที | Firecrawl sampled CER ↓ | แถวตรง Mac / Firecrawl |',
'|---|---:|---|---:|---:|---:|']
ids=['thai-gazette','thai-royal','us-census','us-preservation']
for ident in ids:
    a=find('mac','off',ident);b=find('firecrawl','off',ident)
    lines.append(f"| {ident} | {sec(a['elapsed_ms'])} | {cer(a)} | {sec(b['elapsed_ms'])} | {cer(b)} | {a['table_correct']}/{a['table_total']} / {b['table_correct']}/{b['table_total']} |")
lines+=['','Mac อ่านไฟล์อังกฤษสองชุดด้วย OCR/text layer ที่ฝังเดิม ไม่ใช่ความเร็วของ Paddle OCR ใหม่ สแกนไทยทั้งสองชุดในรอบ off ถูกปฏิเสธเนื่องจาก generation ไม่จบตามปกติ จึงไม่มี CER ของผลที่ยอมรับสำหรับสองชุดนั้น ไม่อ้างว่าเนื้อหาทุกตัวผิด 100%',
'','## แยกปิดแคช / เติมแคช / อ่านซ้ำ',
'','| ระบบ | รอบ | ผ่าน | p50 ทุกคำขอ วินาที | p50 เฉพาะที่ผ่าน วินาที | result-cache hit | sampled CER เฉพาะที่ผ่าน ↓ | แถวตรงทั้งหมด |',
'|---|---|---:|---:|---:|---:|---:|---:|']
for s in summaries:
    if s['provider']=='mac-forced-quality':continue
    label={'off':'ปิดแคช','prime':'เปิดครั้งแรก','hit':'อ่านซ้ำ'}[s['phase']]
    lines.append(f"| {s['provider']} | {label} | {s['ok']}/{s['n']} | {sec(s['p50_ms'])} | {sec(s['accepted_p50_ms']) if s['accepted_p50_ms'] else '—'} | {s['cache_hits']}/{s['n']} | {s['accepted_cer_pct']:.2f}% | {s['table_correct']}/{s['table_total']} |")
lines+=['','p50 รวมความล้มเหลวแสดงเวลาที่ต้องรอก่อนทราบว่าทำไม่ได้ ไม่ใช่ความเร็วในการส่งผลสำเร็จ CER เฉพาะผลที่ผ่านของแต่ละระบบอาจเป็นคนละชุดเอกสาร จึงต้องดูตารางรายไฟล์ประกอบ ห้ามเทียบค่าเฉลี่ยนี้โดยละเลย coverage',
'','รอบอ่านซ้ำ Mac: ไฟล์อังกฤษเป็น result-cache hit จริงสองไฟล์ ส่วน thai-gazette ผ่านหลังอ่านซ้ำแต่ result_cache=false และ page cache=[true,true,false] คือใช้สองหน้าที่เคยทำสำเร็จแล้วและทำหน้าที่เหลือใหม่ thai-royal ยังไม่ผ่าน จึงห้ามสรุปว่าทุกไฟล์อ่านจากแคชได้เร็ว รอบนี้ไม่มีการบังคับให้แคชข้อผิดพลาด',
'','## บังคับ OCR ใหม่ ไม่ใช้ text layer',
'','| เอกสาร | Mac วินาที | สถานะ / sampled CER ↓ | แถวตรง |',
'|---|---:|---|---:|']
for ident in ids:
    a=find('mac-forced-quality','off',ident)
    lines.append(f"| {ident} | {sec(a['elapsed_ms'])} | {cer(a)} | {a['table_correct']}/{a['table_total']} |")
lines+=['','balanced และ quality ปัจจุบันใช้โมเดล/พารามิเตอร์เดียวกัน ผลเสริมจึงไม่ได้พิสูจน์ว่าคุณภาพต่างเพราะ policy ความต่างเกิดร่วมกับลำดับงาน การประมวลผลซ้ำ และสถานะแคชภายใน MLX ซึ่งไม่ได้ปิด โมเดล temperature=0 ก็ไม่ได้ทำให้ยืนยันผลคงที่ได้ในบริการที่ batch บริเวณภาพ',
'','## แรมบน Mac 16 GiB',
'','| รอบ Mac | native OCR/MLX/API RSS สูงสุด GiB | RAM ทั้งเครื่องที่ไม่ free สูงสุด GiB | compressor สูงสุด GiB | available ต่ำสุด GiB | swap-out ระหว่างคำขอ MiB |',
'|---|---:|---:|---:|---:|---:|']
for s in summaries:
    if not s['provider'].startswith('mac'):continue
    lines.append(f"| {s['provider']} / {s['phase']} | {gib(s['native_rss_peak'])} | {gib(s['system_nonfree_peak'])} | {gib(s['compressor_peak'])} | {gib(s['available_min'])} | {s['swap_out_delta']/1024**2:.2f} |")
lines+=['','RSS เป็นผลรวมโปรเซส OCR, MLX และ API รวม gateway ทดสอบ/production ที่ idle ไม่รวม Docker VM และแอปอื่น RSS อาจนับ shared memory ซ้ำและไม่ใช่ MLX allocation ทั้งหมด จึงไม่ใช่ขนาด RAM ที่โมเดลใช้เพียงตัวเดียว',
'','RAM ทั้งเครื่องที่ไม่ free มาจาก vm_stat และรวม file cache ที่เรียกคืนได้ จึงห้ามตีความว่าค่าใกล้ 16 GiB หมายถึงทุกไบต์เป็นแรมที่จำเป็นของระบบนี้ compressor อยู่ใน RAM ทั้งเครื่องแล้ว ห้ามนำมาบวกซ้ำ ใช้ available และ swap ประกอบ มีแอปพื้นหลัง/Docker/Ollama อยู่ตามสภาพเซิร์ฟเวอร์ ไม่ได้กัน RAM แบบ hard isolation',
'','เก็บตัวอย่างทุก 0.5 วินาที คำขอ cache hit ที่สั้นกว่านั้นบางรายการใช้ตัวอย่างก่อน/หลังและระบุไว้ใน analysis.json ไม่ใช่ peak ที่รับรองว่าจับได้ทุก spike แรมเซิร์ฟเวอร์ Firecrawl วัดไม่ได้ผ่าน connected API จึงรายงาน N/A ไม่ใช่ศูนย์',
'','## สาเหตุที่ตรวจพบ',
'','Backend log มี finish_reason=length และ generated_tokens=4096 สำหรับงานที่ถูกปฏิเสธ ตัวครอบตั้งเพดานสูงสุด 8192 แต่ไม่ขยายงบของ request ที่ส่งมาน้อยกว่าเพดานนั้น จึงไม่ควรอ้างว่าทดสอบได้งบ 8192 จริงทุก region ไม่มีการแก้เพดานระหว่าง benchmark; ดู backend-completions.json',
'','เกณฑ์การจบช่วยกันข้อความขาด แต่ไม่ได้รับประกันความแม่น: ผลที่ผ่านยังอาจผิดตัวเลข/ชื่อ/ความสัมพันธ์ตาราง ส่วนไฟล์อังกฤษที่อ่าน text layer เดิมยังมีข้อผิดพลาดที่อยู่ในไฟล์ต้นฉบับ การบังคับ OCR ใหม่ยังไม่ใช่คำตอบที่ดีสำหรับทุกเอกสาร',
'','## วิธีวัดและข้อจำกัด',
'','ใช้ sampled spans 24 ช่วงและ strict row tuples 15 แถวจากภาพชุดเดิม: Unicode NFC, ลบรูปแบบ/whitespace, edlib HW semiglobal Levenshtein, normalize ค่าเลขไทยเหมือน baseline ตัวเลขนี้ไม่ใช่ CER ทั้งเอกสารหรือ TEDS การหา best substring มองไม่เห็นข้อความแต่งเพิ่มนอกช่วงที่เลือก เฉลยเป็น single-reviewer pilot ไม่ใช่ gold ที่มีมนุษย์ตรวจอิสระ',
'','analysis.json แยก accepted_cer_pct ออกจาก delivery_penalty_error_pct: แบบหลังให้ผลที่ถูกปฏิเสธเป็นโทษ 100% เพื่อไม่ตัดความล้มเหลวทิ้ง ไม่เรียกค่านี้ว่า CER ของข้อความจริง',
'','Mac วัดผ่าน HTTP submit/poll บน Mac จนได้ JSON เต็ม Firecrawl วัด connected tool เต็มคำขอบน Windows มี overhead คนละเส้นทาง ค่าที่แสดงไม่ใช่ inference ล้วน และ MCP ที่ใช้งานจริงอาจมี polling/SSH เพิ่ม ชุดนี้สังเกตครั้งเดียวต่อไฟล์ต่อรอบ n=4 ไม่ใช่ p95/SLA',
'','คำว่า off หมายถึง cache ผลลัพธ์เอกสาร/หน้า ไม่ได้ restart โมเดล ไม่ปิด KV/prompt cache ภายใน MLX และไม่ควบคุม parser cache ภายใน Firecrawl ตรวจ GET ที่ fixture origin ประกอบกับ cache metadata ไม่รับรองว่า cloud backend คำนวณ OCR ใหม่จากศูนย์',
'','Firecrawl รายงาน creditsUsed=3 ต่อคำขอ รวม 36 ตาม metadata และ feedback ส่งผลคืนเครดิต 12 แต่ยอดคงเหลือที่ API คืนไม่สะท้อนยอดหัก 36 อย่างสอดคล้องกัน จึงไม่อ้างว่าเสียสุทธิ 24 หรือ 36 เครดิตจริงจากบัญชี เก็บ receipt/ยอดตรวจไว้แยกจาก Git และให้ถือยอด billing จริงเป็นหลัก',
'','ไฟล์หลัก: METHOD.md, reference-lock.json, analyze.py, results/analysis.json, memory.jsonl, origin-requests.jsonl, backend-completions.json และผลดิบต่อคำขอ ปิดเฉพาะ gateway/tunnel/fixture/sampler ชั่วคราวหลังจบและตรวจ production health; ดู cleanup.json เอกสาร/ภาพต้นฉบับอ้าง URL และช่วงหน้าใน real-history-2026-11-01/catalog.json ไม่มีการแก้ไฟล์นิยายหรือเฉลย']
(R/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(R/'REPORT.md')
