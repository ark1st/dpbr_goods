"""Regression tests for the physically observed oversegmented cut failure."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tmp/pylibs')]
from shapely.geometry import Point,Polygon,box,LineString
from shapely.ops import unary_union
from svgpathtools import parse_path
from laser_paths import cut_path,audit_path,fitted,MAX_DEVIATION_MM


class LaserRegression(unittest.TestCase):
    def test_actual_failed_carabiner_is_rejected_then_repaired(self):
        d=(ROOT/'tests/fixtures/carabiner_D_before.txt').read_text()
        with self.assertRaisesRegex(ValueError,'Too many segments|Zero-length'):
            audit_path(d)
        source=parse_path(d);p=Polygon([(s.start.real,s.start.imag) for s in source])
        result,shape=audit_path(cut_path(p))
        self.assertLess(result['segments'],100)
        self.assertGreater(result['curves'],0)
        self.assertLess(p.boundary.hausdorff_distance(shape.boundary),MAX_DEVIATION_MM)
        self.assertTrue(shape.is_valid)

    def test_circle_center_and_diameter_preserved(self):
        p=Point(31,44).buffer(.7,quad_segs=96)
        path=parse_path(cut_path(p))
        self.assertEqual(len(path),4)
        self.assertLess(max(abs(a-b) for a,b in zip(path.bbox(),(30.3,31.7,43.3,44.7))),1e-6)

    def test_tab_and_chamfers_preserved(self):
        body=box(0,0,60,50)
        tab=Polygon([(21,49),(39,49),(39,52.2),(38.6,52.6),(21.4,52.6),(21,52.2)])
        p=unary_union([body,tab]);_,q=audit_path(cut_path(p))
        self.assertAlmostEqual(q.intersection(LineString([(0,51),(60,51)])).length,18,places=6)
        self.assertAlmostEqual(q.bounds[3],52.6,places=6)
        self.assertLess(p.hausdorff_distance(q),1e-6)

    def test_open_contour_rejected(self):
        with self.assertRaisesRegex(ValueError,'Open'):audit_path('M0 0 L10 0 L10 10')

    def test_micro_zigzag_rejected(self):
        d='M0 0 L.02 .01 L.04 0 L.06 .01 L.08 0 L10 0 L10 10 L0 10 Z'
        with self.assertRaisesRegex(ValueError,'Micro-line'):audit_path(d)

    def test_self_crossing_rejected(self):
        with self.assertRaisesRegex(ValueError,'Self-intersection'):audit_path('M0 0 L10 10 L0 10 L10 0 Z')

    def test_zero_edge_rejected(self):
        with self.assertRaisesRegex(ValueError,'Zero-length'):audit_path('M0 0 L0 0 L10 0 L10 10 L0 10 Z')

    def test_protected_no_op_is_measured_not_silently_ignored(self):
        stats,_=audit_path('M0 0 L0 0 L10 0 L10 10 L0 10 Z',allow_original_numerics=True)
        self.assertEqual(stats['original_numerical_notes'],[{'kind':'zero_length_no_op','count':1}])

    def test_protected_original_cannot_bypass_real_intersections(self):
        with self.assertRaisesRegex(ValueError,'Self-intersection'):
            audit_path('M0 0 L10 10 L0 10 L10 0 Z',allow_original_numerics=True)

if __name__=='__main__':unittest.main()
