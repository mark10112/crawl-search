# รอบ 5: ตัวอ่านสำรองบน crop เดิม — ยังไม่มีตัวไหนแก้ได้ครบ

**Tesseract best / PSM 7 ดีที่สุดในชุดนี้ แต่ยังถูกเพียงเลขหน้าราชกิจจาฯ 1/6 ช่อง และ Census 1/3 ช่อง** ใช้เวลาอ่านเก้าภาพรวมประมาณ 0.27 วินาทีหลังรอบแรก และ reader RSS สูงสุดประมาณ 109 MiB การเปลี่ยนตัวอ่านบนภาพชุดนี้อย่างเดียวยังไม่ทำให้แม่นพอจะเปิด fallback อัตโนมัติ ไม่มีการเปลี่ยน pipeline หรือขึ้น main

## ผลความแม่น เวลา และแรม

อ่านรอบแรกหนึ่งครั้ง แล้วอ่านซ้ำอีกสามรอบด้วย PNG เดียวกันทุกไบต์ ทุกการตั้งค่าให้ข้อความเดิมทั้งสามรอบ คะแนนด้านล่างจึงเป็นจำนวนช่องที่ถูกคงที่ ไม่ใช่จำนวนครั้งซ้ำ การเทียบรับเฉพาะผลที่จบครบและข้อความทั้งช่องตรงเฉลยเดิม หลังปรับเลขไทย/อารบิกและเครื่องหมายคั่นหลักพันแบบเดิม ไม่เลือกเฉพาะ substring ที่ถูก

| ตัวอ่าน / การตั้งค่า | เลขหน้าไทย /6 | Census /3 | median ต่อภาพ (ms) | median รวมเก้าภาพ (s) | reader RSS peak (MiB) |
|---|---:|---:|---:|---:|---:|
| PaddleOCR-VL-1.6 เดิม | 0/6 | 0/3 | 307.00 | 2.868 | 2096.9 |
| PP-OCRv5 mobile — recognizer อย่างเดียว | 0/6 | 0/3 | 54.91 | 0.498 | 995.0 |
| Tesseract fast / PSM 7 | 0/6 | 0/3 | 16.23 | 0.231 | 61.3 |
| Tesseract best / PSM 7 | 1/6 | 1/3 | 19.43 | 0.273 | 109.1 |
| PP-OCRv5 mobile — detector + recognizer | 0/6 | 1/3 | 61.69 | 0.354 | 1006.2 |
| Tesseract best / PSM 8 | 0/6 | 0/3 | 27.94 | 0.335 | 109.3 |
| Tesseract best / PSM 13 | 0/6 | 0/3 | 27.28 | 0.324 | 109.3 |

PP-OCRv5 แบบ detector + recognizer อ่าน Cook `1,838,735` ถูก ส่วน Tesseract best / PSM 7 อ่าน Woodford `13,282` และเลขหน้า `๓๑` ถูก ไม่มีตัวไหนอ่าน Adams `59,135` ตรงเฉลยได้ในชุดนี้ ห้ามรวมคำตอบที่ถูกของคนละตัวโดยอาศัยเฉลยแล้วอ้างเป็นความแม่นของ fallback ที่ทำงานอัตโนมัติ

เวลารวมเก้าภาพเป็น median ของผลรวมเวลาเรียกอ่านแต่ละภาพในแต่ละ warm pass ไม่รวมการดาวน์โหลด ติดตั้ง ตัวให้คะแนน หรือการเขียน log Tesseract ใช้ CLI ต่อภาพ จึงรวมการสร้างโปรเซสและโหลด language data ต่อภาพแล้ว ไม่ได้เปรียบกับ persistent Tesseract API ที่ยังไม่ได้ทดสอบ

RSS คือผลรวม resident memory ของโปรเซสตัวอ่านและลูก รวม server MLX สำหรับ VL และรวม imports/framework ของ Paddle ตัวเล็ก **ไม่ใช่ Metal/unified memory ทั้งหมด** และอาจนับ shared pages ซ้ำ เริ่มจับ VL หลัง native server ตอบพร้อมแล้ว จึงไม่ครอบคลุม peak ระหว่าง server เริ่มต้นก่อนหน้า CPU readers ปลด MLX ออกจากแรมก่อนวัด มีข้อมูล host available/swap ใน JSONL; swap ที่ใช้อยู่เดิมไม่เพิ่มระหว่างแต่ละ reader phase ห้ามตีความว่าผลรวม RSS เป็นแรมทั้งเครื่องหรือ VRAM ทั้งหมด

## เวลาเริ่มต้นและขอบเขตกระบวนการ

