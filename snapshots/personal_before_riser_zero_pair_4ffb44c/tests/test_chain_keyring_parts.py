"""Regression tests for the two-hole applicant keyring design."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymupdf as fitz
from PIL import Image, ImageDraw
from shapely.geometry import LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from laser_paths import audit_path, cut_path


def load_geometry_module():
    # These tests use synthetic sprites; loading the module should not require
    # the applicant roster or replace it for other tests.
    roster = ROOT / 'assets/chain_keyring/applicants.json'
    read_text = Path.read_text

    def synthetic_roster(path, *args, **kwargs):
        if path == roster:
            return '{"applicants":[]}'
        return read_text(path, *args, **kwargs)

    spec = importlib.util.spec_from_file_location('test_chain_geometry', ROOT / 'scripts/chain_keyring_parts.py')
    module = importlib.util.module_from_spec(spec)
    with patch.object(Path, 'read_text', synthetic_roster):
        spec.loader.exec_module(module)
    return module


class ChainKeyringTests(unittest.TestCase):
    settings = {
        'art_height_mm': 40, 'art_top_mm': 25, 'clear_border_mm': 2.5,
        'carrier_width_mm': 13, 'hole_diameter_mm': 4,
        'hole_to_art_min_mm': 5, 'hole_to_edge_min_mm': 4,
    }

    @classmethod
    def setUpClass(cls):
        cls.chain = load_geometry_module()

    def render_fixture(self, image):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        source = Path(workspace.name) / 'sprite.png'
        image.save(source)
        entries = [{
            'prepared': source, 'nickname': 'fixture', 'world': 'fixture', 'mode': '현재 모드',
            'source_ink_px': [image.width, image.height], 'source': source.name,
            'prepared_rel': source.name, 'dropped_components': 0, 'changed_px': 0,
        }]
        paths = []
        cut, art, result = self.chain.chain_documents(
            entries, self.settings, lambda page, path: paths.append(path),
        )
        self.addCleanup(cut.close)
        self.addCleanup(art.close)
        return source, cut, art, result[0]['meta'], [audit_path(path)[1] for path in paths]

    def test_both_holes_follow_the_unchanged_upper_axis_and_artwork(self):
        image = Image.new('RGBA', (80, 80))
        ImageDraw.Draw(image).rounded_rectangle((0, 0, 79, 79), radius=10, fill=(211, 64, 35, 255))
        source, cut, art, metadata, shapes = self.render_fixture(image)
        self.assertEqual(len(shapes), 3)
        top, bottom, outline = shapes
        self.assertTrue(outline.is_valid)
        self.assertFalse(outline.interiors)
        self.assertEqual(metadata['hole_center_mm'], [30, 17])
        self.assertEqual(metadata['hole_centers_mm'], [[30, 17], [30, 73]])
        for end, hole, y in [('top', top, 17), ('bottom', bottom, 73)]:
            with self.subTest(end=end):
                self.assertTrue(outline.contains(hole))
                self.assertAlmostEqual(hole.bounds[2] - hole.bounds[0], 4, places=3)
                self.assertAlmostEqual(hole.bounds[3] - hole.bounds[1], 4, places=3)
                self.assertAlmostEqual(hole.centroid.x, 30, places=3)
                self.assertAlmostEqual(hole.centroid.y, y, places=3)
                self.assertGreaterEqual(metadata['hole_clearances_mm'][end]['to_art'], 5)
                self.assertGreaterEqual(outline.boundary.distance(hole), 4)
        self.assertGreater(cut[0].rect.height / self.chain.MM, outline.bounds[3])
        self.assertEqual(metadata['art_rect_mm'], [10, 25, 50, 65])
        self.assertEqual(metadata['art_height_mm'], 40)
        rect = fitz.Rect(*(v * self.chain.MM for v in [10, 25, 50, 65]))
        with fitz.open() as legacy:
            page = legacy.new_page(width=art[0].rect.width, height=art[0].rect.height)
            page.insert_image(rect, filename=str(source))
            self.assertEqual(page.get_pixmap(dpi=96, alpha=True).samples,
                             art[0].get_pixmap(dpi=96, alpha=True).samples)

    def test_lower_carrier_reaches_a_recessed_center_without_changing_upper_outline(self):
        image = Image.new('RGBA', (80, 80))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 79, 30), fill=(39, 96, 203, 255))
        draw.rectangle((0, 30, 18, 79), fill=(39, 96, 203, 255))
        _, _, _, metadata, (top, bottom, outline) = self.render_fixture(image)

        _, body, _ = self.chain.character_documents(image, 40, 2.5, (10, 25))
        old_center = LineString([(30, 20), (30, 70)])
        self.assertGreater(62 - body.intersection(old_center).bounds[3], 6.5)
        top_carrier = LineString([(30, 28), (30, 16)]).buffer(6.5, quad_segs=32)
        old_outline = audit_path(cut_path(unary_union([body, top_carrier])))[1]
        upper = box(0, 0, 60, 25)
        self.assertLess(outline.intersection(upper).boundary.hausdorff_distance(
            old_outline.intersection(upper).boundary), .035)
        self.assertTrue(outline.contains(top))
        self.assertTrue(outline.contains(bottom))
        self.assertTrue(outline.is_valid)
        self.assertFalse(outline.interiors)
        neck = outline.intersection(LineString([(0, 53), (65, 53)]))
        self.assertTrue(any(part.length >= 12.9 for part in neck.geoms))
        self.assertEqual(metadata['hole_clearances_mm']['bottom']['to_edge'], 4.5)


if __name__ == '__main__':
    unittest.main()
