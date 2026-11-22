"""Yanggum SD character as an acrylic mini stand and a hanging keyring.

The supplied raster is printed as-is; only cutting geometry is generated.
Every contour goes through laser_paths.cut_path, never raw traced polylines.
Mechanical interfaces follow the repository's calibrated values: 18 mm tab,
18.8 x 3.0 mm slot, 0.4 mm bottom clearance, 2.5 mm clear border, 4 mm hole.
"""
from pathlib import Path
import io, json, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon, box, LineString, Point
from shapely.ops import unary_union
from shapely import affinity
from laser_paths import cut_path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/yanggum/prepared/character_rgba.png'


def character_documents(im, height_mm, clear_border, origin_mm):
    """Scaled ink polygon and buffered cutter body for one product size."""
    alpha = np.asarray(im)[:, :, 3]
    contours, _ = cv2.findContours((alpha > 8).astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    shapes = [Polygon(c[:, 0, :]).buffer(0) for c in contours if len(c) >= 3]
    ink = unary_union(shapes)
    assert ink.geom_type == 'Polygon', ink.geom_type
    scale = height_mm / im.height
    art = affinity.scale(ink, xfact=scale, yfact=scale, origin=(0, 0))
    # Close sub-pixel notches in the cutter body, never in the printed sprite.
    body = art.buffer(clear_border + .35, quad_segs=32).buffer(-.35, quad_segs=32)
    art = affinity.translate(art, *origin_mm)
    body = affinity.translate(Polygon(body.exterior), *origin_mm)
    return art, body, scale


def section_report(poly, y0, y1, step=.25):
    """Minimum horizontal section widths between y0 and y1, ligaments split."""
    widths = []
    y = y0
    while y <= y1:
        cut = poly.intersection(LineString([(poly.bounds[0] - 1, y), (poly.bounds[2] + 1, y)]))
        if cut.geom_type == 'MultiLineString':
            parts = sorted(c.length for c in cut.geoms)
            widths.append((y, parts, sum(parts)))
        elif not cut.is_empty:
            widths.append((y, [cut.length], cut.length))
        y += step
    return widths


def stand_documents(root, thickness, draw_path, mm, settings):
    im = Image.open(SOURCE).convert('RGBA')
    art, body, scale = character_documents(im, settings['art_height_mm'], settings['clear_border_mm'], (10, 10))
    height = settings['art_height_mm']
    width = im.width * scale
    cx = 10 + width / 2
    shoulder = body.bounds[3]
    depth = float(thickness.removesuffix('T')) - settings['tab_bottom_clearance_mm']
    half = settings['tab_width_mm'] / 2
    rise = settings['bridge_rise_mm']
    bridge = box(cx - half - 1, shoulder - rise, cx + half + 1, shoulder)
    tip = .5
    tab = Polygon([(cx - half, shoulder - .1), (cx + half, shoulder - .1),
                   (cx + half, shoulder + depth - tip), (cx + half - tip, shoulder + depth),
                   (cx - half + tip, shoulder + depth), (cx - half, shoulder + depth - tip)])
    solid = unary_union([body, bridge, tab])
    assert solid.geom_type == 'Polygon' and solid.is_valid and not solid.interiors
    solid = Polygon(solid.exterior)
    for y in [shoulder + .2, shoulder + depth - .6]:
        section = solid.intersection(LineString([(0, y), (200, y)]))
        assert abs(section.length - settings['tab_width_mm']) < .002, (y, section.length)

    bw, bh = settings['base_size_mm']
    bx, by = 10, 95
    br = settings['base_corner_radius_mm']
    base = Polygon(box(bx + br, by + br, bx + bw - br, by + bh - br).buffer(br, quad_segs=32).exterior)
    scx, scy = bx + bw / 2, by + bh / 2
    sl = settings['slot_length_mm']
    sw = float(thickness.removesuffix('T'))
    sr = settings['slot_corner_radius_mm']
    slot = box(scx - (sl - 2 * sr) / 2, scy - (sw - 2 * sr) / 2, scx + (sl - 2 * sr) / 2, scy + (sw - 2 * sr) / 2).buffer(sr, quad_segs=16)
    assert slot.within(base) and base.boundary.distance(slot) > 8, base.boundary.distance(slot)

    cut = fitz.open()
    page = cut.new_page(width=100 * mm, height=130 * mm)
    draw_path(page, cut_path(solid))
    draw_path(page, cut_path(base))
    draw_path(page, cut_path(slot))
    art_doc = fitz.open()
    apage = art_doc.new_page(width=100 * mm, height=130 * mm)
    buffer = io.BytesIO()
    im.save(buffer, format='PNG')
    apage.insert_image(fitz.Rect(10 * mm, 10 * mm, (10 + width) * mm, (10 + height) * mm), stream=buffer.getvalue())

    above = section_report(solid, shoulder - rise, shoulder + 25)
    weakest = min(above, key=lambda r: r[2])
    meta = {
        'character': {'part': 'character', 'art_height_mm': height, 'art_width_mm': width,
                      'source_px': [im.width, im.height], 'effective_ppi': round(im.height / height * 25.4, 1),
                      'clear_border_mm': settings['clear_border_mm'], 'tab_width_mm': settings['tab_width_mm'],
                      'tab_depth_mm': depth, 'slot_target_mm': [sl, sw], 'bridge_rise_mm': rise,
                      'weakest_section_mm': {'y_mm': round(weakest[0], 2), 'ligament_widths_mm': [round(w, 2) for w in weakest[1]],
                                             'total_mm': round(weakest[2], 2)},
                      'physical_fit_test': False},
        'base': {'part': 'base', 'size_mm': [bw, bh], 'corner_radius_mm': settings['base_corner_radius_mm'],
                 'slot_mm': [sl, sw], 'slot_corner_radius_mm': sr,
                 'slot_to_edge_mm': round(base.boundary.distance(slot), 2), 'material_thickness_mm': sw,
                 'physical_fit_test': False},
    }
    return cut, art_doc, meta


def keyring_documents(root, thickness, draw_path, mm, settings):
    im = Image.open(SOURCE).convert('RGBA')
    art_top = 25
    art, body, scale = character_documents(im, settings['art_height_mm'], settings['clear_border_mm'], (10, art_top))
    height = settings['art_height_mm']
    width = im.width * scale
    cx = 10 + width / 2
    carrier = LineString([(cx, art_top + 3), (cx, art_top - 9)]).buffer(settings['carrier_width_mm'] / 2, quad_segs=32)
    solid = unary_union([body, carrier])
    assert solid.geom_type == 'Polygon' and solid.is_valid and not solid.interiors
    solid = Polygon(solid.exterior)
    hole = Point(cx, art_top - 8).buffer(settings['hole_diameter_mm'] / 2, quad_segs=64)
    hole_art = hole.distance(art)
    hole_edge = solid.boundary.distance(hole)
    assert hole.within(solid)
    assert hole_art >= settings['hole_to_art_min_mm'], hole_art
    assert hole_edge >= settings['hole_to_edge_min_mm'], hole_edge

    cut = fitz.open()
    page = cut.new_page(width=70 * mm, height=80 * mm)
    draw_path(page, cut_path(solid))
    draw_path(page, cut_path(hole))
    art_doc = fitz.open()
    apage = art_doc.new_page(width=70 * mm, height=80 * mm)
    buffer = io.BytesIO()
    im.save(buffer, format='PNG')
    apage.insert_image(fitz.Rect(10 * mm, art_top * mm, (10 + width) * mm, (art_top + height) * mm), stream=buffer.getvalue())

    meta = {'part': 'keyring', 'art_height_mm': height, 'art_width_mm': width,
            'source_px': [im.width, im.height], 'effective_ppi': round(im.height / height * 25.4, 1),
            'clear_border_mm': settings['clear_border_mm'], 'hole_diameter_mm': settings['hole_diameter_mm'],
            'hole_to_art_mm': round(hole_art, 2), 'hole_to_edge_mm': round(hole_edge, 2),
            'carrier_width_mm': settings['carrier_width_mm'], 'physical_fit_test': False}
    return cut, art_doc, meta


def yanggum_pieces():
    from build_a3_release import pieces_from, draw_path, MM, CONFIG
    spec = CONFIG['yanggum_products']
    cut, art, meta = stand_documents(ROOT, '3T', draw_path, MM, spec['stand'])
    stand = pieces_from(cut, art, None, 'yanggum_stand', smooth=True)
    stand[0]['design_metadata'] = meta['character']
    stand[1]['design_metadata'] = meta['base']
    cut, art, kmeta = keyring_documents(ROOT, '3T', draw_path, MM, spec['keyring'])
    keyring = pieces_from(cut, art, None, 'yanggum_keyring', smooth=True)
    keyring[0]['design_metadata'] = kmeta
    return {'07_yanggum_stand/3T': stand, '08_yanggum_keyring/3T': keyring}


def render_assembly(root, out, settings):
    """Dimension-faithful assembly reference drawn from the real cut polygons."""
    from build_a3_release import draw_path, MM, polygon_of
    from verify_laser_paths import contours
    from laser_paths import fitted
    from shapely import affinity
    cut, art, meta = stand_documents(root, '3T', draw_path, MM, settings)
    polys = [polygon_of(s) for d in cut[0].get_drawings() for s in contours(d)]
    char_poly, base_poly, slot_poly = polys
    doc = fitz.open()
    page = doc.new_page(width=180 * MM, height=110 * MM)
    page.draw_rect(page.rect, color=None, fill=(.98, .98, .98))
    def outline(p):
        for kind, c in fitted(p.wkb)[0]:
            pts = [fitz.Point(*(q * MM)) for q in c]
            if kind == 'C': page.draw_bezier(*pts)
            else: page.draw_line(pts[0], pts[-1])
    base_shift = (14 - base_poly.bounds[0], 18 - base_poly.bounds[1])
    outline(affinity.translate(base_poly, *base_shift))
    outline(affinity.translate(slot_poly, *base_shift))
    b = char_poly.bounds
    ground = 95
    outline(affinity.translate(char_poly, 104 - b[0], ground - b[3]))
    cx = 104 + (b[0] + b[2]) / 2 - b[0]
    page.draw_rect(fitz.Rect((cx - 36) * MM, ground * MM, (cx + 36) * MM, (ground + 3) * MM), color=(.45, .45, .45), width=.2 * MM)
    page.draw_line((70 * MM, ground * MM), (176 * MM, ground * MM), color=(.4, .4, .4), width=.25 * MM)
    for x, y, text, size in [(10, 12, 'Yanggum SD mini stand - assembly reference (real cut geometry)', 9),
                              (14, 52, 'BASE top view: 72 x 28 mm, slot 18.8 x 3.0 mm', 7),
                              (104, 20, 'FRONT: figure 60 mm, tab 18 x 2.6 mm into the slot', 7),
                              (10, 106, '3T acrylic. Tab clears the base bottom by 0.4 mm. Physical fit not cut-tested.', 7)]:
        page.insert_text((x * MM, y * MM), text, fontsize=size)
    page.get_pixmap(dpi=150, alpha=False).save(out)


def render_final_preview(root, out, spec):
    """Mockup of the shipped products from the real raster and cut polygons."""
    import math
    from PIL import ImageDraw, ImageFont
    from build_a3_release import draw_path, MM, polygon_of
    from verify_laser_paths import contours
    stand_cut, _, _ = stand_documents(root, '3T', draw_path, MM, spec['stand'])
    ring_cut, _, _ = keyring_documents(root, '3T', draw_path, MM, spec['keyring'])
    stand_polys = [polygon_of(s) for d in stand_cut[0].get_drawings() for s in contours(d)]
    ring_polys = [polygon_of(s) for d in ring_cut[0].get_drawings() for s in contours(d)]
    char_poly, base_poly, slot_poly = stand_polys
    key_solid, key_hole = ring_polys
    art = Image.open(SOURCE).convert('RGBA')
    pxmm = 12
    W, H = 230, 150
    img = Image.new('RGB', (W * pxmm, H * pxmm), (247, 247, 250))
    dr = ImageDraw.Draw(img)

    def layer_for(poly, art_rect, paste_px, punch=(), back=None):
        b = poly.bounds
        w = math.ceil((b[2] - b[0]) * pxmm) + 4
        h = math.ceil((b[3] - b[1]) * pxmm) + 4
        layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        pts = [((x - b[0]) * pxmm + 2, (y - b[1]) * pxmm + 2) for x, y in poly.exterior.coords]
        ld.polygon(pts, fill=(255, 255, 255, 46))
        art_px = (max(1, int(round((art_rect[2] - art_rect[0]) * pxmm))),
                  max(1, int(round((art_rect[3] - art_rect[1]) * pxmm))))
        a = art.resize(art_px, Image.LANCZOS)
        layer.paste(a, (int(round((art_rect[0] - b[0]) * pxmm)) + 2, int(round((art_rect[1] - b[1]) * pxmm)) + 2), a)
        ld.polygon(pts, outline=(206, 208, 214, 255), width=2)
        for hpoly in punch:
            hb = hpoly.bounds
            box = [int((hb[0] - b[0]) * pxmm) + 2, int((hb[1] - b[1]) * pxmm) + 2,
                   int((hb[2] - b[0]) * pxmm) + 2, int((hb[3] - b[1]) * pxmm) + 2]
            mask = Image.new('L', (w, h), 0)
            ImageDraw.Draw(mask).ellipse(box, fill=255)
            crop = back.crop((paste_px[0], paste_px[1], paste_px[0] + w, paste_px[1] + h))
            through = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            through.paste(crop, (0, 0), mask)
            layer.paste(through, (0, 0), mask)
        return layer

    bold = ImageFont.truetype('/mnt/c/Windows/Fonts/malgunbd.ttf', int(4.6 * pxmm))
    reg = ImageFont.truetype('/mnt/c/Windows/Fonts/malgun.ttf', int(2.9 * pxmm))
    small = ImageFont.truetype('/mnt/c/Windows/Fonts/malgun.ttf', int(2.4 * pxmm))
    dr.text((10 * pxmm, 8 * pxmm), '양검(yanggum) 최종 미리보기 · 인쇄 데이터 기준 실측', font=bold, fill=(40, 40, 46))
    dr.text((10 * pxmm, 16 * pxmm), '제공 원본 그림을 그대로 인쇄. 실물 재단·인쇄 전 검토용이며 실물 사진이 아닙니다.', font=small, fill=(110, 110, 118))

    ground = 112
    center_x = 58
    cb = char_poly.bounds
    shadow = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([round((center_x - 40) * pxmm), round((ground - 1) * pxmm),
                                    round((center_x + 40) * pxmm), round((ground + 5) * pxmm)], fill=(120, 122, 130, 36))
    img.paste(shadow, (0, 0), shadow)
    dr.rounded_rectangle([round((center_x - 36) * pxmm), round(ground * pxmm),
                          round((center_x + 36) * pxmm), round((ground + 3.6) * pxmm)],
                         radius=int(0.8 * pxmm), fill=(232, 233, 238), outline=(198, 200, 206), width=2)
    dr.rounded_rectangle([round((center_x - 9.4) * pxmm), round((ground - 0.1) * pxmm),
                          round((center_x + 9.4) * pxmm), round((ground + 1.4) * pxmm)],
                         radius=int(0.35 * pxmm), fill=(92, 94, 100))
    char_layer = layer_for(char_poly, (10, 10, 10 + art.width * 60 / art.height, 70), None)
    img.paste(char_layer, (int(round((center_x - (cb[2] - cb[0]) / 2) * pxmm)) - 2,
                           int(round((ground + 2.6 - (cb[3] - cb[1])) * pxmm)) - 2), char_layer)
    dr.text((20 * pxmm, (ground + 9) * pxmm), '미니 스탠드 · 그림 높이 60mm · 컷 62.2×67.5 · 탭 18×2.6 → 받침 홈 18.8×3.0', font=reg, fill=(60, 60, 68))

    kx, ky = 162, 56
    kb = key_solid.bounds
    hb = key_hole.bounds
    hole_cx, hole_cy = (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2
    kc_x, kc_top = (kb[0] + kb[2]) / 2, kb[1]
    paste_px = (int(round((kx - (kb[2] - kb[0]) / 2) * pxmm)) - 2, int(round((ky - kc_top) * pxmm)) - 2)
    ring = Image.new('RGBA', img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rcx = kx + (hole_cx - kc_x)
    rcy = ky + (hole_cy - kc_top) - 9.0
    rr, rt = 9.0, 1.6
    rd.ellipse([round((rcx - rr) * pxmm), round((rcy - rr) * pxmm), round((rcx + rr) * pxmm), round((rcy + rr) * pxmm)],
               outline=(150, 152, 158, 255), width=int(rt * pxmm))
    rd.ellipse([round((rcx - rr - 0.5) * pxmm), round((rcy - rr - 0.5) * pxmm),
                round((rcx + rr + 0.5) * pxmm), round((rcy + rr + 0.5) * pxmm)], outline=(96, 98, 104, 255), width=2)
    img.paste(ring, (0, 0), ring)
    key_layer = layer_for(key_solid, (10, 25, 10 + art.width * 40 / art.height, 65), paste_px, punch=[key_hole], back=ring)
    img.paste(key_layer, paste_px, key_layer)
    dr.text((124 * pxmm, (ky + 62) * pxmm), '키링 · 그림 높이 40mm · 컷 43.1×58.0 · 구멍 ⌀4 (링 별매)', font=reg, fill=(60, 60, 68))
    dr.text((10 * pxmm, (H - 8) * pxmm), '링 그림은 위치 참고용입니다. 아크릴 3T, 받침은 투명 무인쇄.', font=small, fill=(110, 110, 118))
    img.save(out)


def plan_placements():
    """Record reviewed rigid placements for the two yanggum groups."""
    from build_a3_release import MARGIN, SIZE, GAP, shifted_poly
    from nest_contours import rotated
    from shapely import box as sbox
    chosen = {'yanggum_stand_01': (110, 100), 'yanggum_stand_02': (270, 140), 'yanggum_keyring_01': (180, 110)}
    groups = yanggum_pieces()
    rows = {}
    for name, pieces in groups.items():
        entries = []
        shapes = []
        for p in pieces:
            x, y = chosen[p['id']]
            poly, origin = rotated(p, 0)
            placement = dict(piece=p, x=x, y=y, rotation=0, rotated_origin=origin,
                             w=poly.bounds[2], h=poly.bounds[3])
            shape = shifted_poly(p['poly'], placement)
            assert sbox(MARGIN - .002, MARGIN - .002, SIZE[0] - MARGIN + .002, SIZE[1] - MARGIN + .002).contains(shape)
            for q in shapes:
                assert shape.distance(q) >= GAP - .002
            shapes.append(shape)
            entries.append({'id': p['id'], 'x': x, 'y': y, 'rotation_degrees': 0,
                           'source_bounds_mm': [round(v, 6) for v in p['bounds']]})
            print(p['id'], 'bounds', [round(v, 3) for v in p['bounds']], '-> sheet', x, y,
                  'size', round(placement['w'], 2), round(placement['h'], 2))
        rows[name] = entries
    path = ROOT / 'configs/a3_placements.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['groups'].update(rows)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('placement rows written:', list(rows))


if __name__ == '__main__':
    plan_placements()
