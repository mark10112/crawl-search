# ผลทดสอบ Local Research Router เทียบ Firecrawl — 1 พฤศจิกายน 2026

ระบบต่อครบและวัดกับ Firecrawl จริงแล้ว: ชุดหลัก 17 เอกสาร × 3 สถานะแคช × 2 ระบบ = 102 คำขอสำเร็จทั้งหมด เพิ่มโหมด local-quality อีก 17 คำขอ และการตรวจภาษา/ส่งต่ออีก 3 คำขอ Firecrawl ไม่มีการประมาณเครดิตแทนใบเสร็จจริง

## ความเร็ว ความแม่น และเครดิต

| ระบบ | แคช | เอกสาร | p50 วินาที | p95 วินาที | CER เฉลี่ย ↓ | cache hit | เครดิต Firecrawl |
|---|---|---:|---:|---:|---:|---:|---:|
| local | off | 17 | 1.442 | 4.726 | 1.34% | 0 | 0 |
| local | prime | 17 | 1.478 | 4.482 | 1.34% | 0 | 0 |
| local | hit | 17 | 0.009 | 0.018 | 1.34% | 17 | 0 |
| local-quality | off | 17 | 4.355 | 11.315 | 0.41% | 0 | 0 |
| firecrawl | off | 17 | 5.511 | 7.961 | 4.91% | 0 | 17 |
| firecrawl | prime | 17 | 3.203 | 8.870 | 4.91% | 0 | 17 |
| firecrawl | hit | 17 | 2.099 | 2.354 | 4.91% | 17 | 17 |

off = ปิด result cache; prime = เปิดแคชและอ่านครั้งแรก; hit = อ่าน URL/options เดิมซ้ำ ตรวจยืนยัน hit จาก metadata ไม่ได้เดาจากความเร็ว โมเดลและ browser โหลดไว้แล้วทุกกลุ่ม จึงไม่ใช่ cold model startup

Local balanced อ่าน fresh เร็วกว่า Firecrawl ประมาณ 3.8 เท่าในชุดนี้ แต่ local วัดผ่าน HTTP loopback ส่วน Firecrawl วัดผ่าน connected tool รวม gateway/service transport ต่างกัน จึงเป็นเวลาที่ผู้ใช้ deployment นี้ได้รับ ไม่ใช่การเทียบ inference engine ล้วน p95 ของ 17 ตัวอย่างเป็น nearest-rank ซึ่งเท่ากับค่าสูงสุด ไม่มีการทำซ้ำหลายรอบต่อสถานะหรือสลับลำดับแบบสุ่ม จึงไม่ใช่ SLA หรือผลเชิงนัยสำคัญ

## ความแม่นต้องดูแยกชนิดเอกสาร

CER คือจำนวนแก้ไขตัวอักษรเทียบข้อความอ้างอิง หารจำนวนตัวอักษรอ้างอิง ยิ่งต่ำยิ่งดี รายงานเป็นค่าเฉลี่ยต่อเอกสาร ไม่ใช่เปอร์เซ็นต์คำตอบถูก ลบ whitespace/Markdown decoration และ normalize Unicode NFC เหมือนกันทั้งสองระบบ แต่ยังนับตัวเลข วรรคตอน ตัวพิมพ์และเครื่องหมายภาษา

เอกสารสะอาดภาษาเดียว 8 หน้า:

| ระบบ | CER เฉลี่ย |
|---|---:|
| local | 1.85% |
| local-quality | 0.19% |
| firecrawl | 0.87% |

Firecrawl แม่นกว่า balanced ในกลุ่มสะอาดภาษาเดียว ส่วนภาพรวม Firecrawl ผิดหนักในสองหน้าไทยปนอังกฤษ: CER 37.91% และ 38.56% มีข้อความไทยที่ไม่ตรงต้นฉบับ ขณะที่ local balanced สองหน้านี้ 1.96% ทั้งคู่ ทดลอง Firecrawl เพิ่ม language preference th/en อีกสองคำขอได้ข้อความเดิม ไม่แทนที่ baseline; ตัวเลือกนี้ไม่ได้รับประกันการควบคุมภาษา OCR โดยตรง

โหมด quality ใช้ LightOn ทุกหน้าที่ต้อง OCR: CER รวม 0.41%, เฉพาะ 13 PDF สแกน 0.54%; p50 ทั้งชุด 4.36 วินาที และ p95 11.31 วินาที จึงแลกความเร็วกับความแม่นชัดเจน ไม่ควรสรุปว่าโมเดลใดชนะทุกเอกสาร ตารางรายเอกสารอยู่ [results/analysis.md](results/analysis.md)

