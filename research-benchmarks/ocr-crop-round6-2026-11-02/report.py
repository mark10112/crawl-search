"""Render every frozen configuration and distinguish pixel truth from intended values."""
import json
from pathlib import Path
P=Path(__file__).parent;A=json.loads((P/'analysis.json').read_text(encoding='utf8'));audit=json.loads((P/'reference-audit.json').read_text(encoding='utf8'))
names={'vl':'VLM เดิม','tesseract_best':'Tesseract best / PSM 7'}
variants={'original':'เดิม','original_pad10':'เดิม + ขาว 10px','tight':'กรอบกระชับ','tight_pad10':'กระชับ + ขาว 10px'}
lines=['# รอบ 6: ตรวจเฉลย แล้วแยกผลกรอบ crop กับขอบขาว','',
'**เติมขอบขาวช่วย Tesseract ในเลขไทยบางช่อง แต่ยังไม่ใช่การปรับที่ดีขึ้นทุกช่อง** คะแนนเลขไทยเพิ่มจาก 1/6 เป็น 2/6 ขณะที่ช่องที่เคยถูกบางช่องเสียไป หากดูเกณฑ์รวมเดิมเก้าภาพยังถูก 2/9 เท่าเดิมแต่คนละช่อง กรอบกระชับโดยไม่มีขอบขาวแย่ลง VLM ไม่ได้ดีขึ้นในสี่แบบนี้ ไม่มีการเปิดใช้ใน pipeline หรือขึ้น main','',
'## ตรวจเฉลยก่อนรัน','',
'ตรวจ SHA ของ PDF subset เดิม แล้วดูภาพต้นฉบับเต็มแถว/คอลัมน์และภาพขยายจากไฟล์นั้นก่อนตรึงข้อมูลใหม่ เลขไทยทั้งหกคือ `๑, ๒๐, ๒๘, ๓๑, ๙๔, ๑๕๙` ยืนยันจากภาพได้ **ไม่มีการเปลี่ยนค่าตัวเลขในเฉลยเดิม**','',
'สามช่อง Census มีปัญหาคนละระดับ: ค่าที่ตั้งใจรายงานได้รับการยืนยันด้วยตารางทางการอีกชุด แต่รูปร่าง glyph ในภาพทดสอบยังแยก 5/6 หรือ 3/8 ยาก จึงไม่อ้างว่าภาพทั้งสามอ่านได้ชัดแน่นอน และไม่แก้เฉลยไปตามเสียงส่วนใหญ่ของ OCR รอบนี้ใช้เลขไทยหกช่องเป็น primary pixel-accuracy และรายงานสาม Census เป็นคะแนนเทียบ intended value แยกต่างหาก','',
'| ช่อง | ค่าอ้างอิงคงเดิม | สถานะตรวจ | หลักฐาน |','|---|---|---|---|']
for r in audit['rows']:
 ident=r['id'];link=f'[ภาพบริบท](evidence/{ident}-context600.png)'
 if r['group']=='gazette':status='ยืนยันจากภาพ';source=link
 else:status='ค่ามีหลักฐานเทียบ; glyph ในสแกนยังคลุมเครือ';source=link+'; [ตารางทางการอีกชุด]('+r['crosscheck']['url']+')'
 lines.append(f"| {ident} | {r['expected_unchanged']} | {status} | {source} |")
