"""The persisted Len/PAD production slots must match the approved dimensions."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_a3_release import polygon_of,len_slot_fit


class CanonicalLenSlotTests(unittest.TestCase):
    def test_all_four_base_assets_preserve_outer_and_slot_centres(self):
        current=json.loads((ROOT/'configs/individual_contours.json').read_text())['parts']
        previous=json.loads(subprocess.check_output(
            ['git','show','e4d03cdfa6d1a2656505a08bc59e41c6b806767b:configs/individual_contours.json'],cwd=ROOT))['parts']
        for ident,thickness in [('len_3T_07','3T'),('len_5T_07','5T'),
                                ('len_pad_3T_07','3T'),('len_pad_5T_07','5T')]:
            with self.subTest(ident=ident):
                before=previous[ident];after=current[ident]
                self.assertEqual(before['source_bounds_mm'],after['source_bounds_mm'])
                self.assertEqual(before['paths'][-1],after['paths'][-1])
                self.assertEqual(len(after['paths']),9)
                remaining=[polygon_of(path) for path in after['paths'][:-1]]
                target_length,target_width=len_slot_fit(thickness)
                for path in before['paths'][:-1]:
                    old=polygon_of(path)
                    current_slot=min(remaining,key=lambda p:p.centroid.distance(old.centroid))
                    self.assertLess(current_slot.centroid.distance(old.centroid),.002)
                    rect=current_slot.minimum_rotated_rectangle
                    coords=list(rect.exterior.coords)
                    lengths=sorted([((coords[1][0]-coords[0][0])**2+(coords[1][1]-coords[0][1])**2)**.5,
                                    ((coords[2][0]-coords[1][0])**2+(coords[2][1]-coords[1][1])**2)**.5])
                    self.assertAlmostEqual(lengths[0],target_width,delta=.002)
                    self.assertAlmostEqual(lengths[1],target_length,delta=.002)
                    remaining.remove(current_slot)


if __name__=='__main__':unittest.main()
