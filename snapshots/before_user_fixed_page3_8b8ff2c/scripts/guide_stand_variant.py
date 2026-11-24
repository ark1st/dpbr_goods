"""One optional Remsha guide-size stand, separate from the main production set.

Assembled height is 60 mm measured from the underside of a 3 mm base to the
top of the panel. The original 18 mm mounting tab is retained; the additional
4 mm circular hole is for a ring and is not the mounting opening.
"""
import json
from pathlib import Path

import pymupdf as fitz
from shapely.geometry import Point, box

from additional_stands import ROOT, MM, prepare_sprites
from chain_keyring_parts import stand_documents, stand_axis_width
from build_a3_release import draw_path, pieces_from
from laser_paths import cut_path

TARGET_ASSEMBLED_MM = 60.0
BASE_THICKNESS_MM = 3.0
TAB_DEPTH_MM = 2.6
TARGET_PANEL_MM = TARGET_ASSEMBLED_MM - BASE_THICKNESS_MM + TAB_DEPTH_MM
BASE_DIAMETER_MM = 40.0
RING_DIAMETER_MM = 4.0
SLOT_LENGTH_MM = 18.8
SLOT_WIDTH_MM = 3.0


def build_variant():
    """Return [character plate, circular base] as 1:1 cutting and art pieces."""
    settings = json.loads((ROOT / 'configs/a3_release.json').read_text(encoding='utf-8'))['chain_keyring_products']['stand'].copy()
    assert settings['tab_width_mm'] == 18 and settings['tab_bottom_clearance_mm'] == .4
    entry = next(e for e in prepare_sprites() if e['nickname'] == '렘샤')
    # The original source uses a 60 mm art height, with a stable clear border
    # and tab. Correct the art height from the measured actual outline, never
    # scaling the 18 mm tab or the base slot.
    settings['art_height_mm'] = 60.0
    cut0, art0, result0 = stand_documents([entry], settings, draw_path, thickness='3T')
    old = pieces_from(cut0, art0, None, 'guide_probe', smooth=True)[0]
    original_height = old['bounds'][3] - old['bounds'][1]
    settings['art_height_mm'] = 60.0 - (original_height - TARGET_PANEL_MM)
    cut, art, meta = stand_documents([entry], settings, draw_path, thickness='3T')
    initial = pieces_from(cut, art, None, 'guide_stand_렘샤', smooth=True)
    assert len(initial) == 2 and len(initial[0]['paths']) == 1
    panel = initial[0]
    panel_height = panel['bounds'][3] - panel['bounds'][1]
    if abs(panel_height - TARGET_PANEL_MM) >= .001:
        settings['art_height_mm'] -= panel_height - TARGET_PANEL_MM
        cut, art, meta = stand_documents([entry], settings, draw_path, thickness='3T')
        initial = pieces_from(cut, art, None, 'guide_stand_렘샤', smooth=True)
        panel = initial[0]
        panel_height = panel['bounds'][3] - panel['bounds'][1]
    assert abs(panel_height - TARGET_PANEL_MM) < .003, ('Panel height', panel_height)
    char_meta = meta[0]['char_meta']
    cx, shoulder = char_meta['tab_center_mm']
    assert abs(stand_axis_width(panel['poly'], cx, shoulder + .4) - 18) < .005
    assert abs(char_meta['tab_depth_mm'] - TAB_DEPTH_MM) < .0001

    center_x, center_y = 140.0, 45.0
    base = Point(center_x, center_y).buffer(BASE_DIAMETER_MM / 2, quad_segs=128)
    ring = Point(center_x, center_y - 14).buffer(RING_DIAMETER_MM / 2, quad_segs=128)
    radius = .35
    slot = box(center_x - SLOT_LENGTH_MM / 2 + radius, center_y - SLOT_WIDTH_MM / 2 + radius,
               center_x + SLOT_LENGTH_MM / 2 - radius, center_y + SLOT_WIDTH_MM / 2 - radius).buffer(radius, quad_segs=32)
    assert base.contains(slot) and base.contains(ring) and slot.disjoint(ring)
    assert base.boundary.distance(ring.boundary) > 3.99
    assert slot.boundary.distance(ring.boundary) > 10

    output_cut = fitz.open()
    cp = output_cut.new_page(width=180 * MM, height=140 * MM)
    draw_path(cp, panel['paths'][0]['path'])
    # Each cutting outline, including exact circular hole, is emitted by the
    # shared laser path fitter; the outer contour contains both holes.
    for shape in [base, slot, ring]:
        draw_path(cp, cut_path(shape))
    output_art = fitz.open()
    ap = output_art.new_page(width=180 * MM, height=140 * MM)
    ap.show_pdf_page(art[0].rect, art, 0)
    pieces = pieces_from(output_cut, output_art, None, 'guide_stand_렘샤')
    assert len(pieces) == 2 and [len(p['paths']) for p in pieces] == [1, 3]
    pieces[0]['design_metadata'] = {**char_meta, 'guide_variant': True,
        'assembled_height_mm': BASE_THICKNESS_MM + panel_height - TAB_DEPTH_MM,
        'target_assembled_height_mm': TARGET_ASSEMBLED_MM, 'panel_outer_height_mm': panel_height,
        'assembly_formula_mm': [BASE_THICKNESS_MM, panel_height, -TAB_DEPTH_MM],
        'guide_comparison_only': True, 'physical_fit_test': False}
    pieces[1]['design_metadata'] = {'part': 'base', 'nickname': '렘샤', 'mode': '현재 모드',
        'guide_variant': True, 'diameter_mm': BASE_DIAMETER_MM,
        'slot_mm': [SLOT_LENGTH_MM, SLOT_WIDTH_MM], 'slot_center_mm': [center_x, center_y],
        'ring_hole_diameter_mm': RING_DIAMETER_MM,
        'ring_hole_center_mm': [center_x, center_y - 14],
        'ring_to_outer_mm': base.boundary.distance(ring.boundary),
        'ring_to_slot_mm': ring.boundary.distance(slot.boundary),
        'material_thickness_mm': BASE_THICKNESS_MM, 'guide_comparison_only': True,
        'physical_fit_test': False}
    return pieces


if __name__ == '__main__':
    records = build_variant()
    print(json.dumps([{'id': p['id'], 'bounds_mm': p['bounds'],
                       'contours': len(p['paths']), 'metadata': p['design_metadata']}
                      for p in records], ensure_ascii=False, indent=2))