lines+=['',
'แหล่งไทยที่ใช้ชื่อ ID ว่า thai-gazette คือหนังสือประมวลประกาศ รัชกาลที่ ๔ เล่ม ๓ ฉบับรวมพิมพ์ภายหลัง PDF หน้า 6–8 จากกรมศิลปากร ไม่ใช่แผ่นราชกิจจาฯ ศตวรรษที่ 19 ภาพ 600 DPI ใน evidence เป็นการขยายเพื่อดู ไม่ได้สร้างรายละเอียดที่หายไป และข้อความ OCR เก่าที่ฝังใน PDF ไม่ถูกใช้เป็นเฉลย','',
'ภาพแถวเต็มเพื่อดูชื่อแถวและลำดับช่อง: [Adams](evidence/adams-full-row600.png), [Cook](evidence/cook-full-row600.png), [Woodford](evidence/woodford-full-row600.png) เก็บจากภาพต้นฉบับก่อนการทดลอง ไม่ใช่ภาพที่ผ่านตัวอ่าน','',
'## การทดลองสี่แบบ','',
'- เดิม: PNG round 5 เดิมทุกไบต์',
'- เดิม + ขาว: เพิ่มขอบขาว 10 พิกเซลรอบภาพ',
'- กระชับ: หากลุ่มหมึกหลักด้วยกฎ component ที่ตรึงไว้ เลือกกรอบบรรทัดตัวเลข ตัดขอบว่าง/เศษแถวข้างเคียงนอกกรอบ',
'- กระชับ + ขาว: กรอบเดียวกับข้อก่อน แล้วเพิ่มขาว 10 พิกเซล',
'',
'ไม่มี resize, sharpen, แต่งเส้น หรือลบ pixel ภายในกรอบที่เก็บไว้ ใช้ threshold เฉพาะหา geometry ภาพอ่านจริงคงค่าสีเดิม กรอบใหม่ของ Cook เอาเศษแถว Crawford ที่ติดขอบล่างออกได้ ตัวอย่างนี้ถูกตรวจด้วยภาพก่อนรัน ไม่ได้เลือกกรอบจากการรู้ว่าผลใดจะตรงเฉลย','',
'![Cook: เดิมและกรอบที่ปรับ](evidence/r3-c1-variants.png)','',
'![ตัวอย่างเลขไทย: เดิมและกรอบที่ปรับ](evidence/g2-variants.png)','',
'## ความแม่นและความเร็ว','',
'รันบน Mac M4 เดิม โมเดล/weights/prompt/ภาษาเหมือนรอบ 5 ตัวละหนึ่งรอบแรกและสาม warm passes ให้ข้อความเหมือนกันทุกรอบ ทุกคำตอบจบตาม completion checks แต่การจบไม่ได้แปลว่าอ่านถูก ทั้ง 36 PNG ใช้เหมือนกันระหว่างสอง reader และไม่ส่งเฉลยเข้า prompt','',
'| ตัวอ่าน | กรอบ | เลขไทยชัด /6 | Census เทียบค่าอ้างอิง /3* | median ต่อภาพ (ms) | median รวมเก้าภาพ (s) |','|---|---|---:|---:|---:|---:|']
for s in A['summaries']:
 lines.append(f"| {names[s['mode']]} | {variants[s['variant']]} | {s['groups']['gazette']['stable_correct']}/6 | {s['groups']['census']['stable_correct']}/3 | {s['median_warm_ms']:.2f} | {s['median_nine_image_ms']/1000:.3f} |")
lines+=['',
'*สาม Census ไม่ถูกนับรวมเป็น primary pixel-accuracy เพราะภาพยังคลุมเครือ ถึงแม้ค่าอ้างอิงจะมีหลักฐานทางการสนับสนุน การเปรียบเทียบเก้าภาพทั้งหมดตาม legacy reference ยังอยู่ใน analysis แต่ไม่ใช้ปะปนกับหกภาพที่ยืนยันได้','',
'เวลาเป็นผลรวมเวลาเรียกอ่านภาพที่เตรียมไว้แล้ว ไม่รวมขั้นสร้าง crop หรือติดตั้ง/โหลดเครื่องมือ เทียบ reader API เดิม: VLM เป็น native server; Tesseract เป็น CLI จึงรวมการสร้างโปรเซสและโหลด language data ต่อภาพ ใช้ median ของผลรวมเก้าภาพจากสาม warm passes ไม่อ้างอัตราเร่งทั้ง PDF หรือความต่างไม่กี่ ms ว่ามีนัยสำคัญ','',
'## แรมและเวลาเริ่มต้น','',
'| ตัวอ่าน | reader-phase RSS peak | startup ภายใน worker | หมายเหตุ |','|---|---:|---:|---|']
for m in A['models']:
 raw=json.loads((P/'results'/(m['mode']+'.json')).read_text(encoding='utf8'))
 prep=f"{raw['setup']['startup_seconds']:.3f}s" if m['mode']=='vl' else 'รวมใน CLI แต่ละภาพ'
 note='รวม native MLX + worker; import/warmup ใน worker แยกจาก server ready' if m['mode']=='vl' else 'รวม wrapper + subprocess; child peak ตรวจด้วย /usr/bin/time -l'
 lines.append(f"| {names[m['mode']]} | {m['rss_phase_peak_bytes']/2**20:.1f} MiB | {prep} | {note} |")
