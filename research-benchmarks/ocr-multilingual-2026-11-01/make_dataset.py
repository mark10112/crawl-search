import asyncio
import hashlib
import html
import json
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
CASES = [
    ("english", "en", "en", "Research memorandum\nThe council met on 18 April 1855 to discuss trade and taxation.\nImport duties were calculated on the market value of goods.\nA successful agreement required trust, money, and clear records.\nInvoice number 1874: total payment 12,450.75 baht."),
    ("french", "fr", "latin", "Note de recherche\nLe comité étudie les relations entre le commerce et le pouvoir.\nLes archives décrivent une négociation difficile et plusieurs intérêts.\nIl faut vérifier les sources avant de tirer une conclusion.\nRéférence 1875 : coût total 2 345,60 euros."),
    ("german", "de", "latin", "Forschungsbericht\nDie Regierung prüft die Einnahmen und die öffentlichen Ausgaben.\nEine zuverlässige Quelle unterscheidet Tatsachen von Vermutungen.\nÜbermäßige Macht kann neue politische Konflikte verursachen.\nAktenzeichen 1874: Gesamtbetrag 3.456,70 Euro."),
    ("thai", "th", "th", "บันทึกการวิจัย\nคณะกรรมการประชุมเพื่อพิจารณารายได้และค่าใช้จ่ายของรัฐ\nการเจรจาต้องคำนึงถึงผลประโยชน์ของประชาชนหลายกลุ่ม\nควรตรวจสอบหลักฐานก่อนสรุปว่าใครเป็นผู้สั่งการ\nเลขที่เอกสาร ๒๔๑๗ จำนวนเงิน ๑๒,๔๕๐ บาท"),
    ("chinese", "zh", "ch", "研究记录\n委员会讨论了贸易、税收以及政府的公共支出。\n可靠的历史研究必须区分事实、传闻和个人意见。\n谈判双方都希望保护自己的利益与安全。\n档案编号1874：总金额为12,450元。"),
    ("japanese", "ja", "ch", "調査報告書\n委員会は貿易と税金について話し合いました。\n歴史を研究するときは、事実と推測を区別する必要があります。\n交渉では、それぞれの立場と利益を理解することが重要です。\n資料番号1874：合計金額は12,450円です。"),
    ("arabic", "ar", "arabic", "تقرير البحث\nناقشت اللجنة التجارة والضرائب والنفقات العامة.\nيجب التمييز بين الحقائق والشائعات عند قراءة الوثائق التاريخية.\nتحتاج المفاوضات إلى الثقة والسجلات الواضحة.\nرقم الوثيقة 1874 والمبلغ الإجمالي 12450."),
    ("hindi", "hi", "devanagari", "अनुसंधान रिपोर्ट\nसमिति ने व्यापार और सार्वजनिक खर्च पर चर्चा की।\nऐतिहासिक दस्तावेज पढ़ते समय तथ्य और अनुमान अलग रखने चाहिए।\nसमझौते के लिए विश्वास और स्पष्ट अभिलेख आवश्यक हैं।\nदस्तावेज संख्या 1874 और कुल राशि 12450 रुपये है।"),
    ("mixed-thai-english", "th+en", "th", "Trade and public revenue\nรายงานการค้าและรายได้ของรัฐ\nImport duty: 3 percent of the market value.\nต้องตรวจสอบบัญชีและหลักฐานการชำระเงิน\nReference 1874 / จำนวนเงิน 12,450 บาท"),
    ("mixed-latin", "en+fr+de", "latin", "International research notes\nVerify the source before making a claim.\nVérifiez les sources avant de conclure.\nPrüfen Sie die Quelle vor einer Schlussfolgerung.\nTotal: 1,234.50 / Référence 1874 / Akte 1875"),
]


async def main():
    folder = ROOT / "dataset"
    folder.mkdir(exist_ok=True)
    items = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 1500}, device_scale_factor=1)
        for name, languages, rec, text in CASES:
            direction = "rtl" if languages == "ar" else "ltr"
            markup = f'''<html><meta charset="utf-8"><style>body{{margin:0;background:white;color:#111}}article{{padding:100px 75px;font-family:"Leelawadee UI","Nirmala UI","Microsoft YaHei","Yu Gothic",Arial,sans-serif;font-size:34px;line-height:1.8;white-space:pre-wrap;direction:{direction};}}</style><article>{html.escape(text)}</article></html>'''
            await page.set_content(markup)
            await page.evaluate("document.fonts.ready")
            path = folder / (name + ".png")
            await page.screenshot(path=str(path), full_page=True)
            overflow = await page.evaluate("document.documentElement.scrollWidth > 1200")
            if overflow:
                raise RuntimeError(f"Horizontal clipping: {name}")
            items.append({"id": name, "languages": languages, "rapid_language": rec, "image": path.name,
                          "reference": text, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "kind": "clean-single-block"})
        await browser.close()
    for source in [items[0], items[3], items[8]]:
        image = Image.open(folder / source["image"])
        image = image.resize((600, 750)).resize(image.size).filter(ImageFilter.GaussianBlur(.6))
        image = ImageEnhance.Contrast(image).enhance(.6)
        name = source["id"] + "-degraded"
        path = folder / (name + ".png")
        image.save(path)
        items.append({**source, "id": name, "image": path.name, "kind": "degraded-single-block", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (folder / "manifest.json").write_text(json.dumps({"synthetic": True, "notes": "Self-authored multilingual test blocks, not a representative historical-document corpus. RapidOCR gets the known script; language detection cost excluded.", "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    thumbs = Image.new("RGB", (1200, 4*375), "#cccccc")
    for index, item in enumerate(items[:12]):
        image = Image.open(folder / item["image"]).resize((300,375))
        thumbs.paste(image, ((index%4)*300,(index//4)*375))
    thumbs.save(folder / "contact-sheet.jpg")
    print(json.dumps({"items": len(items), "folder": str(folder)}))


if __name__ == "__main__":
    asyncio.run(main())