| ตัวอ่าน | ช่วงเตรียมตัวอ่านภายในโปรเซส (s) | รอบแรกเก้าภาพ (s) | หมายเหตุ |
|---|---:|---:|---|
| PaddleOCR-VL-1.6 เดิม | 3.577 | 2.873 | import worker + English warmup; server startup แยก |
| PP-OCRv5 mobile — recognizer อย่างเดียว | 3.124 | 0.569 | imports + โหลดโมเดลไทย/อังกฤษสองชุด |
| Tesseract fast / PSM 7 | รวมในคำสั่งแต่ละภาพ | 0.253 | ไม่มี resident model ข้ามภาพ; OS file cache อุ่นแล้ว |
| Tesseract best / PSM 7 | รวมในคำสั่งแต่ละภาพ | 0.284 | ไม่มี resident model ข้ามภาพ; OS file cache อุ่นแล้ว |
| PP-OCRv5 mobile — detector + recognizer | 2.135 | 0.413 | imports + โหลดโมเดลไทย/อังกฤษสองชุด |
| Tesseract best / PSM 8 | รวมในคำสั่งแต่ละภาพ | 0.337 | ไม่มี resident model ข้ามภาพ; OS file cache อุ่นแล้ว |
| Tesseract best / PSM 13 | รวมในคำสั่งแต่ละภาพ | 0.326 | ไม่มี resident model ข้ามภาพ; OS file cache อุ่นแล้ว |

MLX restart จน endpoint พร้อมใช้ใช้ 3.053 วินาที ก่อนเริ่ม worker warmup ตัวเลข setup ไม่รวม Python imports พื้นฐานที่อยู่นอกช่วงจับเวลา และไม่ใช่ pure weight-loading time ที่เทียบข้าม framework ได้ตรง ๆ ไม่ล้าง OS file caches จึงไม่เรียกผลนี้ว่า cold-disk benchmark

## คำตอบครบทั้งเก้าช่อง

ตารางนี้แสดงผล warm pass แรก อีกสอง pass ให้ข้อความเหมือนกันทุกช่อง ✓ หมายถึงตรงเฉลยเดิมทั้งช่อง ผลว่างคงเป็นผิด ไม่กรองทิ้ง

| ช่อง | เฉลยเดิม | VL เดิม | PP recognizer | Tess fast/7 | Tess best/7 | PP detector+rec | Tess best/8 | Tess best/13 |
|---|---|---|---|---|---|---|---|---|
| g1 | ๑ | ⑨ | cl | อ | อ | [ว่าง] | "จ@ รรส[เงเว | "จ@ รรส[เงเว |
| g2 | ๒๐ | 30 | cYalwb | ๒๓๐ | ๒๓๐ | 3O | 1๒๒)๐ วุ | 1๒๒)๐ วุ |
| g3 | ๒๘ | 33 | c-w | ๒๓๕๐ | ๒๓๕๐ | [ว่าง] | 141ๆ๕ ภ-ฝฉ | 141ๆ๕ ภ-ฝฉ |
| g4 | ๓๑ | मॅ | c-b | ๓อ๑ | ๓๑ ✓ | 3 | วฑ@ >ณป | วฑ@ >ณป |
| g5 | ๙๔ | ཨུ | cYwb | ๕๕ | ๕๕ | [ว่าง] | ๕๕ โงเว | ๕๕ โงเว |
| g6 | ๑๕๙ | ༢༤་༤ | cYwb | ๑๕๓ | ๑๕๓ | [ว่าง] | ๑๕๓๕ ว | ๑๕๓๕ ว |
| r1-c3 | 59,135 | 69,135 | 69, 135 | 69,185 | 69,185 | 69, 135 | 59,185 | 59,185 |
| r3-c1 | 1,838,735 | 1,833,735 | 1, 838, 785 | 1, 888, 785 | 1,838,785 | 1, 838, 735 ✓ | 1,838,786 | 1,838,786 |
| r4-c5 | 13,282 | 18,282 | 18, 282 | 18, 282 | 13,282 ✓ | 18, 282 | 18,282 | 18,282 |

## ภาพเดิมและวิธีควบคุม

