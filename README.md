# Crawl Search

ระบบค้นหาเว็บ อ่านเอกสาร และ OCR สำหรับรันเอง งานประมวลผลทำบน Mac mini M4 และ Windows เรียกผ่าน MCP กับ SSH

## สถานะ

- นำเข้า prototype `local-research-stack` 0.2.0 ที่ทดสอบบน Windows แล้ว
- มี SearXNG client, HTTP/browser/PDF reader, OCR router, cache และ Firecrawl client-agent handoff
- นำเข้ารายงาน benchmark ทั้งชุดจำลองและเอกสารประวัติศาสตร์จริง ผลจริงพบข้อจำกัดของ OCR เก่า ตาราง และการรายงานข้อความขาด
- เปิดใช้ Mac server แล้ว: SearXNG, HTTP/browser/PDF reader และ PaddleOCR-VL 1.6 ผ่าน native MLX/Metal พร้อมคิวงาน SQLite
- Windows เหลือ MCP bridge; ปิด SearXNG/OCR containers เดิมและปิดการเริ่มใหม่อัตโนมัติแล้ว
- ทดสอบผ่าน MCP จริงทั้งค้นหา เว็บ JavaScript อัปโหลดภาพไทย และการเก็บผลหลังรีสตาร์ต API; ดู [สถานะและคู่มือ](docs/mac-server.md)
- การย้ายเครื่องไม่ได้ยืนยันว่าความแม่น OCR สแกนเก่า/ตารางแก้ครบแล้ว ยังต้องเทียบชุดเอกสารจริงใหม่

## โครงสร้าง

| ตำแหน่ง | หน้าที่ |
|---|---|
| `research-tools/local-research/` | ตัวอ่าน MCP/CLI, HTTP adapter, tests และ OCR service prototype |
| `research-benchmarks/` | สคริปต์ ชุดจำลอง เฉลย และผลวัดที่คัดไว้ |
| `deploy/mac/` | ติดตั้งบริการบน Mac, เวอร์ชัน OCR และทดสอบผ่าน API/MCP |
| `docs/mac-server.md` | สถานะบริการ ขั้นตอนติดตั้ง และคู่มือดูแล Mac server |

## ทดลองตัวอ่านพื้นฐาน

ต้องมี Python 3.12 หรือ 3.13 และ uv:

```sh
cd research-tools/local-research
uv sync --frozen
uv run python -m local_research.cli health
uv run python -m unittest discover -s tests -v
```

ตัวอ่าน browser ต้องเพิ่ม `--extra browser` และติดตั้ง Chromium ตามคู่มือแพ็กเกจ ส่วน tests ที่ตรวจ browser recovery ใช้ extra นี้ด้วย คำสั่ง health ไม่ได้ยืนยันว่า OCR GPU พร้อมแล้ว

Dockerfile/service GPU ที่นำเข้ารุ่นแรกเป็น **NVIDIA/CUDA prototype** ใช้เป็น baseline บน Windows/Linux เส้นทาง Mac จะมี environment ของตัวเอง ไม่ให้นำ CUDA service ไปรันแล้วอ้างว่าใช้ Metal

## หลักฐานผลวัด

- [เอกสารจริง ไทย/อังกฤษ หลายหน้าและตาราง](research-benchmarks/real-history-2026-11-01/REPORT.md)
- [Local router เทียบ Firecrawl บนชุดจำลอง](research-benchmarks/router-vs-firecrawl-2026-11-01/REPORT.md)
- [RapidOCR / PaddleOCR-VL / LightOnOCR หลายภาษา](research-benchmarks/ocr-multilingual-2026-11-01/REPORT.md)

ผลตัวอย่างไม่ใช่การรับรองความแม่นกับทุกคลังเอกสาร ค่า CER ของชุดจริงใช้ช่วงข้อความที่ตรวจด้วยภาพโดยผู้ตรวจรายเดียว และเก็บการแก้เฉลยไว้เพื่อเปิดตรวจได้

Repository ไม่รวม virtual environments, credentials, SSH keys, model weights, runtime cache หรือไฟล์นิยาย เอกสารจริงต้นฉบับ/ภาพ render ดาวน์โหลดหรือสร้างใหม่จาก URL และเลขหน้าใน catalog/manifest รายงานเก่าบางลิงก์ไปผลดิบหรือ ZIP ที่เก็บไว้นอก Git; Git รุ่นแรกเก็บรายงานและคะแนนที่คัดไว้เท่านั้น
