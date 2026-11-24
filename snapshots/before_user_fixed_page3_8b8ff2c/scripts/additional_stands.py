"""Two additional 3T stands from the user's pinned Maple.GG avatar downloads.

The original PNG bytes stay unchanged. Only transparent canvas is trimmed;
pixel art is enlarged with nearest-neighbour sampling. Character and matching
base remain independently movable parts, with source coordinates in mm.
"""
from pathlib import Path
import hashlib
import json
import math
import sys

import numpy as np
from PIL import Image
import pymupdf as fitz
from shapely.geometry import box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pylibs'))
from chain_keyring_parts import MM, stand_documents, stand_axis_width
from laser_paths import audit_path, cut_path
from build_a3_release import draw_path, pieces_from

ASSET_DIR = ROOT / 'assets/chain_keyring/추가스탠드'
NAMES = [('적매화검', '크로아'), ('렘샤', '베라')]


def prepare_sprites():
    """Trim transparent margins and preserve every remaining RGBA pixel."""
    provenance = json.loads((ASSET_DIR / 'provenance.json').read_text(encoding='utf-8'))
    entries = []
    for name, world in NAMES:
        row = next(r for r in provenance['records'] if r['nickname'] == name and r['kind'] == 'stand300')
        source = ROOT / row['file']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256']
        with Image.open(source) as image:
            im = image.convert('RGBA')
        bounds = im.getchannel('A').getbbox()
        assert bounds is not None
        crop = im.crop(bounds)
        target_h = round(60 * 300 / 25.4)
        target_w = round(crop.width * target_h / crop.height)
        enlarged = crop.resize((target_w, target_h), Image.Resampling.NEAREST)
        path = ASSET_DIR / (name + '_stand60_prepared.png')
        if path.exists():
            with Image.open(path) as existing:
                assert existing.convert('RGBA').tobytes() == enlarged.tobytes(), (path, 'Different existing prepared asset')
        else:
            enlarged.save(path, dpi=(300, 300))
        entries.append({'nickname': name, 'world': world, 'mode': '현재 모드',
                        'source': source.name, 'prepared': path,
                        'prepared_rel': path.relative_to(ROOT).as_posix(),
                        'source_ink_px': list(crop.size), 'dropped_components': 0, 'changed_px': 0,
                        'crop_box_px': list(bounds), 'source_sha256': row['sha256']})
    return entries


def softened_outer(outline, meta):
    """Locally close 3 mm gaps while retaining the original silhouette and tab."""
    shoulder = meta['tab_center_mm'][1]
    x0, y0, x1, y1 = outline.bounds
    upper_box = box(x0 - 3, y0 - 3, x1 + 3, shoulder)
    lower_box = box(x0 - 3, shoulder, x1 + 3, y1 + 3)
    # Close only local indentations, rather than wrapping the art in a convex
    # hull. A tiny fitting allowance protects the approved artwork border.
    original_upper = outline.intersection(upper_box)
    upper = (original_upper.buffer(3, quad_segs=16).buffer(-3, quad_segs=16)
             .buffer(.06, quad_segs=16).intersection(upper_box))
    solid = unary_union([upper, outline.intersection(lower_box)])
    assert solid.is_valid and solid.geom_type == 'Polygon'
    path = cut_path(solid)
    _, result = audit_path(path)
    def material(geometry):
        areas = [g for g in getattr(geometry, 'geoms', (geometry,))
                 if g.geom_type == 'Polygon' and not g.is_empty]
        assert areas
        return unary_union(areas)
    # Clipping exactly through a shoulder can also produce zero-area line
    # fragments. Compare material boundaries and retain real protrusions.
    original_tab = material(outline.intersection(lower_box))
    new_tab = material(result.intersection(lower_box))
    assert original_tab.boundary.hausdorff_distance(new_tab.boundary) <= .002
    assert result.buffer(.002).covers(outline)
    cx = meta['tab_center_mm'][0]
    assert all(abs(stand_axis_width(result, cx, y) - 18) < .002
               for y in [shoulder + .2, shoulder + 2.0])
    return path


def build_stands():
    """Return four ordinary `pieces_from` records for downstream A3 placement."""
    settings = json.loads((ROOT / 'configs/a3_release.json').read_text(encoding='utf-8'))['chain_keyring_products']['stand']
    assert settings['art_height_mm'] == 60 and settings['tab_width_mm'] == 18
    assert settings['base_size_mm'] == [72, 28] and settings['slot_length_mm'] == 18.8
    records = []
    for entry in prepare_sprites():
        cut, art, meta = stand_documents([entry], settings, draw_path, thickness='3T')
        parts = pieces_from(cut, art, None, 'extra_stand_' + entry['nickname'], smooth=True)
        assert len(parts) == 2 and [len(p['paths']) for p in parts] == [1, 2]
        try:
            outer_path = softened_outer(parts[0]['poly'], meta[0]['char_meta'])
            exterior = 'locally softened 3 mm closing, original tab preserved'
        except AssertionError:
            # If a broader shape cannot preserve the complete tab interface,
            # retain the already curve-fitted supported exterior.
            outer_path = parts[0]['paths'][0]['path']
            exterior = 'curve-fitted original supported exterior; broadening rejected to preserve tab'
        broad_cut = fitz.open()
        page = broad_cut.new_page(width=cut[0].rect.width, height=cut[0].rect.height)
        draw_path(page, outer_path)
        # Internal holes and base exterior retain the source's exact paths.
        for piece_path in parts[1]['paths']:
            draw_path(page, piece_path['path'])
        pieces = pieces_from(broad_cut, art, None, 'extra_stand_' + entry['nickname'])
        assert len(pieces) == 2
        pieces[0]['design_metadata'] = meta[0]['char_meta']
        pieces[1]['design_metadata'] = meta[0]['base_meta']
        pieces[0]['design_metadata']['exterior'] = exterior
        width = pieces[0]['bounds'][2] - pieces[0]['bounds'][0]
        height = pieces[0]['bounds'][3] - pieces[0]['bounds'][1]
        assert width <= 86 and height <= 68.86, (entry['nickname'], width, height)
        assert height + 3 + 28 <= 100, (entry['nickname'], height)
        records.extend(pieces)
    return records


if __name__ == '__main__':
    results = build_stands()
    print(json.dumps([{'id': p['id'], 'bounds_mm': p['bounds'], 'contours': len(p['paths']),
                       'metadata': p['design_metadata']} for p in results], ensure_ascii=False, indent=2))