lines+=['',
'RSS ไม่ใช่ unified memory/Metal allocation ทั้งหมด อาจนับ shared pages ซ้ำ เริ่มจับ VLM หลัง server พร้อม จึงไม่ครอบคลุม peak ก่อน server ready และ RAM ที่ค้างจากคำสั่งก่อนหน้าอาจอยู่ในช่วงของ variant ถัดไป ไม่ใช้สรุปว่ากรอบใดประหยัดแรมกว่าอย่างเป็นเหตุเป็นผล ข้อมูล peak ใน call windows ของแต่ละ variant อยู่ใน analysis.json','',
'CPU phase ปลด MLX ออกก่อนวัด ไม่มี inference ซ้อนกัน Sampling ขอทุก 20ms ช่วงห่างจริงสูงสุดประมาณ 55ms; Tesseract มีค่าจุดสูงสุดจากระบบต่อ subprocess เป็นหลักฐานเสริม Swap ที่ใช้อยู่ก่อนหน้าไม่เพิ่มระหว่างสอง reader phases คืน supervisor และบริการ production หลังจบแล้ว','',
'## เปลี่ยนช่องไหนบ้าง','',
'Tesseract เดิมอ่านเลข `๓๑` และ Woodford `13,282` ตรงค่าอ้างอิง แต่เติมขอบขาวกลับอ่านสองช่องนี้ผิด และได้ `๑` กับ `๒๐` ถูกแทน จึงไม่ใช่ชนะทุกช่อง ทั้งกรอบเดิม+ขาวและกระชับ+ขาวได้เลขไทย 2/6 เหมือนกัน ส่วนกระชับอย่างเดียวได้ 0/6','',
'| ตัวอ่าน / ช่อง | ค่าอ้างอิง | เดิม | เดิม+ขาว | กระชับ | กระชับ+ขาว |','|---|---|---|---|---|---|']
ids=[r['id'] for r in audit['rows']]
for mode in ['vl','tesseract_best']:
 for ident in ids:
  choices=[next(d for d in A['details'] if d['mode']==mode and d['variant']==v and d['id']==ident) for v in variants]
  row=[names[mode]+' / '+ident,choices[0]['expected']]
  for d in choices:
   r=d['predictions'][0];t=r['text'].replace('|','\\|').replace('\n','<br>') or '[ว่าง]';row.append(t+(' ✓' if r['correct'] else ''))
  lines.append('| '+' | '.join(row)+' |')
lines+=['',
'## ข้อสรุปและขอบเขต','',
'การเติม border มีผลกับ segmentation/คำตอบของ Tesseract จริง แต่ยังไม่มี configuration เดียวที่แม่นพอเปิดอัตโนมัติ การตัดขอบให้ชิดที่สุดไม่ได้ช่วยโดยตัวมันเอง และ VLM เดิมไม่ได้กู้เลขไทยชุดนี้ด้วยการเปลี่ยนกรอบทั้งสี่แบบ ควรเก็บผลนี้เป็นข้อจำกัดของชุดภาพ/การอ่านร่วมกัน ไม่กล่าวโทษโมเดลล้วน ๆ จากสาม glyph ที่กำกวม และไม่รวมคำตอบแต่ละกรอบที่ตรงเฉลยมาอ้างเป็นระบบ ensemble ที่ทำงานจริง','',
'นี่เป็น development-set ablation ที่รู้ failure เก่าแล้ว มี unique cases 9 ช่อง ไม่ใช่ holdout แม้อ่านซ้ำ 288 ครั้งผลนิ่งก็ตาม ไม่มีการหาค่าขอบ/threshold จากผล OCR ทีละช่อง ต้องมีชุดเอกสารยืนยันแยกก่อนเลือกนโยบาย preprocessing','',
'[METHOD.md](METHOD.md) ตรึงวิธี, [reference-audit.json](reference-audit.json) แยกสถานะเฉลย, [inputs.json](inputs.json) ล็อกกรอบ/PNG hash, [analysis.json](analysis.json) เก็บผลทุก pass และเวลา, [validation.json](validation.json) ตรวจว่าพิกเซลภายในกรอบ/ขอบขาวตรงตามกฎและ control เดิมตรง round 5 ทุกตัว แฟ้ม PDF/weights ต้นฉบับอยู่นอก Git','',
'งานทั้งหมดอยู่ใน branch ทดลอง ไม่มี runtime pipeline change หรือ main merge บริการ Mac คืน `ac1b98b` แล้ว ไม่ใช้ Firecrawl และไม่มี external document upload','']
(P/'REPORT.md').write_text('\n'.join(lines),encoding='utf8');print(P/'REPORT.md')
