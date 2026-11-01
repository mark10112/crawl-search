# Local Research 0.2.0

ระบบที่ติดตั้ง: SearXNG :8088 → HTTP/trafilatura → Crawl4AI เมื่อจำเป็น; PDF อ่าน text layer ก่อน แล้ว OCR เฉพาะหน้าที่ไม่มีข้อความ → RapidOCR หรือ LightOnOCR → หากอ่านไม่ได้ส่งงานให้ client เรียก Firecrawl แล้วรับผลกลับเข้าตัวแคช

## OCR Docker

บริการ `local-research-ocr` ที่ติดตั้งบนเครื่องนี้ใช้ image ทดสอบที่มีอยู่ `ocr-multilingual-bench:2026-11-01` และ mount service แบบ read-only โดย `start-ocr.ps1` เปิดเฉพาะ loopback :8091 และ restart unless-stopped เมื่อ Docker ทำงาน โมเดลอยู่ใน volume `ocr-benchmark-models` ไม่อยู่ในแพ็กเกจ ZIP

สำหรับเครื่องใหม่ build จาก `services/Dockerfile` ด้วย `docker compose -f services/compose.yaml up -d --build` ต้องมี NVIDIA GPU, Docker GPU support และพื้นที่ดาวน์โหลดโมเดล ครั้งแรกใช้เวลามากกว่าคำขอหลังโหลดโมเดลแล้ว Dockerfile นี้เป็นเส้นทาง build ที่ให้ไว้ ยังไม่ได้ benchmark image ที่ build จากไฟล์ใหม่นี้; การวัดใช้ image ที่ระบุข้างต้น

MCP ลงทะเบียนพร้อม `LOCAL_RESEARCH_OCR_URL=http://127.0.0.1:8091` แล้ว ในแชตที่เปิดค้างอาจต้องโหลดรายการ MCP ใหม่หรือเปิดแชตใหม่

## การเลือกเส้นทาง

- `ocr_policy="balanced"`: ใช้ language hint จากผู้เรียกหรือ PDF /Lang สำหรับ RapidOCR; ถ้าความมั่นใจต่ำใช้ LightOn ภาษาไม่ทราบ/หลายภาษาใช้ LightOn โดยตรง
- `ocr_policy="quality"`: ใช้ LightOn กับทุกหน้าที่ต้อง OCR ช้ากว่าแต่แม่นกว่าในชุดนี้ เหมาะสำหรับเอกสารสำคัญหรือหลายภาษา
- ความมั่นใจของ OCR ไม่รับประกันความถูกต้อง ชื่อเฉพาะ ตัวเลข ตาราง และเอกสารเก่ายังต้องตรวจต้นฉบับ
- LightOn ใช้ named model class และ revision ที่ตรึงไว้ ตรวจ missing/unexpected weights ก่อนให้บริการ ไม่ใช้ AutoModel ที่อาจเลือก architecture ผิด
- `cache=False` ปิดทั้ง URL cache และ OCR result cache แต่ไม่ได้ unload โมเดลหรือ browser; cache key รวม policy, language, page range และ revision
- Search มี cache, pacing และ cooldown เมื่อ upstream จำกัดคำขอ; URL ซ้ำใน read_many ใช้งานร่วมกัน

## Firecrawl fallback

Reader ไม่เก็บ Firecrawl API key และไม่เรียกบริการเสียเครดิตเอง หาก local ล้มเหลวจะคืน `fallback_request_id` กับ `next_tool_call` ให้ agent เรียก connected Firecrawl แล้วส่งข้อความ/metadata/credits กลับผ่าน `research_complete_fallback` คำขอมีอายุและตรวจ source URL ก่อนรับผล หากเปิด cache ผลนี้อ่านซ้ำในเครื่องได้โดยไม่เรียก Firecrawl ซ้ำ เส้นทางนี้ต้องมี agent/client ที่ทำ handoff ไม่ใช่ server-to-server fallback อัตโนมัติ

ตรวจเส้นทางจริงแล้วโดยจำลอง local outage → connected Firecrawl 1 เครดิต → complete → อ่านซ้ำ cache_hit=true, credits_used=0 ดูผลใน `research-benchmarks/router-vs-firecrawl-2026-11-01/results/fallback-integration.json` จาก workspace root

## ผลวัดจริง

รายงานหลักอยู่ `research-benchmarks/router-vs-firecrawl-2026-11-01/REPORT.md` จาก workspace root พร้อมเอกสารต้นทาง ข้อความอ้างอิง ผลดิบ และสคริปต์ ทำซ้ำได้แต่ Firecrawl จะเสียเครดิตเพิ่ม เอกสารสังเคราะห์หน้าเดียว 17 ชิ้น ไม่ใช่หลักฐานความแม่นกับทุกคลังเอกสาร และไม่รวมการค้นหาเว็บ

มี HTTP adapter สำหรับ client ในเครื่อง (`python -m local_research.http_api`, loopback :8768) ซึ่งใช้วัดครั้งนี้ ไม่จำเป็นต้องเปิดสำหรับ MCP stdio