## ชุดเอกสารและความเป็นธรรม

- ใช้ URL และไฟล์เดียวกันทั้งสองระบบ: 13 PDF สแกนหน้าเดียว, HTML ธรรมดา 2 ภาษา, เว็บ JavaScript 1 และ PDF มี text layer 1
- ภาษาภาพสแกน: อังกฤษ ฝรั่งเศส เยอรมัน ไทย จีน ญี่ปุ่น อาหรับ ฮินดี รวมหน้าผสมภาษาและภาพเสื่อมคุณภาพ ข้อความอ้างอิงเขียนไว้ก่อนและไม่ได้ส่งให้ reader
- ภาพ OCR ฝังใน PDF แบบ lossless ไม่มี hidden text; source SHA-256 ของ local ตรง manifest ทั้งหมด Firecrawl ได้ URL ไฟล์เดียวกันผ่าน tunnel ที่ให้บริการเฉพาะ fixture ไม่มีไฟล์นิยาย/ข้อมูลลับ
- ข้อความสั้น หน้าเดียว layout เรียบ เป็น synthetic corpus ไม่ครอบคลุมลายมือ ตารางซับซ้อน สมุดไทย เอกสารประวัติศาสตร์จริง หรือการค้นหาเว็บ; การสรุปผลจำกัดอยู่ในชุดนี้
- เครื่อง i5-12400F, RAM 16 GiB, RTX 4060 8 GiB; LightOnOCR-2-1B revision be7c41313c30e940fe5571de59e5fabc779e00c8, RapidOCR 3.10.0 รายละเอียด gate/cache/transport อยู่ [METHOD.md](METHOD.md)

## เครดิตจริงและ fallback

Account balance details omitted from the public Git snapshot. Per-call benchmark credit totals are preserved.

Firecrawl cache hit ทั้ง 17 คำขอยังคิด 1 เครดิตต่อชิ้นในครั้งนี้ การเก็บผล Firecrawl กลับเข้า local cache จึงช่วยลดการเรียกเสียเครดิตซ้ำได้จริง

ทดสอบ local/browser outage แบบควบคุม → agent เรียก connected Firecrawl → complete_fallback → อ่าน URL เดิมจาก local cache ผ่านจริง คำขอแรก 1 เครดิต อ่านซ้ำ 0 เครดิต เส้นทางนี้เป็น client-agent handoff ต้องมี agent เรียกเครื่องมือที่ส่งกลับ ไม่ใช่ backend แอบดึง credential แล้วเรียก cloud เอง ผลอยู่ [results/fallback-integration.json](results/fallback-integration.json) ไม่รวมการจำลอง outage ในตารางความเร็วหลัก

## การใช้และตรวจซ้ำ

ใช้ balanced สำหรับอ่านกว้าง ๆ; quality สำหรับหลายภาษา/งานที่ต้องตรวจตัวเลขและชื่ออย่างจริงจัง และกลับดูต้นฉบับเมื่อข้อมูลสำคัญ confidence gate ยังปล่อยข้อความผิดได้ เช่น อาหรับของ balanced ในชุดนี้

ตรวจ unit/integration tests ผ่าน 15/15 และเรียก MCP stdio จริงเห็นเครื่องมือครบห้าตัว รวม research_complete_fallback; อ่าน PDF ผ่าน router:lighton สำเร็จ ช่องทาง tunnel และ HTTP fixture/benchmark server ปิดแล้ว คงบริการ SearXNG และ OCR ไว้ใช้จริง

อ่าน [README ของแพ็กเกจ](../../research-tools/local-research/README.md) และ [ROUTER-V2.md](../../research-tools/local-research/ROUTER-V2.md) สำหรับการติดตั้ง/ขอบเขต ผลดิบรายคำขออยู่ results/; manifest มี reference และ hash; fixtures.py, local_benchmark.py, analyze.py, report.py เป็นสคริปต์ประกอบ ข้อมูล Firecrawl เป็นผลเรียก connected tool ที่บันทึกจริง การรันทดสอบ cloud ซ้ำต้องเปิด public fixture endpoint ใหม่และใช้เครดิตเพิ่ม URL tunnel เดิมถูกปิดหลังจบงาน
