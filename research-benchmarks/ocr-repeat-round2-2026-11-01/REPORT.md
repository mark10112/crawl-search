# รอบสอง: คุมการวนซ้ำและส่งผล OCR ให้ครบ

Before `27466cae9c17ab3427295d0c64cc1b93556e551c`; after `2324ae3dbd260f155f90354710f6a6f209d11ca0`

เอกสารเดิม 4 ไฟล์ ไฟล์ละ 3 หน้า: auto และ forced OCR รวม 16 คำขอ timed ปิด result cache ทั้งหมด รีเซ็ต MLX/อุ่นเครื่องแบบเดิมก่อนแต่ละรุ่น ไม่มี Firecrawl ไม่ขึ้น main

Before เป็น candidate 8,192 โทเคนของรอบแรก ไม่ใช่ production 4,096 รุ่นเก่า วัด baseline ใหม่ในรอบนี้เพื่อไม่ปะปนเวลาแต่ละสภาพเครื่อง

After ส่ง repetition_penalty=1.05/context=64 โดยยังใช้ 8192 โทเคน ไม่ลบข้อความซ้ำ ไม่ผ่อน completion checks และลด presentation attributes ใน HTML ตารางโดยคงข้อความ/เซลล์/rowspan/colspan ส่วน API เพิ่ม max_chars=0 เพื่อส่งครบ และ output_complete สำหรับแยก preview

Primary A/B ยังคง max_chars=40000 ทั้งสองฝั่ง การส่งครบในผลนี้จึงต้องเกิดภายในงบเท่ากัน ไม่ใช่เพิ่มเพดานเฉพาะ after

## ข้อค้นพบ

Penalty 1.05 ไม่แก้ Thai length stops: auto ยังคงส่งครบ 2/4 ส่วน forced OCR ส่งครบเพิ่ม 1/4 เป็น 2/4 จากการแก้ HTML/API Census (CER ข้อความที่ส่งจริง 22.64% → 1.50%, แถวตรง 0/6 → 1/6) ไม่ใช้ผลนี้อ้างว่าแก้การวนซ้ำสำเร็จ

Supplemental crop probe ของ Thai royal จบปกติทุกค่า 1.0/1.1/1.15 ภายใน ~2 วินาที แม้ตัว pipeline เดิมจะวน จึงทดลอง serialization ต่อใน ../ocr-serial-round2b-2026-11-01 โดยไม่เลือก penalty สูงขึ้นตามคะแนนอ้างอิง เก็บผล 1.05 ทั้งหมดไว้ ไม่ขึ้น main

![ผลเวลาและหน่วยความจำ](comparison.png)

## เส้นทางอัตโนมัติ

| เอกสาร | ก่อน วินาที | หลัง วินาที | ส่งครบก่อน / หลัง | sampled CER ก่อน / หลัง | แถวตรงก่อน / หลัง | length stops ก่อน / หลัง |
|---|---:|---:|---|---|---|---|
| thai-gazette | 97.72 | 93.15 | ปฏิเสธ / ปฏิเสธ | ปฏิเสธผล / ปฏิเสธผล | 0/6 / 0/6 | 1 / 1 |
| thai-royal | 92.56 | 95.01 | ปฏิเสธ / ปฏิเสธ | ปฏิเสธผล / ปฏิเสธผล | 0/0 / 0/0 | 1 / 2 |
| us-census | 0.24 | 0.22 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 0.67% / 0.67% | 1/6 / 1/6 | 0 / 0 |
| us-preservation | 0.22 | 0.22 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 14.09% / 14.09% | 0/3 / 0/3 | 0 / 0 |
## บังคับ OCR

| เอกสาร | ก่อน วินาที | หลัง วินาที | ส่งครบก่อน / หลัง | sampled CER ก่อน / หลัง | แถวตรงก่อน / หลัง | length stops ก่อน / หลัง |
|---|---:|---:|---|---|---|---|
| thai-gazette | 98.60 | 93.27 | ปฏิเสธ / ปฏิเสธ | ปฏิเสธผล / ปฏิเสธผล | 0/6 / 0/6 | 1 / 1 |
| thai-royal | 93.71 | 95.48 | ปฏิเสธ / ปฏิเสธ | ปฏิเสธผล / ปฏิเสธผล | 0/0 / 0/0 | 1 / 2 |
| us-census | 84.28 | 80.91 | ถูกตัด / ครบตามเกณฑ์จบ | 22.64% / 1.50% | 0/6 / 1/6 | 0 / 0 |
| us-preservation | 23.67 | 22.86 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 7.45% / 7.45% | 2/3 / 2/3 | 0 / 0 |

## สรุปและหน่วยความจำ

