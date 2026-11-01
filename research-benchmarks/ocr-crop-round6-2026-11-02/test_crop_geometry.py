import unittest
from PIL import Image,ImageDraw,ImageChops
from crop_geometry import dominant_bbox,variants

class GeometryTests(unittest.TestCase):
    def test_keeps_comma_but_excludes_next_row_fragment_and_speck(self):
        im=Image.new('RGB',(100,40),'white');draw=ImageDraw.Draw(im)
        draw.rectangle((25,5,35,24),fill='black');draw.rectangle((45,5,55,24),fill='black')
        draw.rectangle((38,21,40,27),fill='black') # Comma below digit baseline.
        draw.rectangle((22,35,60,37),fill='black');draw.point((0,29),fill='black')
        self.assertEqual(dominant_bbox(im),[25,5,56,28])
    def test_padding_retains_pixels_exactly(self):
        im=Image.new('RGB',(80,30),'white');ImageDraw.Draw(im).rectangle((20,5,40,24),fill=(15,22,36))
        for name,result,box,pad in variants(im):
            inner=result.crop((pad,pad,result.width-pad,result.height-pad)) if pad else result
            self.assertIsNone(ImageChops.difference(inner,im.crop(box)).getbbox(),name)
            if pad:self.assertEqual(result.getpixel((0,0)),(255,255,255))
