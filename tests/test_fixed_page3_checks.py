import sys
import unittest
import tempfile
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fixed_page3_checks as checks


def square(ident, x, y=10):
    return {'id': ident, 'expected_paths': [[(x,y), (x+5,y), (x+5,y+5), (x,y+5), (x,y)]]}


class FixedPage3Checks(unittest.TestCase):
    def setUp(self):
        self.ids = patch.object(checks, 'FIXED_IDS', {'fixed_01', 'fixed_02'})
        self.gaps = patch.object(checks, 'BASELINE_GAPS', {frozenset(('fixed_01', 'fixed_02')): 2.5})
        self.edges = patch.object(checks, 'BASELINE_EDGES', {})
        for p in (self.ids, self.gaps, self.edges): p.start(); self.addCleanup(p.stop)
        self.rows = [square('fixed_01', 10), square('fixed_02', 17.5), square('added', 26)]

    def test_only_the_measured_existing_pair_is_permitted(self):
        checks.check_page_geometry(self.rows)
        with self.assertRaises(AssertionError):
            checks.check_page_geometry([*self.rows[:2], square('added', 25)])
        with self.assertRaises(AssertionError):
            checks.check_page_geometry([self.rows[0], square('fixed_02', 17.6), self.rows[2]])

    def test_new_piece_must_respect_edge_margin(self):
        with self.assertRaises(AssertionError):
            checks.check_page_geometry([*self.rows[:2], square('added', 26, y=7)])

    def test_duplicate_id_is_rejected(self):
        with self.assertRaises(AssertionError):
            checks.check_page_geometry([*self.rows, square('added', 40)])

    def test_frozen_file_bytes_and_inventory_are_locked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = []
            for name in ('one', 'two'):
                folder = root / 'output' / name
                folder.mkdir(parents=True)
                (folder / 'plate.pdf').write_bytes(b'original')
                pages.append({'folder': name, 'files': {'plate.pdf': hashlib.sha256(b'original').hexdigest()}})
            checks.verify_frozen_pages(root, {'frozen_pages': pages})
            (root / 'output' / 'one' / 'plate.pdf').write_bytes(b'changed')
            with self.assertRaises(AssertionError):
                checks.verify_frozen_pages(root, {'frozen_pages': pages})
            (root / 'output' / 'one' / 'plate.pdf').write_bytes(b'original')
            (root / 'output' / 'two' / 'extra.pdf').write_bytes(b'extra')
            with self.assertRaises(AssertionError):
                checks.verify_frozen_pages(root, {'frozen_pages': pages})

    def test_original_hairline_is_limited_to_matching_source_contour(self):
        import pymupdf as fitz
        from shapely.geometry import box
        from verify_laser_paths import inspect_pdf, MM
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cut.pdf'
            doc = fitz.open()
            page = doc.new_page(width=100*MM, height=100*MM)
            page.draw_rect(fitz.Rect(10*MM, 10*MM, 15*MM, 15*MM), color=(1,0,0), width=.01)
            doc.save(path)
            doc.close()
            with self.assertRaises(ValueError):
                inspect_pdf(path)
            result = inspect_pdf(path, fixed_strokes=[(box(10,10,15,15), .01/MM)])
            self.assertFalse(result['errors'])
            with self.assertRaises(ValueError):
                inspect_pdf(path, fixed_strokes=[(box(20,20,25,25), .01/MM)])
            with self.assertRaises(ValueError):
                inspect_pdf(path, fixed_strokes=[(box(10,10,15,15), .001)])

    def test_fixed_page_requires_all_requested_additions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'configs').mkdir()
            (root/'configs/individual_contours.json').write_text('{"parts": {}}')
            (root/'configs/fixed_page3_additions.json').write_text(json.dumps({'placements': []}))
            with self.assertRaisesRegex(AssertionError, 'Missing a requested addition'):
                checks.verify_fixed_additions(root, {'parts': []})

    def test_exported_holes_must_match_too(self):
        outer = [(0,0),(10,0),(10,10),(0,10),(0,0)]
        hole = [(2,2),(3,2),(3,3),(2,3),(2,2)]
        spec = {'parts': [{'expected_paths': [outer, hole]}]}
        paths = ['M 0 0 L 10 0 L 10 10 L 0 10 Z', 'M 2 2 L 3 2 L 3 3 L 2 3 Z']
        checks.verify_exported_paths(spec, paths)
        with self.assertRaises(AssertionError):
            checks.verify_exported_paths(spec, [paths[0], 'M 4 4 L 5 4 L 5 5 L 4 5 Z'])

    def test_extra_muhani_keyring_is_allowed_but_missing_keyring_is_not(self):
        from collections import Counter
        counts=Counter(muhani_stand_body=4,muhani_stand_base=4,muhani_keyring=5)
        self.assertEqual(checks.verify_muhani_counts(counts),(4,1))
        counts['muhani_keyring']=3
        with self.assertRaisesRegex(AssertionError,'Incomplete Muhani set'):
            checks.verify_muhani_counts(counts)


if __name__ == '__main__':
    unittest.main()
