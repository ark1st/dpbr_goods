"""Regression checks for real-size A3 packing and rigid mechanical dimensions."""
import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'));sys.path.insert(0,str(ROOT/'scripts'))
from shapely.geometry import box,Point
from build_a3_release import pack,shifted_poly,SIZE,MARGIN,GAP

class A3PackingTests(unittest.TestCase):
    def test_len_dot_and_four_keyrings_5t_still_fit_one_a3(self):
        sizes=json.loads((ROOT/'tests/fixtures/len_dot_linked_5t_sizes.json').read_text())
        self.assertEqual(len(sizes),12)
        self.assertFalse(any('fit' in row['id'] or 'test' in row['id'] for row in sizes))
        pieces=[]
        for row in sizes:
            p=box(0,0,*row['size_mm'])
            pieces.append({'id':row['id'],'bounds':p.bounds,'poly':p})
        pages=pack(pieces)
        self.assertEqual(len(pages),1)
        placed=pages[0]['placements']
        self.assertEqual({p['piece']['id'] for p in placed},{p['id'] for p in pieces})
        for i,p in enumerate(placed):
            actual=shifted_poly(p['piece']['poly'],p)
            self.assertAlmostEqual(actual.area,p['piece']['poly'].area,6)
            for q in placed[:i]:self.assertGreaterEqual(actual.distance(shifted_poly(q['piece']['poly'],q)),GAP-.001)

    def test_keyrings_allocated_once_across_selected_pair(self):
        c=json.loads((ROOT/'configs/a3_release.json').read_text())
        allocated=sum(c['linked_allocation'].values(),[])
        expected={f'supplied_saetui_{i:02}' for i in range(1,5)}|{f'{n}_01' for n in ['tuiing','golden','burnt','unfried']}
        self.assertEqual(set(allocated),expected)
        self.assertEqual(len(allocated),8)
        self.assertEqual(c['cadena_source_part_ids'],['ascent_01','ascent_11','ascent_12','ascent_13','ascent_14'])
        self.assertNotIn('03_linked_keyrings',c['current_groups'])
        self.assertNotIn('04_ascent_original',c['current_groups'])

    def test_ascent_inventory_fits_two_without_scaling(self):
        pieces=[]
        for i in range(31):
            w,h=(104,62.807) if i<26 else (104,30)
            p=box(100,200,100+w,200+h)
            pieces.append({'id':str(i),'bounds':p.bounds,'poly':p})
        pages=pack(pieces)
        self.assertEqual(len(pages),2)
        self.assertEqual(sum(len(p['placements']) for p in pages),31)
        for page in pages:
            polys=[shifted_poly(p['piece']['poly'],p) for p in page['placements']]
            for i,p in enumerate(polys):
                self.assertTrue(box(MARGIN-.001,MARGIN-.001,SIZE[0]-MARGIN+.001,SIZE[1]-MARGIN+.001).contains(p))
                for q in polys[:i]:self.assertGreaterEqual(p.distance(q),GAP-.001)
    def test_rotation_preserves_hole_diameter_and_slot(self):
        place={'piece':{'bounds':(10,20,110,80)},'x':8,'y':8,'rotation':90}
        hole=Point(30,40).buffer(2,quad_segs=64)
        result=shifted_poly(hole,place)
        self.assertAlmostEqual(result.area,hole.area,8)
        self.assertAlmostEqual(result.bounds[2]-result.bounds[0],4,8)
        self.assertAlmostEqual(result.centroid.x,28,8)
        self.assertAlmostEqual(result.centroid.y,88,8)
        slot=shifted_poly(box(30,40,50.2,43.2),place)
        self.assertAlmostEqual(slot.bounds[2]-slot.bounds[0],3.2,8)
        self.assertAlmostEqual(slot.bounds[3]-slot.bounds[1],20.2,8)
    def test_oversize_part_is_rejected_not_shrunk(self):
        p=box(0,0,500,300)
        with self.assertRaises(AssertionError):pack([{'id':'oversize','bounds':p.bounds,'poly':p}])

if __name__=='__main__':unittest.main()
