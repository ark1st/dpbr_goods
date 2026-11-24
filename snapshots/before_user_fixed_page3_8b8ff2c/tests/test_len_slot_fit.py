"""Kerf/fit compensation for Len mounting slots (issue #1)."""
import sys,unittest,math
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'));sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from shapely.geometry import box
from laser_paths import slot_path,audit_path,cut_path
from build_a3_release import len_slot_fit,compensate_len_slots,CONFIG

def size(poly):
    c=np.array(poly.minimum_rotated_rectangle.exterior.coords)
    return sorted([math.hypot(*(c[1]-c[0])),math.hypot(*(c[2]-c[1]))],reverse=True)

def entry(poly,protected=False):
    path=cut_path(poly);stats,actual=audit_path(path)
    return dict(path=path,poly=actual,protected=protected,stats=stats)

def rounded(cx,cy,l,w,r=.35):
    return box(cx-l/2+r,cy-w/2+r,cx+l/2-r,cy+w/2-r).buffer(r,quad_segs=16)

class LenSlotFitTests(unittest.TestCase):
    def test_standard_values_and_formula(self):
        self.assertEqual(len_slot_fit('3T'),(17.9,2.9))
        self.assertEqual(len_slot_fit('5T'),(17.8,4.85))
        fit=CONFIG['len_slot_fit']
        for t,(length,width) in [('3T',len_slot_fit('3T')),('5T',len_slot_fit('5T'))]:
            v=fit['thickness'][t]
            # After cutting: slot grows one kerf, tab shrinks one kerf.
            self.assertAlmostEqual(width+v['kerf_mm']-v['part_thickness_mm'],v['thickness_clearance_mm'],9)
            self.assertAlmostEqual((length+v['kerf_mm'])-(fit['tab_width_mm']-v['kerf_mm']),v['side_clearance_mm'],9)

    def test_slot_path_is_exact_at_any_angle(self):
        for angle in [0,15,90,135]:
            _,poly=audit_path(slot_path((40,30),angle,17.9,2.9,.35))
            a,b=size(poly)
            self.assertAlmostEqual(a,17.9,5);self.assertAlmostEqual(b,2.9,5)
            self.assertAlmostEqual(poly.centroid.x,40,6);self.assertAlmostEqual(poly.centroid.y,30,6)

    def test_only_nominal_len_slots_change(self):
        outer=entry(box(0,0,120,60))
        len_slot=entry(rounded(30,20,18.8,3))
        cadena=entry(rounded(80,20,20.2,3.2))
        guarded=entry(rounded(60,45,18.8,3),protected=True)
        piece=dict(paths=[outer,len_slot,cadena,guarded],bounds=outer['poly'].bounds)
        before={id(e):e['path'] for e in piece['paths']}
        b=len_slot['poly'].bounds;mid=((b[0]+b[2])/2,(b[1]+b[3])/2)
        self.assertEqual(compensate_len_slots([piece],'3T'),1)
        a,b=size(len_slot['poly'])
        self.assertAlmostEqual(a,17.9,4);self.assertAlmostEqual(b,2.9,4)
        self.assertAlmostEqual(len_slot['poly'].centroid.x,mid[0],6)
        self.assertAlmostEqual(len_slot['poly'].centroid.y,mid[1],6)
        self.assertEqual(len_slot['slot_fit']['angle_degrees']%180,0)
        for e in [outer,cadena,guarded]:self.assertEqual(e['path'],before[id(e)])

    def test_mixed_sheet_counts_only_the_len_owned_exported_slots(self):
        import pymupdf as fitz
        from build_a3_release import draw_path,polygon_of,MM
        from verify_a3_release import len_slot_counts
        # A Yanggeum base legitimately retains its nominal 18.8 x 3 slot.
        # Seven corrected Len slots plus one nominal Len slot must still fail.
        for wrong_len_slot in (False,True):
            with self.subTest(wrong_len_slot=wrong_len_slot), TemporaryDirectory() as tmp:
                doc=fitz.open();page=doc.new_page(width=220*MM,height=100*MM)
                owned=[]
                for i in range(8):
                    length,width=(18.8,3) if wrong_len_slot and i==0 else len_slot_fit('3T')
                    path=slot_path((20+i*24,20),0,length,width,.35)
                    draw_path(page,path);owned.append(list(polygon_of(path).exterior.coords))
                other=slot_path((20,60),0,18.8,3,.35)
                draw_path(page,other)
                file=Path(tmp)/'03_CUT_ONLY.pdf';doc.save(file);doc.close()
                spec={'parts':[{'source':'len_3T','expected_paths':owned},
                               {'source':'yanggum_stand','expected_paths':[list(polygon_of(other).exterior.coords)]}]}
                counts=len_slot_counts(file,'3T',spec,'len_3T')
                expected={'nominal':1,'compensated':7} if wrong_len_slot else {'nominal':0,'compensated':8}
                self.assertEqual(counts,expected)
                if wrong_len_slot:self.assertNotEqual(counts,{'nominal':0,'compensated':8})

if __name__=='__main__':unittest.main()
