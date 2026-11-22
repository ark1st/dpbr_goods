"""Survey applicants' chain keyrings and stand keyrings as A3 source documents.

Every applicant's set is cut from their own A3 group; two combined groups
gather every applicant's pieces for a single-run cut. Source art is the
prepared 300-ppi sprite from prepare_chain_keyring_characters.py (the OpenAPI
look render) printed as-is with no redraw. Every contour goes through
laser_paths.cut_path. Mechanical interfaces reuse the calibrated yanggum
values: 18 mm tab, 18.8 x 3.0 mm slot, 0.4 mm bottom clearance, 2.5 mm clear
border and a 4 mm hole on a 13 mm carrier.
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
ASSETS = ROOT / 'assets/chain_keyring'
MM = 72 / 25.4
APPLICANTS = json.loads((ASSETS / 'applicants.json').read_text(encoding='utf-8'))['applicants']
CHAIN_COMBINED = '17_줄줄이_결합판/3T'
STAND_COMBINED = '18_스탠드_결합판/3T'


def kind_of(app):
    return '줄줄이' if '줄줄이' in app['product'] else '스탠드'


def group_of(applicant):
    for i, app in enumerate(APPLICANTS, start=10):
        if app['applicant'] == applicant:
            return f'{i}_{applicant}_{kind_of(app)}/3T'
    raise KeyError(applicant)


def mode_label(nickname, name):
    if name.endswith('_render300_alpha.png'):
        return '알파 (공식 과거 이미지)'
    if name.endswith('_render300_beta.png'):
        return '베타 (공식 이미지)'
    if nickname in ZERO_SUFFIXLESS_MODE:
        return ZERO_SUFFIXLESS_MODE[nickname]
    return '현재 모드'


ZERO_SUFFIXLESS_MODE = {
    '마가다락방': '알파 (랭킹 스냅샷 · 현재 활성 모드는 베타)',
    '청민예': '알파 (현재 활성 모드)',
    '뿟쥐': '베타 (현재 활성 모드)',
}


def world_display(world):
    return world.replace('(icon_3)', '')


def sprite_entries(app, tag):
    """One entry per printed sprite: current mode first, then _alpha/_beta."""
    prep = json.loads((ASSETS / app['applicant'] / 'prepared' / 'provenance.json').read_text(encoding='utf-8'))
    by_source = {s['source']: s for s in prep['sprites']}
    entries = []
    for ch in app['characters']:
        files = sorted((f for f in ch['files'] if '_render300' in f),
                       key=lambda f: (f.count('_render300_'), f))
        for f in files:
            stem = f[:-4]
            prepared = ASSETS / app['applicant'] / 'prepared' / f'{stem}_{tag}.png'
            prep_record = by_source[f]
            entries.append({
                'nickname': ch['nickname'], 'world': world_display(ch['world']), 'level': ch.get('level'),
                'mode': mode_label(ch['nickname'], f), 'source': f,
                'prepared': prepared,
                'prepared_rel': prepared.relative_to(ROOT).as_posix(),
                'source_ink_px': prep_record['crop_px'],
                'dropped_components': len(prep_record['dropped']),
                'changed_px': prep_record['changed_px'],
            })
    return entries


def character_documents(im, height_mm, clear_border, origin_mm):
    """Scaled ink polygon and buffered cutter body for one product size."""
    alpha = np.asarray(im)[:, :, 3]
    contours, _ = cv2.findContours((alpha > 8).astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    shapes = [Polygon(c[:, 0, :]).buffer(0) for c in contours if len(c) >= 3]
    assert shapes, 'empty sprite'
    ink = unary_union(shapes)
    scale = height_mm / im.height
    art = affinity.scale(ink, xfact=scale, yfact=scale, origin=(0, 0))
    body = art.buffer(clear_border + .35, quad_segs=32).buffer(-.35, quad_segs=32)
    assert body.geom_type == 'Polygon' and body.is_valid, 'detached detail beyond the clear border'
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


def chain_documents(entries, settings, draw_path):
    """One cut doc + one art doc holding every keyring piece of one applicant."""
    n = len(entries)
    ims = [Image.open(e['prepared']).convert('RGBA') for e in entries]
    widths = [im.width * (settings['art_height_mm'] / im.height) for im in ims]
    xs = []
    x = 10.0
    for w in widths:
        xs.append(round(x, 4))
        x += w + 2 * settings['clear_border_mm'] + 10
    page_w, page_h = round(x + 5), 80
    cut = fitz.open()
    cpage = cut.new_page(width=page_w * MM, height=page_h * MM)
    art = fitz.open()
    apage = art.new_page(width=page_w * MM, height=page_h * MM)
    solids = []
    for i, e in enumerate(entries):
        im = ims[i]
        x = xs[i]
        art_top = settings['art_top_mm']
        ink, body, scale = character_documents(im, settings['art_height_mm'], settings['clear_border_mm'], (x, art_top))
        height = settings['art_height_mm']
        width = widths[i]
        cx = x + width / 2
        carrier = LineString([(cx, art_top + 3), (cx, art_top - 9)]).buffer(settings['carrier_width_mm'] / 2, quad_segs=32)
        solid = unary_union([body, carrier])
        assert solid.geom_type == 'Polygon' and solid.is_valid and not solid.interiors, e['nickname']
        solid = Polygon(solid.exterior)
        hole = Point(cx, art_top - 8).buffer(settings['hole_diameter_mm'] / 2, quad_segs=64)
        hole_art = hole.distance(ink)
        hole_edge = solid.boundary.distance(hole)
        assert hole.within(solid) and hole_art >= settings['hole_to_art_min_mm'] and hole_edge >= settings['hole_to_edge_min_mm'], (e['nickname'], hole_art, hole_edge)
        draw_path(cpage, cut_path(solid))
        draw_path(cpage, cut_path(hole))
        buffer = io.BytesIO()
        im.save(buffer, format='PNG')
        apage.insert_image(fitz.Rect(x * MM, art_top * MM, (x + width) * MM, (art_top + height) * MM), stream=buffer.getvalue())
        solids.append(solid)
        e['meta'] = {
            'part': 'keyring', 'nickname': e['nickname'], 'world': e['world'], 'mode': e['mode'],
            'art_height_mm': height, 'art_width_mm': width,
            'source_ink_px': e['source_ink_px'], 'print_px': [im.width, im.height],
            'effective_source_ppi': round(e['source_ink_px'][1] / height * 25.4, 1),
            'clear_border_mm': settings['clear_border_mm'],
            'hole_diameter_mm': settings['hole_diameter_mm'],
            'hole_to_art_mm': round(hole_art, 2), 'hole_to_edge_mm': round(hole_edge, 2),
            'carrier_width_mm': settings['carrier_width_mm'],
            'art_rect_mm': [round(x, 4), art_top, round(x + width, 4), round(art_top + height, 4)],
            'hole_center_mm': [round(cx, 4), art_top - 8],
            'prepared_source': e['source'], 'prepared_path': e['prepared_rel'],
            'dropped_components': e['dropped_components'], 'changed_px': e['changed_px'],
            'physical_fit_test': False,
        }
    for i in range(n):
        for j in range(i + 1, n):
            assert solids[i].distance(solids[j]) >= 5, ('chain document overlap', i, j)
    return cut, art, entries


def stand_documents(entries, settings, draw_path, thickness='3T'):
    """One cut doc + one art doc holding char+base pairs of one applicant."""
    n = len(entries)
    ims = [Image.open(e['prepared']).convert('RGBA') for e in entries]
    widths = [im.width * (settings['art_height_mm'] / im.height) for im in ims]
    xs = []
    x = 10.0
    for w in widths:
        xs.append(round(x, 4))
        x += max(w + 2 * settings['clear_border_mm'], settings['base_size_mm'][0]) + 10
    page_w, page_h = round(x + 5), 130
    cut = fitz.open()
    cpage = cut.new_page(width=page_w * MM, height=page_h * MM)
    art = fitz.open()
    apage = art.new_page(width=page_w * MM, height=page_h * MM)
    chars = []
    depth = float(thickness.removesuffix('T')) - settings['tab_bottom_clearance_mm']
    half = settings['tab_width_mm'] / 2
    for i, e in enumerate(entries):
        im = ims[i]
        x = xs[i]
        ink, body, scale = character_documents(im, settings['art_height_mm'], settings['clear_border_mm'], (x, 10))
        height = settings['art_height_mm']
        width = widths[i]
        cx = x + width / 2
        shoulder = body.bounds[3]
        rise = settings['bridge_rise_mm']
        bridge = box(cx - half - 1, shoulder - rise, cx + half + 1, shoulder)
        tip = .5
        tab = Polygon([(cx - half, shoulder - .1), (cx + half, shoulder - .1),
                       (cx + half, shoulder + depth - tip), (cx + half - tip, shoulder + depth),
                       (cx - half + tip, shoulder + depth), (cx - half, shoulder + depth - tip)])
        solid = unary_union([body, bridge, tab])
        assert solid.geom_type == 'Polygon' and solid.is_valid and not solid.interiors, e['nickname']
        solid = Polygon(solid.exterior)
        for y in [shoulder + .2, shoulder + depth - .6]:
            section = solid.intersection(LineString([(0, y), (page_w + 10, y)]))
            assert abs(section.length - settings['tab_width_mm']) < .002, (e['nickname'], y, section.length)

        bw, bh = settings['base_size_mm']
        bx, by = x, 95
        br = settings['base_corner_radius_mm']
        base = Polygon(box(bx + br, by + br, bx + bw - br, by + bh - br).buffer(br, quad_segs=32).exterior)
        scx, scy = bx + bw / 2, by + bh / 2
        sl = settings['slot_length_mm']
        sw = float(thickness.removesuffix('T'))
        sr = settings['slot_corner_radius_mm']
        slot = box(scx - (sl - 2 * sr) / 2, scy - (sw - 2 * sr) / 2,
                   scx + (sl - 2 * sr) / 2, scy + (sw - 2 * sr) / 2).buffer(sr, quad_segs=16)
        assert slot.within(base) and base.boundary.distance(slot) > 8, (e['nickname'], base.boundary.distance(slot))

        draw_path(cpage, cut_path(solid))
        draw_path(cpage, cut_path(base))
        draw_path(cpage, cut_path(slot))
        buffer = io.BytesIO()
        im.save(buffer, format='PNG')
        apage.insert_image(fitz.Rect(x * MM, 10 * MM, (x + width) * MM, (10 + height) * MM), stream=buffer.getvalue())
        chars.append(solid)

        above = section_report(solid, shoulder - rise, shoulder + 25)
        weakest = min(above, key=lambda r: r[2])
        e['char_meta'] = {
            'part': 'character', 'nickname': e['nickname'], 'world': e['world'], 'mode': e['mode'],
            'art_height_mm': height, 'art_width_mm': width,
            'source_ink_px': e['source_ink_px'], 'print_px': [im.width, im.height],
            'effective_source_ppi': round(e['source_ink_px'][1] / height * 25.4, 1),
            'clear_border_mm': settings['clear_border_mm'], 'tab_width_mm': settings['tab_width_mm'],
            'tab_depth_mm': depth, 'slot_target_mm': [sl, sw], 'bridge_rise_mm': rise,
            'weakest_section_mm': {'y_mm': round(weakest[0], 2),
                                   'ligament_widths_mm': [round(w, 2) for w in weakest[1]],
                                   'total_mm': round(weakest[2], 2)},
            'art_rect_mm': [round(x, 4), 10, round(x + width, 4), round(10 + height, 4)],
            'prepared_source': e['source'], 'prepared_path': e['prepared_rel'],
            'dropped_components': e['dropped_components'], 'changed_px': e['changed_px'],
            'physical_fit_test': False,
        }
        e['base_meta'] = {
            'part': 'base', 'nickname': e['nickname'], 'mode': e['mode'],
            'size_mm': [bw, bh], 'corner_radius_mm': br,
            'slot_mm': [sl, sw], 'slot_corner_radius_mm': sr,
            'slot_center_mm': [round(scx, 4), round(scy, 4)],
            'slot_to_edge_mm': round(base.boundary.distance(slot), 2),
            'material_thickness_mm': sw, 'physical_fit_test': False,
        }
    for i in range(n):
        for j in range(i + 1, n):
            assert chars[i].distance(chars[j]) >= 5, ('stand document overlap', i, j)
    return cut, art, entries


def build_all(only=None):
    """Source documents for every applicant group plus the two combined groups."""
    from build_a3_release import pieces_from, draw_path, CONFIG
    spec = CONFIG['chain_keyring_products']
    records = []
    per_app = {}
    for app in APPLICANTS:
        kind = kind_of(app)
        group = group_of(app['applicant'])
        if kind == '줄줄이':
            entries = sprite_entries(app, 'chain40')
            cut, art, entries = chain_documents(entries, spec['keyring'], draw_path)
            pieces = pieces_from(cut, art, None, f"{app['applicant']}_keyring", smooth=True)
            assert len(pieces) == len(entries), (group, len(pieces))
            for p, e in zip(pieces, entries):
                p['design_metadata'] = e['meta']
        else:
            entries = sprite_entries(app, 'stand60')
            cut, art, entries = stand_documents(entries, spec['stand'], draw_path)
            pieces = pieces_from(cut, art, None, f"{app['applicant']}_stand", smooth=True)
            assert len(pieces) == 2 * len(entries), (group, len(pieces))
            for k, e in enumerate(entries):
                pieces[2 * k]['design_metadata'] = e['char_meta']
                pieces[2 * k + 1]['design_metadata'] = e['base_meta']
        per_app[app['applicant']] = (kind, pieces)
        if not only or only in group:
            records.append({'group': group, 'kind': kind, 'applicant': app['applicant'], 'pieces': pieces})
    chain_apps = [a for a, (k, _) in per_app.items() if k == '줄줄이']
    stand_apps = [a for a, (k, _) in per_app.items() if k == '스탠드']
    for group, names, kind in [(CHAIN_COMBINED, chain_apps, '줄줄이'), (STAND_COMBINED, stand_apps, '스탠드')]:
        if only and only not in group:
            continue
        pieces = [p for a in names for p in per_app[a][1]]
        records.append({'group': group, 'kind': kind, 'applicant': None, 'pieces': pieces})
    return records


def applicant_batches(only=None):
    return [(r['group'], r['pieces']) for r in build_all(only)]


def _wrap(items, max_w, gap):
    rows, cur, x = [], [], 0.0
    for item in items:
        if cur and x + item[1] > max_w + 1e-6:
            rows.append(cur)
            cur, x = [], 0.0
        cur.append(item)
        x += item[1] + gap
    if cur:
        rows.append(cur)
    return rows


def grid_placements(record):
    """Reviewed rigid placements, zero rotation, centered rows."""
    from build_a3_release import MARGIN, SIZE, GAP
    from nest_contours import rotated
    gap = GAP
    max_w = SIZE[0] - 2 * MARGIN
    placements = []
    if record['kind'] == '줄줄이':
        items = [(p, p['bounds'][2] - p['bounds'][0], p['bounds'][3] - p['bounds'][1]) for p in record['pieces']]
        y = MARGIN
        for row in _wrap(items, max_w, gap):
            row_w = sum(w for _, w, _ in row) + gap * (len(row) - 1)
            row_h = max(h for _, _, h in row)
            x = MARGIN + (max_w - row_w) / 2
            for p, w, h in row:
                _, origin = rotated(p, 0)
                placements.append(dict(piece=p, x=round(x, 4), y=round(y, 4), rotation=0, rotated_origin=origin, w=w, h=h))
                x += w + gap
            y += row_h + gap
    else:
        items = []
        it = iter(record['pieces'])
        for char, base in zip(it, it):
            cb, bb = char['bounds'], base['bounds']
            cw = max(cb[2] - cb[0], bb[2] - bb[0])
            items.append(((char, base), cw, (cb[3] - cb[1]) + gap + (bb[3] - bb[1])))
        y = MARGIN
        for row in _wrap(items, max_w, gap):
            row_w = sum(w for _, w, _ in row) + gap * (len(row) - 1)
            row_h = max(h for _, _, h in row)
            x = MARGIN + (max_w - row_w) / 2
            for (char, base), cw, _ in row:
                cb, bb = char['bounds'], base['bounds']
                for p, w, dy in [(char, cb[2] - cb[0], 0), (base, bb[2] - bb[0], (cb[3] - cb[1]) + gap)]:
                    poly, origin = rotated(p, 0)
                    placements.append(dict(piece=p, x=round(x + (cw - w) / 2, 4), y=round(y + dy, 4), rotation=0, rotated_origin=origin, w=w, h=poly.bounds[3]))
                x += cw + gap
            y += row_h + gap
    return placements


def plan_placements(only=None):
    """Compute and record reviewed placement rows for every group."""
    from build_a3_release import MARGIN, SIZE, GAP, shifted_poly
    from shapely import box as sbox
    rows_all = {}
    for record in build_all(only):
        placements = grid_placements(record)
        shapes = []
        entries = []
        for place in placements:
            shape = shifted_poly(place['piece']['poly'], place)
            assert sbox(MARGIN - .002, MARGIN - .002, SIZE[0] - MARGIN + .002, SIZE[1] - MARGIN + .002).contains(shape), record['group']
            for q in shapes:
                assert shape.distance(q) >= GAP - .002, (record['group'], place['piece']['id'])
            shapes.append(shape)
            entries.append({'id': place['piece']['id'], 'x': place['x'], 'y': place['y'],
                            'rotation_degrees': 0,
                            'source_bounds_mm': [round(v, 6) for v in place['piece']['bounds']]})
        rows_all[record['group']] = entries
        first, last = entries[0], entries[-1]
        print(record['group'], len(entries), 'pieces', first['x'], first['y'], '->', last['x'], last['y'], flush=True)
    path = ROOT / 'configs/a3_placements.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['groups'].update(rows_all)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('placement rows written:', list(rows_all))


def group_title(record):
    kind = record['kind']
    n = len(record['pieces'])
    if record['applicant'] is None:
        return ('줄줄이 키링 전원 결합판' if kind == '줄줄이' else '스탠드 키링 전원 결합판') + f' · {n}조각'
    return (f"{record['applicant']} · 줄줄이 키링" if kind == '줄줄이' else f"{record['applicant']} · 스탠드 키링") + f' · {n}조각'


def _mode_short(mode):
    if mode.startswith('알파'):
        return '알파'
    if mode.startswith('베타'):
        return '베타'
    return '현재'


def _preview_label(meta):
    label = f"{meta['nickname']} · {_mode_short(meta['mode'])}"
    if meta.get('part') in ('keyring', 'character'):
        label += f" · {meta['world']}"
    return label


def render_group_preview(record, out):
    """Final-look mockup from the prepared rasters and the real cut polygons."""
    from PIL import ImageDraw, ImageFont
    pxmm = 8
    gap = 10.0
    label_h = 9.0
    header_h, footer_h = 24.0, 12.0
    if record['kind'] == '줄줄이':
        cells = [{'items': [(p, p['bounds'])], 'w': p['bounds'][2] - p['bounds'][0],
                  'h': p['bounds'][3] - p['bounds'][1], 'label': _preview_label(p['design_metadata'])}
                 for p in record['pieces']]
    else:
        cells = []
        it = iter(record['pieces'])
        for char, base in zip(it, it):
            cb, bb = char['bounds'], base['bounds']
            cw = max(cb[2] - cb[0], bb[2] - bb[0])
            cells.append({'items': [(char, cb), (base, bb)], 'w': cw,
                          'h': (cb[3] - cb[1]) + gap + (bb[3] - bb[1]),
                          'label': _preview_label(char['design_metadata'])})
    rows = _wrap([(c, c['w'], c['h']) for c in cells], 410.0, gap)
    content_h = header_h
    row_specs = []
    for row in rows:
        row_w = sum(w for _, w, _ in row) + gap * (len(row) - 1)
        row_h = max(h for _, _, h in row)
        row_specs.append((row, 15 + (410 - row_w) / 2, content_h, row_h))
        content_h += row_h + label_h + gap
    W, H = 440.0, content_h + footer_h
    img = Image.new('RGB', (round(W * pxmm), round(H * pxmm)), (247, 247, 250))
    dr = ImageDraw.Draw(img, 'RGBA')
    bold = ImageFont.truetype('/mnt/c/Windows/Fonts/malgunbd.ttf', int(4.4 * pxmm))
    reg = ImageFont.truetype('/mnt/c/Windows/Fonts/malgun.ttf', int(2.7 * pxmm))
    small = ImageFont.truetype('/mnt/c/Windows/Fonts/malgun.ttf', int(2.3 * pxmm))
    dr.text((10 * pxmm, 7 * pxmm), group_title(record) + ' · 인쇄 데이터 기준 실측', font=bold, fill=(40, 40, 46))
    dr.text((10 * pxmm, 15 * pxmm), '제공 렌더를 그대로 인쇄(재작성 없음). 실물 사진이 아니며 실물 끼움·절단은 미검증입니다.', font=small, fill=(110, 110, 118))

    def piece_at(p, b, px, py):
        meta = p['design_metadata']
        pts = [((x - b[0] + px) * pxmm, (y - b[1] + py) * pxmm) for x, y in p['poly'].exterior.coords]
        dr.polygon(pts, fill=(255, 255, 255, 46))
        if meta['part'] != 'base':
            ax, ay, _, _ = meta['art_rect_mm']
            sprite = Image.open(ROOT / meta['prepared_path']).convert('RGBA')
            tw = max(1, round(meta['art_width_mm'] * pxmm))
            th = max(1, round(meta['art_height_mm'] * pxmm))
            sprite = sprite.resize((tw, th), Image.NEAREST)
            img.paste(sprite, (round((ax - b[0] + px) * pxmm), round((ay - b[1] + py) * pxmm)), sprite)
        dr.polygon(pts, outline=(206, 208, 214, 255), width=2)
        if meta['part'] == 'keyring':
            hx, hy = meta['hole_center_mm']
            cxp, cyp = (hx - b[0] + px) * pxmm, (hy - b[1] + py) * pxmm
            r = 2 * pxmm
            dr.ellipse([cxp - r, cyp - r, cxp + r, cyp + r], outline=(150, 152, 158, 255), width=2)
            R = 4 * pxmm
            dr.ellipse([cxp - R, cyp - R, cxp + R, cyp + R], outline=(172, 174, 180, 255), width=3)
        elif meta['part'] == 'base':
            scx, scy = meta['slot_center_mm']
            sl, sw = meta['slot_mm']
            lx = (scx - sl / 2 - b[0] + px) * pxmm
            ly = (scy - sw / 2 - b[1] + py) * pxmm
            dr.rounded_rectangle([lx, ly, lx + sl * pxmm, ly + sw * pxmm], radius=int(.35 * pxmm),
                                 outline=(92, 94, 100, 255), width=2)

    for row, x0, y0, row_h in row_specs:
        x = x0
        for cell, cw, _ in row:
            if record['kind'] == '줄줄이':
                p, b = cell['items'][0]
                piece_at(p, b, x, y0)
            else:
                (char, cb), (base, bb) = cell['items']
                piece_at(char, cb, x + (cw - (cb[2] - cb[0])) / 2, y0)
                piece_at(base, bb, x + (cw - (bb[2] - bb[0])) / 2, y0 + (cb[3] - cb[1]) + gap)
            dr.text((x * pxmm, (y0 + row_h + 2) * pxmm), cell['label'], font=reg, fill=(60, 60, 68))
            x += cw + gap

    footer = ('캐리어 폭 13mm · 구멍 ⌀4mm (링·체인 별매)' if record['kind'] == '줄줄이'
              else '탭 18×2.6mm → 받침 홈 18.8×3.0mm · 받침 72×28mm 무인쇄 투명')
    dr.text((10 * pxmm, (H - 8) * pxmm), footer + ' · 아크릴 3T · 실물 사진 아님', font=small, fill=(110, 110, 118))
    img.save(out)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--group')
    parser.add_argument('--previews', action='store_true')
    args = parser.parse_args()
    if args.previews:
        base = ROOT / 'output/a3_release'
        for record in build_all(args.group):
            out = base / record['group'].split('/')[0] / 'final_preview.png'
            out.parent.mkdir(parents=True, exist_ok=True)
            render_group_preview(record, out)
            print('preview', out.relative_to(ROOT), flush=True)
    else:
        plan_placements(args.group)


if __name__ == '__main__':
    main()
