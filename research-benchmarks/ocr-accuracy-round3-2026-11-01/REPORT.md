# รอบ 3: ความละเอียดต้นฉบับและตารางแบ่งช่วงแถว

ก่อน `633aa9d32648e68813b33dfcdf10f54e8849a2a4`; หลัง `1ce4459919b06af93f2b7174ba16e6d0c099319a`

วัดก่อนและหลังใหม่ทั้งคู่บน Mac เครื่องเดิม เอกสารเดิม 4 ไฟล์ × 3 หน้า × auto/forced OCR รวม 16 timed reads ปิดแคชทั้ง document/page ผลทุกไฟล์ต้องมี source SHA-256 ตรง manifest เดิม เฉลย 24 ช่วงข้อความและ 15 แถวไม่เปลี่ยน

หลังแก้ใช้ภาพ OCR ไม่เกิน 300 DPI โดยลด DPI เมื่อจำเป็นให้อยู่ใน 12MP/20MiB ส่วนตารางหนาแน่นแบ่งเป็นช่วงตามช่องว่างของภาพ เก็บทุกพิกเซลต่อเนื่อง ไม่ซ้ำหรือข้ามช่วง แต่ละช่วงต้องจบปกติและจำนวนคอลัมน์สูงสุดต้องตรงกันก่อนประกอบ OTSL คืนให้ Paddle

ยังใช้ PaddleOCR-VL-1.6/MLX revision เดิม, 8192 tokens, serialization และ repetition guard เดิม ไม่มีการแก้ตัวเลขจาก dictionary/เฉลย ไม่มี route ตามชื่อไฟล์หรือแถวที่ใช้วัด CPU/grid OCR ที่ทดลองยังไม่เปิดใน candidate นี้

ทั้งสองฝั่งใช้ max_chars=40000 และ source/page bounds เดิม รีเซ็ต MLX และอุ่นเครื่องด้วย English PNG เดียวกันก่อนแต่ละรุ่น เวลาไม่รวม upload แต่รวม render/อ่านภาพ/ประกอบผลและ polling ไม่ใช้ Firecrawl หรือ external upload ไม่ขึ้น main

![เวลาและหน่วยความจำ](comparison.png)

## เส้นทางอัตโนมัติ

| เอกสาร | ก่อน วินาที | หลัง วินาที | ส่งครบก่อน / หลัง | sampled CER ก่อน / หลัง | แถวตรงก่อน / หลัง |
|---|---:|---:|---|---|---|
| thai-gazette | 23.02 | 24.69 | ปฏิเสธ / ครบตามเกณฑ์จบ | ปฏิเสธผล / 7.99% | 0/6 / 0/6 |
| thai-royal | 53.62 | 68.03 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 8.04% / 12.97% | 0/0 / 0/0 |
| us-census | 0.23 | 0.24 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 0.67% / 0.67% | 1/6 / 1/6 |
| us-preservation | 0.32 | 0.33 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 14.09% / 14.09% | 0/3 / 0/3 |

## บังคับ OCR

| เอกสาร | ก่อน วินาที | หลัง วินาที | ส่งครบก่อน / หลัง | sampled CER ก่อน / หลัง | แถวตรงก่อน / หลัง |
|---|---:|---:|---|---|---|
| thai-gazette | 22.93 | 24.68 | ปฏิเสธ / ครบตามเกณฑ์จบ | ปฏิเสธผล / 7.99% | 0/6 / 0/6 |
| thai-royal | 54.08 | 68.82 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 8.04% / 12.97% | 0/0 / 0/0 |
| us-census | 101.58 | 25.81 | ครบตามเกณฑ์จบ / ปฏิเสธ | 1.11% / ปฏิเสธผล | 1/6 / 0/6 |
| us-preservation | 33.79 | 47.96 | ครบตามเกณฑ์จบ / ครบตามเกณฑ์จบ | 7.45% / 7.45% | 2/3 / 2/3 |

## ภาพรวมและแรม

