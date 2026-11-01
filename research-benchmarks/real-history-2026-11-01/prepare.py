import json,hashlib
from pathlib import Path
import pymupdf
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
for ident,pages in [('thai-gazette',range(1,12)),('thai-royal',range(1,21)),('us-preservation',range(1,17)),('us-census',range(1,4))]:
    doc=pymupdf.open(ROOT/'sources'/f'{ident}.pdf')
    sheet=Image.new('RGB',(4*250,((len(pages)+3)//4)*360),'#ddd');draw=ImageDraw.Draw(sheet)
    for n,i in enumerate(pages):
        p=doc[i-1];pix=p.get_pixmap(matrix=pymupdf.Matrix(.5,.5));im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);im.thumbnail((245,330))
        x=(n%4)*250;y=(n//4)*360;sheet.paste(im,(x,y+25));draw.text((x+5,y+3),f'{ident} PDF {i}',fill='black')
    sheet.save(ROOT/'review'/f'{ident}-contact.jpg')
