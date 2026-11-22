from pathlib import Path
import sys,tempfile,unittest,json
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pymupdf as fitz
from shapely.geometry import box,Point,Polygon
from build_a3_release import MM,polygon_of,extract_layers
from laser_paths import cut_path
from verify_laser_paths import contours
from build_individual_assets import export_asset

class IndependentAssetRegression(unittest.TestCase):
    def test_extract_isolates_neighbour_and_preserves_slot_and_hole(self):
        art=fitz.open();pg=art.new_page(width=100*MM,height=100*MM)
        pg.draw_rect(fitz.Rect(10*MM,20*MM,25*MM,50*MM),color=None,fill=(0,0,0))
        # Neighbour inside the bounding box but outside the L-shaped part.
        pg.draw_rect(fitz.Rect(30*MM,30*MM,37*MM,37*MM),color=None,fill=(1,0,0))
        outer=Polygon([(10,20),(40,20),(40,25),(25,25),(25,50),(10,50)])
        hole=Point(16,27).buffer(2,quad_segs=32);slot=box(13,40,21,43)
        paths=[{'path':cut_path(q),'poly':q,'protected':False} for q in [hole,slot,outer]]
        piece={'id':'fixture','bounds':outer.bounds,'poly':outer,'paths':paths,'art':art,'white':None,'source':'test'}
        with tempfile.TemporaryDirectory() as d,patch('build_individual_assets.OUT',Path(d)),patch('build_individual_assets.ROOT',Path(d).parent.parent):
            # exporter paths are registered relative to ROOT/output, so use the
            # same folder arrangement as a production catalog.
            root=Path(d);out=root/'output/individual_assets'
            with patch('build_individual_assets.OUT',out),patch('build_individual_assets.ROOT',root):
                export_asset({'piece':piece,'groups':['fixture/3T']})
            folder=out/'fixture';spec=json.loads((folder/'asset.json').read_text(encoding='utf-8'))
            self.assertEqual(spec['cut_size_mm'],[30,30])
            with fitz.open(folder/'03_CUT_ONLY.pdf') as doc:
                polys=[polygon_of(s) for dr in doc[0].get_drawings() for s in contours(dr)]
            self.assertEqual(len(polys),3)
            self.assertAlmostEqual(polys[0].bounds[2]-polys[0].bounds[0],4,places=3)
            self.assertAlmostEqual(polys[1].bounds[2]-polys[1].bounds[0],8,places=3)
            self.assertAlmostEqual(polys[1].bounds[3]-polys[1].bounds[1],3,places=3)
            with fitz.open(folder/'01_PRINT.pdf') as doc:
                pix=doc[0].get_pixmap(dpi=100,alpha=True)
                isolated=extract_layers(folder/'02_MASTER.ai',['PRINT_ARTWORK'])
                self.assertEqual(isolated[0].get_pixmap(dpi=100,alpha=True).samples,pix.samples)
                # Isolated artwork must contain no red neighbour pixels.
                from PIL import Image
                im=Image.frombytes('RGBA',(pix.width,pix.height),pix.samples)
                self.assertFalse(any(r>180 and g<30 and a>100 for r,g,b,a in im.get_flattened_data()))

if __name__=='__main__':unittest.main()
