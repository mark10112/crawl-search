# Local Research Stack

แพ็กเกจ MCP/CLI สำหรับค้นด้วย SearXNG แล้วเลือกตัวอ่านตามเอกสาร พร้อม benchmark ที่ทดสอบซ้ำได้

## เส้นทางอ่าน

```text
research_search -> local SearXNG -> URLs/snippets
research_read   -> HTTP + article extraction + scholarly metadata
                  ├─ HTML ไม่มีเนื้อหา/โหลดไม่ได้ -> Crawl4AI browser
                  └─ PDF -> selectable text per page
                            └─ หน้าสแกน -> OCR service: RapidOCR / LightOnOCR
                                           └─ ไม่ได้ตั้ง service: legacy Tesseract/Docling
                  └─ อ่านไม่ได้ -> agent เรียก Firecrawl -> complete_fallback -> cache
```

ตัวอ่านไม่ตีความเนื้อหาเป็นคำตอบเอง ส่งข้อความ แหล่งที่มา ช่วงหน้า การตัดข้อความ และเวลาแต่ละขั้นกลับให้ agent ไม่มีการเรียกโมเดลภาษาหรือ Firecrawl แบบเสียเงินอัตโนมัติ ถ้ายังอ่านไม่ได้คืน `external_fallback_required: true` เพื่อให้ agent เลือกแหล่งอื่นหรือเครื่องมือที่ได้รับอนุญาตต่อ

เลือก `ocr_engine="router"`, `"docling"` หรือ `"tesseract"` ได้ ค่า `auto` ใช้ OCR service ถ้าตั้งไว้ เลือก `ocr_policy="quality"` เพื่อใช้ LightOn กับหน้าสแกนทั้งหมด การคืนข้อความได้ไม่ได้พิสูจน์ว่าครบทุกบรรทัดหรืออ่านชื่อเฉพาะถูก ต้องตรวจเทียบภาพเมื่อใช้เป็นหลักฐาน

## ใช้งานบนเครื่องนี้

ติดตั้งและลงทะเบียน MCP ชื่อ **local-research** แล้ว ตัว SearXNG เดิมอยู่ที่ `http://127.0.0.1:8088` ต้องเปิด Docker Desktop และให้ container `searxng-local` ทำงาน ส่วน MCP เริ่มโปรเซสเมื่อ client เชื่อมต่อ ไม่ต้องเปิด terminal ค้างเอง

เครื่องมือ:

- `research_search`: ค้นพร้อมคืนข้อผิดพลาดของเอนจินต้นทาง
- `research_read`: เลือก HTTP/browser/PDF/OCR อัตโนมัติ มี cache หนึ่งชั่วโมง
- `research_read_many`: อ่านพร้อมกันสูงสุดสามงาน ไม่เกินสิบ URL ต่อคำขอ; browser และ OCR ใช้ worker อย่างละหนึ่งตัว
- `research_health`: ตรวจบริการและรุ่นไลบรารี

คำค้นที่สำเร็จมีแคชสิบนาที เรียกต้นทางห่างกันอย่างน้อยหนึ่งวินาทีในโปรเซสเดียว หากได้ผลว่างพร้อม CAPTCHA/การจำกัดคำขอ จะพักหกสิบวินาทีและคืน `external_search_required` ให้ agent เปลี่ยนไปใช้ Native search เอง MCP ไม่สามารถเรียกเครื่องมือ Native ของ client แทน agent ได้ และไม่ยิง Firecrawl แบบเสียเครดิตอัตโนมัติ

การตั้งค่า MCP ใหม่อาจต้องเปิดแชตใหม่หรือโหลดการเชื่อมต่อใหม่จึงจะเห็นในรายการ tools ของแอป การทดสอบ stdio ในแพ็กเกจยืนยันการเรียกได้โดยตรง ไม่ได้หมายความว่ารายการ tools ของแชตเดิมรีโหลดแล้ว

## ติดตั้งซ้ำ — Windows / Python 3.12 / uv

ในโฟลเดอร์แพ็กเกจ:

```powershell
.\setup.ps1                 # browser + OCR เบา
.\setup.ps1 -WithDocling    # เพิ่ม Docling/EasyOCR/PyTorch CPU แบบ optional
.\.venv\Scripts\python.exe -m local_research.cli health
.\.venv\Scripts\python.exe -m local_research.cli search "วิกฤตการณ์วังหน้า"
.\.venv\Scripts\python.exe -m local_research.cli read "https://docs.searxng.org/dev/search_api.html" --no-cache
```

`uv.lock` ล็อกรุ่น dependencies; extra OCR ใช้ PyTorch CPU จาก official wheel index ไม่ติดตั้ง CUDA toolkit โดยปริยาย การติดตั้ง browser อาจใช้ cache ของ Playwright ตามปกติ ข้อมูลภาษา Tesseract อยู่ `.cache/tessdata` ส่วนโมเดล Docling/EasyOCR ใช้ cache ของไลบรารีและดาวน์โหลดเมื่อเรียกครั้งแรก

MCP launcher แบบไม่ขึ้นกับ working directory: `.venv/Scripts/python.exe` ตามด้วย path เต็มของ `server.py` สามารถกำหนด `SEARXNG_URL`, `LOCAL_RESEARCH_STATE`, `LOCAL_RESEARCH_TESSDATA` ผ่าน environment ได้

## Docker

มี `Dockerfile` และ `compose.yaml` สำหรับรุ่น CPU/browser ใช้ข้อมูล OCR ไทย+อังกฤษ ไม่รวม PyTorch, Docling หรือโมเดล VLM ใน image เริ่มต้น การเลือก Docling ใน image นี้จะรายงานว่าไม่มี dependency แทนการแอบโหลด package เพิ่ม

```powershell
docker build -t local-research-stack:0.1.0 .
docker run --rm --entrypoint /app/.venv/bin/python local-research-stack:0.1.0 -m local_research.cli health
docker run --rm -i -v local-research-cache:/data local-research-stack:0.1.0
```

คำสั่งสุดท้ายเป็น MCP stdio สำหรับนำไปตั้งค่าใน client ค่า SearXNG ใน Docker ใช้ `http://host.docker.internal:8088` บน Docker Desktop บน Linux ต้องปรับ endpoint หรือใช้ `--add-host=host.docker.internal:host-gateway` และทำให้บริการเข้าถึงได้ ไม่มีการเปิดพอร์ตสำหรับ MCP ออกสู่เครือข่าย

Docling เป็นชุดแปลงเอกสารที่เลือก OCR engine ได้ ไม่ใช่ชื่อโมเดล OCR ตัวเดียว บันทึก OCR รุ่นก่อนอยู่ใน [OCR-MODELS.md](OCR-MODELS.md) ส่วนผลปัจจุบันรวม RapidOCR, PaddleOCR-VL-1.6 และ LightOnOCR ดู benchmark หลายภาษาและ router รุ่น 0.2.0 ด้านล่าง

## อัปเดต 0.2.0 — ใช้งานบนเครื่องนี้แล้ว

เพิ่ม OCR service แบบโหลดโมเดลค้างไว้, RapidOCR → LightOn fallback, นโยบาย balanced/quality, OCR content cache, PDF รายหน้า และ client-agent Firecrawl handoff พร้อมรับผลกลับเข้า local cache รายละเอียดการใช้และติดตั้งใหม่อยู่ [ROUTER-V2.md](ROUTER-V2.md) คำสั่ง Docker 0.1.0 ข้างต้นเป็น CPU reader รุ่นเดิม ส่วน GPU OCR เป็นบริการแยก :8091

เทียบ Firecrawl จริงบนเอกสารเดียวกัน 17 ชิ้น แยก cache off/prime/hit ครบ 102 observations: local balanced p50 fresh 1.44 วินาที, cached 0.009 วินาที; Firecrawl 5.51 และ 2.10 วินาทีตามลำดับ CER รวม local balanced 1.34%, quality 0.41%, Firecrawl 4.91% แต่ Firecrawl แม่นกว่า balanced ในกลุ่มสะอาดภาษาเดียว ผลนี้จำกัดที่เอกสารสังเคราะห์สั้นและวัดคนละ transport ไม่ใช่การรับประกันกับเอกสารทุกชนิด รายงาน/ผลดิบอยู่ `research-benchmarks/router-vs-firecrawl-2026-11-01/REPORT.md` จาก workspace root

