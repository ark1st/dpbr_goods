"""Kerf/fit compensation for Len mounting slots (issue #1)."""
import sys,unittest,math
from pathlib import Path
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

if __name__=='__main__':unittest.main()
