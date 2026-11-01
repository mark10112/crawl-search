"""Generate round-three report from unchanged-reference paired observations."""
import json
from pathlib import Path
P=Path(__file__).parent;A=json.loads((P/'results/analysis.json').read_text(encoding='utf8'));S=json.loads((P/'results/started.json').read_text())
lines=['# รอบ 3c: รักษา dot leaders และรายละเอียดตารางโดยไม่แก้ค่าจากเฉลย','',f"ก่อน `{S['before_sha']}`; หลัง `{S['after_sha']}`",'',
'ใช้ baseline ใหม่ทั้ง 8 งานจากรอบ 3 ใน turn เดียวกันโดยเก็บไฟล์และ hash เดิม แล้ววัด after ใหม่บน Mac เครื่องเดิม เป็น reused-baseline follow-up ไม่ใช่ paired A/B ใหม่อีกรอบ เอกสารเดิม 4 ไฟล์ × 3 หน้า × auto/forced OCR รวม 16 timed reads ปิดแคชทั้ง document/page ผลทุกไฟล์ต้องมี source SHA-256 ตรง manifest เดิม เฉลย 24 ช่วงข้อความและ 15 แถวไม่เปลี่ยน','',
'หลังแก้ใช้ภาพไม่เกิน 300 DPI สำหรับหน้าเล็ก/หน้ามีเส้นตาราง และคง 144 DPI สำหรับหน้าข้อความใหญ่ เลือกจาก physical geometry/preview rules ไม่ใช่ชื่อไฟล์ โดยยังอยู่ใน 12MP/20MiB ส่วนตารางหนาแน่นแบ่งเป็นช่วงตามช่องว่างของภาพ เก็บทุกพิกเซลต่อเนื่อง ไม่ซ้ำหรือข้ามช่วง แต่ละช่วงต้องจบปกติและคอลัมน์ต้องตรงกัน ถ้าไม่ตรงจะไม่ยอมรับ/ไม่ pad ค่าตัวเลข แต่ขออ่าน table crop เต็มใหม่หนึ่งครั้งและเก็บ attempt ทั้งสองไว้','',
'ยังใช้ PaddleOCR-VL-1.6/MLX revision เดิม, 8192 tokens, serialization และ repetition guard เดิม ไม่มีการแก้ตัวเลขจาก dictionary/เฉลย ไม่มี route ตามชื่อไฟล์หรือแถวที่ใช้วัด guard ยังจับ semantic repeats 20x แต่แยก dot leaders ที่พิมพ์จริงออกจากวงจรตัวเลข โดยมี punctuation-only runaway cap 1024 อักขระ CPU/grid OCR ที่ทดลองยังไม่เปิดใน candidate นี้','',
'ทั้งสองฝั่งใช้ max_chars=40000 และ source/page bounds เดิม รีเซ็ต MLX และอุ่นเครื่องด้วย English PNG เดียวกันก่อนแต่ละรุ่น เวลาไม่รวม upload แต่รวม render/อ่านภาพ/ประกอบผลและ polling เมื่อ detail ไม่ผ่านจึงอ่านหน้าเดิมใหม่อีกครั้งด้วย 144 DPI/baseline profile เพียงครั้งเดียว ไม่เอาผลล้มเหลวมาเปลี่ยนเป็น success เก็บทั้งสอง attempt และรวมต้นทุน retry ในเวลา ไม่ใช้ Firecrawl หรือ external upload ไม่ขึ้น main','',
'![เวลาและหน่วยความจำ](comparison.png)','']
for mode,title in [('auto','เส้นทางอัตโนมัติ'),('ocr','บังคับ OCR')]:
 lines+=['## '+title,'','| เอกสาร | ก่อน วินาที | หลัง วินาที | ส่งครบก่อน / หลัง | sampled CER ก่อน / หลัง | แถวตรงก่อน / หลัง |','|---|---:|---:|---|---|---|']
 for ident in ['thai-gazette','thai-royal','us-census','us-preservation']:
  b=next(r for r in A['rows'] if (r['variant'],r['mode'],r['id'])==('before',mode,ident));a=next(r for r in A['rows'] if (r['variant'],r['mode'],r['id'])==('after',mode,ident))
  def cer(r):return f"{r['accepted_cer_pct']:.2f}%" if r['ok'] else 'ปฏิเสธผล'
  def outcome(r):return 'ครบตามเกณฑ์จบ' if r['complete_output'] else 'API ตัด' if r['ok'] else 'ปฏิเสธ'
  lines.append(f"| {ident} | {b['seconds']:.2f} | {a['seconds']:.2f} | {outcome(b)} / {outcome(a)} | {cer(b)} / {cer(a)} | {b['table_correct']}/{b['table_total']} / {a['table_correct']}/{a['table_total']} |")
 lines+=['']