**ผลเอกสารประวัติศาสตร์จริงให้ข้อสรุปต่างออกไป:** 4 แหล่ง 12 หน้า รวมสแกนไทยเก่าและตารางหนาแน่น Local ปัจจุบันยังไม่เหมาะแทน Firecrawl สำหรับงานกลุ่มนี้ แม้ cache และ text layer จะเร็ว พบตัวเลขผิด แถวตารางเสียความสัมพันธ์ และข้อความซ้ำจาก OCR ดู [รายงานเอกสารจริง](../../research-benchmarks/real-history-2026-11-01/REPORT.md) พร้อมผลดิบและข้อจำกัดของการตรวจเฉลยแบบสุ่มตัวอย่าง ไม่ควรใช้ผลชุดจำลองเป็นหลักฐานความแม่นในคลังประวัติศาสตร์

## Performance และการทดสอบ

```powershell
.\benchmark.ps1 -Suite controlled -Repeats 3
.\benchmark.ps1 -Suite live -Repeats 3
.\.venv\Scripts\python.exe -m local_research.mcp_probe
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Controlled suite สร้าง HTML ธรรมดา, เว็บ JavaScript, PDF ตัวอักษร และ PDF ภาพสแกนไทย/อังกฤษที่รู้ข้อความแน่นอน วัด first/warm/cached แยกกัน และตรวจทั้งข้อความอังกฤษกับคำหลักภาษาไทย ไม่เอาผลล้มเหลวที่คืนเร็วไปนับว่าอ่านเร็วสำเร็จ ชุดสร้าง fixture ปัจจุบันใช้ฟอนต์ Windows

Live suite อ่านแหล่งเดียวกับ benchmark ก่อนหน้า เทียบ basic กับ auto สลับลำดับ ปิดแคชผลลัพธ์ของแพ็กเกจ ค้นหกคำค้นซ้ำ และอ่าน PDF ไทยจริงสองหน้า ทุกผลเก็บ `raw.json`, `summary.json`, `summary.md` พร้อม stage timings, errors, text, p50/p95 และ peak RSS ของ process tree

ดู [PERFORMANCE.md](PERFORMANCE.md) สำหรับผลที่วัดได้จริง ตัวเลขเหล่านี้ไม่รวมเวลาคิด/เขียนคำตอบของโมเดล จึงไม่ควรนำไปเทียบตรง ๆ กับเวลา subagent ใน benchmark ก่อนหน้า

## ขอบเขต

- ดาวน์โหลดไม่เกิน 32 MiB ต่อ URL; อ่าน PDF สูงสุดสิบหน้าต่อคำขอ (ค่าเริ่มต้นห้า); ข้อความส่งกลับสูงสุด 40,000 อักษร พร้อม `truncated`
- ตรวจ HTTP(S), ปฏิเสธ URL แบบ file และแหล่ง private/local ในงานอ่านทั่วไป; benchmark เปิด loopback เฉพาะ fixture ของตัวเอง ไม่ใช่บริการสำหรับเปิดให้ผู้ใช้ภายนอกใช้งาน
- มี timeout แยก HTTP/browser/OCR และ kill/restart OCR worker เมื่อเกินเวลา
- ผลที่อ่านไม่สำเร็จไม่ถูกเก็บเป็นแคชสำเร็จ; แคชอยู่ในเครื่องและอาจมีเนื้อเอกสารที่อ่าน
- SearXNG อาจได้ผลบางส่วนเมื่อเอนจินต้นทางจำกัดคำขอ มี `engine_errors` ให้ตรวจ ไม่รับประกันว่าได้ผลเหมือนกันทุกครั้ง
- p95 จากสามรอบเป็นสถิติบรรยายกลุ่มตัวอย่างเล็ก ไม่ใช่ SLA; แคชของเว็บไซต์/CDN และเอนจินต้นทางควบคุมไม่ได้
- ไม่แก้ไฟล์นิยายหรือต้นฉบับใด ๆ
