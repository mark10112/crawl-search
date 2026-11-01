import base64,importlib.util,io,sys,unittest
from pathlib import Path
from PIL import Image
import pymupdf
from local_research.stack import render_ocr_page
services=Path(__file__).resolve().parents[1]/'services'
spec=importlib.util.spec_from_file_location('tested_table_bands',services/'table_bands.py');bands_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(bands_module)

class AccuracyRenderingTests(unittest.TestCase):
 def test_small_print_is_rendered_at_source_useful_resolution(self):
  d=pymupdf.open();p=d.new_page(width=72,height=72)
  p.insert_text((5,20),'small print',fontsize=5)
  data,meta=render_ocr_page(p)
  self.assertEqual(Image.open(io.BytesIO(data)).size,(300,300))
  self.assertEqual(meta['dpi'],300)
  self.assertLessEqual(meta['encoded_bytes'],20*1024*1024)
  d.close()
 def test_large_page_obeys_pixel_budget(self):
  d=pymupdf.open();p=d.new_page(width=2000,height=3000)
  data,meta=render_ocr_page(p)
  self.assertLess(meta['dpi'],300)
  self.assertLess(meta['width']*meta['height'],12100000)
  self.assertEqual(Image.open(io.BytesIO(data)).size,(meta['width'],meta['height']))
  d.close()
 def test_band_partition_preserves_every_source_pixel(self):
  from PIL import ImageDraw
  image=Image.new('RGB',(1800,1800),'white');draw=ImageDraw.Draw(image)
  for y in range(30,1800,70):draw.rectangle((0,y,1799,y+18),fill='black')
  intervals=bands_module.bands(image);rebuilt=Image.new('RGB',image.size)
  self.assertGreater(len(intervals),1)
  self.assertEqual(intervals[0][0],0);self.assertEqual(intervals[-1][1],1800)
  for i,(a,b) in enumerate(intervals):
   if i:self.assertEqual(a,intervals[i-1][1])
   rebuilt.paste(image.crop((0,a,1800,b)),(0,a))
  self.assertEqual(image.tobytes(),rebuilt.tobytes())
 def part(self,text,reason='stop'):
  return {'choices':[{'message':{'content':text},'finish_reason':reason}],'usage':{'completion_tokens':4},'token_usage_complete':True}
 def test_join_otsl_keeps_values_and_all_source_intervals(self):
  parts=[self.part('<fcel>Alpha<fcel>123<nl>'),self.part('<fcel>Beta<fcel>456<nl>')]
  r=bands_module.combine(parts,[{'y':[0,100]},{'y':[100,200]}],200)
  self.assertTrue(r['table_band_complete'])
  self.assertEqual(r['choices'][0]['message']['content'],'<fcel>Alpha<fcel>123<nl><fcel>Beta<fcel>456<nl>')
  self.assertEqual(r['usage']['completion_tokens'],8)
 def test_incomplete_or_inconsistent_tiles_are_not_success(self):
  for parts,metadata in [([self.part('<fcel>Alpha<nl>')],[{'y':[0,100]}]),
    ([self.part('<fcel>Alpha<nl>'),self.part('<fcel>Beta<fcel>456<nl>')],[{'y':[0,100]},{'y':[100,200]}]),
    ([self.part('<fcel>Alpha<nl>','length')],[{'y':[0,200]}])]:
   r=bands_module.combine(parts,metadata,200)
   self.assertFalse(r['table_band_complete']);self.assertEqual(r['choices'][0]['finish_reason'],'length')