- สามช่อง Census คัดลอกไฟล์ round 4 เดิมแบบ byte-identical: `r1-c3`, `r3-c1`, `r4-c5`
- เลขหน้าราชกิจจาฯ หกช่องใช้ geometry 300 DPI ที่บันทึกไว้ในรอบ 4 สร้าง PNG ครั้งเดียวก่อนวัด g1/g5 มี hash ตรง request เก่าที่เคยส่งอ่านจริง อีกสี่ช่องเคยกำหนดกรอบแต่ยังไม่เคยถูกอ่านหลังระบบหยุดแถวแรก จึงเรียก reconstructed frozen crop ไม่อ้างว่าเป็นไฟล์ผลอ่านเก่าครบหกภาพ
- ทุกตัวได้รับไฟล์เดียวกัน ไม่มี resize, padding, ลบพื้นหลัง, เปลี่ยนตัวอักษร หรือ whitelist เลขเป็นการเตรียมภายนอก ตัวอ่านทำ preprocessing ภายในตาม configuration ที่ระบุ
- ความสูง crop เลขไทยเพียง 24–33 พิกเซล และมีขอบขาวกว้าง ภาพบางช่องมีความกำกวม 5/6 หรือ 3/8 ผลนี้ยังแยกเหตุจากกรอบภาพ ฟอนต์สแกน เฉลยผู้ตรวจคนเดียว และตัวโมเดลออกจากกันไม่ได้
- ใช้ภาษาประจำเอกสารที่รู้อยู่แล้วสำหรับตัวอ่านภาษาไทย/อังกฤษ ส่วน VL คง prompt `OCR:` เดิม ไม่มีการส่งค่าหรือชื่อจากเฉลยเข้า reader; references ถูกอ่านเฉพาะตัวสร้างชุดข้อมูลและ offline scorer
- CPU thread budget 2; รันทีละ reader, หยุดรับงาน production และปลด OCR/MLX ตามช่วง ก่อนคืน supervisors ทุกตัวเมื่อจบ ไม่มี concurrent model inference
- สี่การตั้งค่าแรกเป็น run ที่ตรึงไว้ก่อนอ่านผล ส่วน detector-assisted และ PSM 8/13 เป็น follow-up ที่บันทึกแยกหลังพบปัญหา input framing ไม่ใช่การทดสอบแบบ blinded หรือการเลือก configuration บน holdout
- ทั้งหมด 7 configurations × 9 crops × 4 passes = 252 observations แต่มีตัวอย่างไม่ซ้ำเพียงเก้าช่องที่เลือกจาก failure เดิม ไม่ใช่ full-document accuracy หรือผลทางสถิติ

## ข้อสรุปสำหรับระบบ

ยังไม่ควรเปลี่ยน reader หลักหรือเปิดเลือกคำตอบอัตโนมัติจากผลนี้ Tesseract best ใช้ทรัพยากรน้อยและช่วยได้บางช่อง แต่ยังพลาดห้าเลขหน้าไทยและสองช่อง Census การเพิ่ม detector ให้ PP ช่วย Cook แต่ไม่กู้เลขไทย ควรตรวจ framing/ขอบภาพและเฉลยที่กำกวมก่อน พร้อมใช้ตัวสำรองเป็นความเห็นที่สองหรือสัญญาณให้ตรวจทานเมื่อไม่ตรงกัน ขั้นถัดไปต้องมีข้อมูลแยกไว้ยืนยัน ไม่เลือกค่าจากเฉลยทีละช่อง

การลอง PSM 8/13 เป็นการตรวจ configuration ที่เหมาะกับคำ/บรรทัด ตาม [คู่มือ Tesseract](https://github.com/tesseract-ocr/tessdoc/blob/main/ImproveQuality.md#page-segmentation-method) ผลจริงในชุดนี้แย่กว่า PSM 7 ไม่ได้เปลี่ยน weights ส่วนภาษาไทยใช้ [โมเดลทางการ th_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/th_PP-OCRv5_mobile_rec) ที่โหลดจาก cache เดิม ตรวจชื่อและ hash ไฟล์แล้ว แยกกรณี recognition-only ออกจาก detector+recognizer ชัดเจน

## หลักฐานและสถานะ

- [METHOD.md](METHOD.md), [inputs.json](inputs.json), [references.json](references.json), [models.json](models.json) ล็อกวิธี ภาพ เฉลย และโมเดล; weights และ PDF ต้นฉบับอยู่นอก Git
- [analysis.json](analysis.json) และ [analyze.py](analyze.py) เก็บคะแนน/เวลาทุกรอบ; raw outputs ใน [results/](results/), [supplement/results/](supplement/results/), [wordmodes/results/](wordmodes/results/)
- Memory sampling ขอทุก 20 ms; ช่วงห่างจริงสูงสุดประมาณ 54 ms มี self ru_maxrss และ Tesseract `/usr/bin/time -l` เป็นหลักฐานเสริมเพื่อไม่พึ่ง sample สั้นเพียงอย่างเดียว
- ตัวสำรองใช้ CPU; VL ใช้ MLX/Metal; setup/import boundaries และ native allocation ต่างกันตามที่เปิดเผย จึงไม่อ้างว่าตารางแรมเป็นการวัด unified memory ทุกประเภทที่เทียบตรงกันได้
- Tesseract 5.5.4 ติดตั้งผ่าน Homebrew พร้อม dependencies บน Mac; language data fast/best ไทย/อังกฤษดาวน์โหลดจาก commit ทางการที่ระบุใน models.json ไว้ใน `~/research-server/models/tesseract-round5/` ไม่มีการติดตั้งเข้าบริการหลัก
- ผ่าน [validation.json](validation.json) สำหรับภาพเดิม จำนวนผล รอยเวลา การวัดแรม และ restoration ทั้งสาม sessions; production ยัง `ac1b98b`, controller กลับมาทำงาน ไม่มี runtime code change, main merge, Firecrawl หรือ external document upload
