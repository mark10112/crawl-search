import sys,unittest
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services'))
from row_geometry import index_rows,short_table_rows

class RowGeometryTests(unittest.TestCase):
    def test_index_keeps_multiline_title_and_detached_endpoint(self):
        image=Image.new('RGB',(1000,1400),'white');draw=ImageDraw.Draw(image)
        for y in range(300,1200,150):
            draw.rectangle((50,y,110,y+18),fill='black')
            draw.rectangle((200,y,700,y+18),fill='black')
            draw.rectangle((200,y+40,650,y+58),fill='black')
            draw.rectangle((915,y+40,940,y+58),fill='black')
        rows=index_rows(image)
        self.assertEqual(len(rows),6)
        for row in rows:
            self.assertLess(row['label_bbox'][0],200)
            self.assertGreater(row['label_bbox'][3]-row['label_bbox'][1],58)
            self.assertGreaterEqual(row['value_bbox'][0],860)
    def test_plain_paragraph_and_dashed_table_are_not_indexes(self):
        for dashed in [False,True]:
            image=Image.new('RGB',(1000,1400),'white');draw=ImageDraw.Draw(image)
            for y in range(200,1200,40):
                draw.rectangle((60,y,130,y+15),fill='black')
                draw.rectangle((200,y,950,y+(2 if dashed else 15)),fill='black')
            self.assertEqual(index_rows(image),[])
    def test_short_table_splits_data_lines_and_keeps_every_pixel(self):
        image=Image.new('RGB',(640,80),'white');draw=ImageDraw.Draw(image)
        for y in [8,28,60]:
            for x in [25,55,85]:draw.rectangle((x,y,x+14,y+8),fill='black')
        draw.line((0,0,639,0),fill='black');draw.line((0,79,639,79),fill='black')
        intervals=short_table_rows(image)
        self.assertEqual(len(intervals),3)
        self.assertEqual([v for a,b in intervals for v in range(a,b)],list(range(80)))
        self.assertEqual(short_table_rows(Image.new('RGB',(640,80),'white')),[])