| รุ่น / โหมด | ส่งครบ | median วินาที รวม failures | strict rows | native RSS peak GiB |
|---|---:|---:|---|---:|
| before / auto | 3/4 | 11.67 | 1/15 | 3.49 |
| before / ocr | 3/4 | 43.94 | 3/15 | 3.80 |
| after / auto | 4/4 | 12.51 | 1/15 | 3.77 |
| after / ocr | 3/4 | 36.89 | 2/15 | 4.24 |

## รายละเอียดการ render และแบ่งตาราง

| รุ่น / โหมด / เอกสาร | DPI ต่อหน้า | จำนวน bands ต่อ table request | คอลัมน์ต่อ band |
|---|---|---|---|
| after / auto / thai-gazette | [300, 300, 300] | [] | [] |
| after / auto / thai-royal | [252, 252, 252] | [] | [] |
| after / auto / us-census | [] | [] | [] |
| after / auto / us-preservation | [] | [] | [] |
| after / ocr / thai-gazette | [300, 300, 300] | [] | [] |
| after / ocr / thai-royal | [252, 252, 252] | [] | [] |
| after / ocr / us-census | [] | [1] | [[13]] |
| after / ocr / us-preservation | [300, 300, 300] | [2] | [[3, 3]] |
| before / auto / thai-gazette | [] | [] | [] |
| before / auto / thai-royal | [144, 144, 144] | [] | [] |
| before / auto / us-census | [] | [] | [] |
| before / auto / us-preservation | [] | [] | [] |
| before / ocr / thai-gazette | [] | [] | [] |
| before / ocr / thai-royal | [144, 144, 144] | [] | [] |
| before / ocr / us-census | [144, 144, 144] | [] | [] |
| before / ocr / us-preservation | [144, 144, 144] | [] | [] |

## ขอบเขตและสถานะ

ส่งครบตามเกณฑ์หมายถึงไม่มีการตัด API และผ่าน completion checks ของทุกช่วงที่อ่าน ไม่ใช่คำรับรองว่าตัวอักษรถูกทั้งหมดหรือ layout พบทุกบริเวณ เก็บ page/region provenance และ metadata ทุก band ไว้ใน telemetry

sampled CER ใช้ข้อความอ้างอิงเดิม 24 ช่วง, normalization และ edlib HW เดิม ไม่ใช่ full-document CER หรือ hallucination score ทั้งเอกสาร ค่าเฉลี่ยเฉพาะไฟล์ที่ผ่านต่าง subset เปรียบเทียบตรง ๆ ไม่ได้ จึงแสดงรายไฟล์และ strict row tuples 15 แถวด้วย

Auto เอกสารอังกฤษยังใช้ text layer เดิมตาม routing; ข้อมูลใน text layer ไม่ได้ถูกนำมาเติมคำตอบ forced OCR คะแนน auto กับ forced แยกกัน ผลผิด/ถูกตัด/ไม่จบคงอยู่ในผลดิบ ไม่ทิ้ง failed outputs

แต่ละเอกสาร/โหมด/รุ่นมีหนึ่ง observation บน development corpus เดิมที่ใช้วิเคราะห์ failure ไม่ใช่ผลทางสถิติหรือ holdout การเปลี่ยน ROI/batching มีความแปรผันแม้ temperature=0 Native RSS ไม่ใช่ Metal allocation ทั้งหมด และ host memory มี background apps

CPU recognizer/grid pilots แสดงไว้แยกเพื่อบันทึกแนวทางที่ยังไม่ผ่าน: ภาพ 144 DPI และ segmentation ที่ตัดผ่านตัวเลขให้ผลผิด ข้อมูลเหล่านี้ไม่ได้ใช้เติมหรือแก้ primary output ภาพ overlay แสดงการตรวจ geometry ตัวทดลองเหล่านี้ไม่ถูกเรียกใน runtime candidate

ผลที่นำมาวัดจริงอยู่ใน results/*.json, telemetry.jsonl และ memory.jsonl; METHOD.md ตรึงวิธีวัดและ reference-lock.json ล็อกเฉลยเดิม SOURCE.md/SOURCES.md บันทึกที่มา งานทั้งหมดอยู่ใน branch ทดลอง ไม่มีการ merge main และคืน production ตาม restored.json