| รุ่น / โหมด | reader ok | ส่งครบ | median วินาทีรวม failures | penalty-inclusive CER | แถวตรง | native RSS peak GiB |
|---|---:|---:|---:|---:|---|---:|
| before / auto | 2/4 | 2/4 | 46.40 | 53.69% | 1/15 | 3.39 |
| before / ocr | 2/4 | 1/4 | 88.99 | 57.52% | 2/15 | 3.42 |
| after / auto | 2/4 | 2/4 | 46.69 | 53.69% | 1/15 | 3.40 |
| after / ocr | 2/4 | 2/4 | 87.09 | 52.23% | 3/15 | 3.45 |

## การตรวจผล

| รุ่น / โหมด / ไฟล์ | chars ส่งจริง | API ตัด | normal pages | regions ต่อหน้าที่สังเกต | งบส่งจริง | penalty ส่งจริง |
|---|---:|---|---:|---|---|---|
| after / auto / thai-gazette | 0 | False | 2 | [13, 12, 12] | [8192] | [1.05] |
| after / auto / thai-royal | 0 | False | 0 | [5] | [8192] | [1.05] |
| after / auto / us-census | 23185 | False | 0 | [] | [] | [] |
| after / auto / us-preservation | 7993 | False | 0 | [] | [] | [] |
| after / ocr / thai-gazette | 0 | False | 2 | [13, 12, 12] | [8192] | [1.05] |
| after / ocr / thai-royal | 0 | False | 0 | [5] | [8192] | [1.05] |
| after / ocr / us-census | 27505 | False | 3 | [13, 8, 11] | [8192] | [1.05] |
| after / ocr / us-preservation | 10085 | False | 3 | [11, 7, 12] | [8192] | [1.05] |
| before / auto / thai-gazette | 0 | False | 2 | [13, 12, 12] | [8192] | [None] |
| before / auto / thai-royal | 0 | False | 0 | [5] | [8192] | [None] |
| before / auto / us-census | 23185 | False | 0 | [] | [] | [] |
| before / auto / us-preservation | 7993 | False | 0 | [] | [] | [] |
| before / ocr / thai-gazette | 0 | False | 2 | [13, 12, 12] | [8192] | [None] |
| before / ocr / thai-royal | 0 | False | 0 | [5] | [8192] | [None] |
| before / ocr / us-census | 40000 | True | 3 | [13, 8, 11] | [8192] | [None] |
| before / ocr / us-preservation | 21287 | False | 3 | [11, 7, 12] | [8192] | [None] |

## ขอบเขตการแปลผล

ส่งครบตามเกณฑ์จบหมายถึง reader ok ไม่มีการตัดตัวอักษร และ OCR ผ่าน completion checks; ไม่ได้รับประกันว่าถอดทุกคำถูกหรือ layout ตรวจพบทุกบริเวณ เก็บ page/region provenance ใน telemetry และเทียบจำนวนบริเวณประกอบ ผล reject ไม่ถูกนับเป็น transcript ผ่าน

sampled CER คือ 24 ช่วงข้อความอ้างอิงเดิม ใช้ normalization/edlib HW เดิม ไม่ใช่ CER ทั้งเอกสารหรือคะแนนตรวจ hallucination ทุกจุด ตารางใช้ strict row tuples 15 แถวเดิม ไม่มีการเปลี่ยนเฉลยตามผลทดลอง ผลที่ reader ปฏิเสธมี penalty 100% ส่วน output ที่ถูก API ตัดคงแสดงคะแนนของข้อความที่ส่งจริงและทำเครื่องหมายไม่ครบ

Auto อังกฤษใช้ text layer จึงไม่ใช่ความเร็ว recognition ใหม่ Median รวม failures; accepted CER เปรียบเทียบได้เฉพาะเอกสารเดียวกัน ไม่ใช้ค่าเฉลี่ยคนละ subset สรุปว่าดีขึ้น

เป็น A/B ครั้งเดียวต่อเอกสาร/โหมด ไม่ใช่ข้อสรุปทางสถิติ MLX region batching มีความแปรผันแม้ temperature=0 Native RSS ไม่ใช่ Metal allocation ทั้งหมดหรือ RAM เฉพาะโมเดล และ host memory มี background apps

compaction-replay.json เป็นการพิสูจน์แยกบน Census ของรอบแรกว่า plain text และโครงสร้างตารางไม่เปลี่ยนจากการตัด presentation attributes ไม่ใช่การอนุมานใหม่หรือเอาผลเก่ามาแทนผล benchmark

ยังไม่ขึ้น main ระหว่างการทดลอง ต้องประเมินคุณภาพจากหลักฐานก่อน Production คืนรุ่นเดิมตาม restored.json

ไฟล์หลัก: METHOD.md, run_ab.py, observe_worker.py, analyze.py, results/*.json, telemetry.jsonl, memory.jsonl; reference-lock.json ล็อกเฉลยเดิม