lines+=['## ภาพรวมและแรม','','| รุ่น / โหมด | ส่งครบ | median วินาที รวม failures | strict rows | native RSS peak GiB |','|---|---:|---:|---|---:|']
for s in A['summaries']:lines.append(f"| {s['variant']} / {s['mode']} | {s['complete_output']}/{s['n']} | {s['median_seconds']:.2f} | {s['table_correct']}/{s['table_total']} | {s['native_rss_peak']/2**30:.2f} |")
lines+=['','## รายละเอียดการ render และแบ่งตาราง','','| รุ่น / โหมด / เอกสาร | DPI ต่อหน้า | จำนวน bands ต่อ table request | คอลัมน์ต่อ band |','|---|---|---|---|']
for r in A['rows']:
 lines.append(f"| {r['variant']} / {r['mode']} / {r['id']} | {r.get('render_dpi',[])} | {r.get('table_band_counts',[])} | {r.get('table_band_columns',[])} |")
lines+=['','## ขอบเขตและสถานะ','',
'ส่งครบตามเกณฑ์หมายถึงไม่มีการตัด API และผ่าน completion checks ของทุกช่วงที่อ่าน ไม่ใช่คำรับรองว่าตัวอักษรถูกทั้งหมดหรือ layout พบทุกบริเวณ เก็บ page/region provenance และ metadata ทุก band ไว้ใน telemetry','',
'sampled CER ใช้ข้อความอ้างอิงเดิม 24 ช่วง, normalization และ edlib HW เดิม ไม่ใช่ full-document CER หรือ hallucination score ทั้งเอกสาร ค่าเฉลี่ยเฉพาะไฟล์ที่ผ่านต่าง subset เปรียบเทียบตรง ๆ ไม่ได้ จึงแสดงรายไฟล์และ strict row tuples 15 แถวด้วย','',
'Auto เอกสารอังกฤษยังใช้ text layer เดิมตาม routing; ข้อมูลใน text layer ไม่ได้ถูกนำมาเติมคำตอบ forced OCR คะแนน auto กับ forced แยกกัน ผลผิด/ถูกตัด/ไม่จบคงอยู่ในผลดิบ ไม่ทิ้ง failed outputs','',
'แต่ละเอกสาร/โหมด/รุ่นมีหนึ่ง observation บน development corpus เดิมที่ใช้วิเคราะห์ failure ไม่ใช่ผลทางสถิติหรือ holdout การเปลี่ยน ROI/batching มีความแปรผันแม้ temperature=0 Native RSS ไม่ใช่ Metal allocation ทั้งหมด และ host memory มี background apps','',
'CPU recognizer/grid pilots แสดงไว้แยกเพื่อบันทึกแนวทางที่ยังไม่ผ่าน: ภาพ 144 DPI และ segmentation ที่ตัดผ่านตัวเลขให้ผลผิด ข้อมูลเหล่านี้ไม่ได้ใช้เติมหรือแก้ primary output ภาพ overlay แสดงการตรวจ geometry ตัวทดลองเหล่านี้ไม่ถูกเรียกใน runtime candidate','',
'ผลที่นำมาวัดจริงอยู่ใน results/*.json, telemetry.jsonl และ memory.jsonl; METHOD.md ตรึงวิธีวัดและ reference-lock.json ล็อกเฉลยเดิม SOURCE.md/SOURCES.md บันทึกที่มา งานทั้งหมดอยู่ใน branch ทดลอง ไม่มีการ merge main และคืน production ตาม restored.json']
(P/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8');print(P/'REPORT.md')
