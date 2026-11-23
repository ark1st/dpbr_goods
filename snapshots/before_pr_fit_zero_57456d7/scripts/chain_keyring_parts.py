"""Survey applicants' chain keyrings and stand keyrings as A3 source documents.

Every applicant's set is cut from their own A3 group; two combined groups
gather every applicant's pieces for a single-run cut. Source art is the
prepared 300-ppi sprite from prepare_chain_keyring_characters.py (the OpenAPI
look render) printed as-is with no redraw. Every contour goes through
laser_paths.cut_path. Mechanical interfaces reuse the calibrated yanggum
values: 18 mm tab, 18.8 x 3.0 mm slot, 0.4 mm bottom clearance, 2.5 mm clear
border and two 4 mm connection holes on 13 mm carriers.
"""
from pathlib import Path
import io, json, sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon, box, LineString, Point
from shapely.ops import linemerge, unary_union
from shapely import affinity
from laser_paths import cut_path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/chain_keyring'
MM = 72 / 25.4
APPLICANTS = json.loads((ASSETS / 'applicants.json').read_text(encoding='utf-8'))['applicants']
CHAIN_COMBINED = '17_줄줄이_결합판/3T'
STAND_COMBINED = '18_스탠드_결합판/3T'
COMBINED_ZERO_STANDS = frozenset({'마가다락방', '청민예'})


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


def chain_documents(entries, settings, draw_path):
    """One cut doc + one art doc holding every keyring piece of one applicant."""
    height = settings['art_height_mm']
    art_top = settings['art_top_mm']
    art_bottom = art_top + height
    carrier_radius = settings['carrier_width_mm'] / 2
    hole_radius = settings['hole_diameter_mm'] / 2
    ims = [Image.open(e['prepared']).convert('RGBA') for e in entries]
    widths = [im.width * (height / im.height) for im in ims]
    xs = []
    x = 10.0
    for w in widths:
        xs.append(round(x, 4))
        x += w + 2 * settings['clear_border_mm'] + 10
    page_w, page_h = round(x + 5), max(80, art_bottom + 9 + carrier_radius + 5)
    cut = fitz.open()
    cpage = cut.new_page(width=page_w * MM, height=page_h * MM)
    art = fitz.open()
    apage = art.new_page(width=page_w * MM, height=page_h * MM)
    solids = []
    for i, e in enumerate(entries):
        im = ims[i]
        x = xs[i]
        ink, body, _ = character_documents(im, height, settings['clear_border_mm'], (x, art_top))
        width = widths[i]
        cx = x + width / 2
        top_carrier = LineString([(cx, art_top + 3), (cx, art_top - 9)]).buffer(carrier_radius, quad_segs=32)
        # The bottom of the silhouette's centerline can sit above its lowest
        # pixel (for example, when a weapon or garment extends below it).
        centerline = body.intersection(LineString([(cx, body.bounds[1] - 1), (cx, body.bounds[3] + 1)]))
        assert not centerline.is_empty, (e['nickname'], 'no lower carrier attachment')
        anchor_y = min(art_bottom - 3, centerline.bounds[3] - 3)
        bottom_carrier = LineString([(cx, anchor_y), (cx, art_bottom + 9)]).buffer(carrier_radius, quad_segs=32)
        assert bottom_carrier.intersection(body).area > 0, (e['nickname'], 'detached lower carrier')
        solid = unary_union([body, top_carrier, bottom_carrier])
        assert solid.geom_type == 'Polygon' and solid.is_valid and not solid.interiors, e['nickname']
        solid = Polygon(solid.exterior)
        centers = {'top': (cx, art_top - 8), 'bottom': (cx, art_bottom + 8)}
        clearances = {}
        for end, center in centers.items():
            hole = Point(center).buffer(hole_radius, quad_segs=64)
            hole_art = hole.distance(ink)
            hole_edge = solid.boundary.distance(hole)
            assert (hole.within(solid)
                    and hole_art >= settings['hole_to_art_min_mm']
                    and hole_edge >= settings['hole_to_edge_min_mm']), (e['nickname'], end, hole_art, hole_edge)
            clearances[end] = {'to_art': round(hole_art, 2), 'to_edge': round(hole_edge, 2)}
            draw_path(cpage, cut_path(hole))
        draw_path(cpage, cut_path(solid))
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
            'hole_to_art_mm': clearances['top']['to_art'], 'hole_to_edge_mm': clearances['top']['to_edge'],
            'hole_clearances_mm': clearances,
            'carrier_width_mm': settings['carrier_width_mm'],
            'art_rect_mm': [round(x, 4), art_top, round(x + width, 4), round(art_top + height, 4)],
            'hole_center_mm': [round(cx, 4), centers['top'][1]],
            'hole_centers_mm': [[round(hx, 4), hy] for hx, hy in centers.values()],
            'prepared_source': e['source'], 'prepared_path': e['prepared_rel'],
            'dropped_components': e['dropped_components'], 'changed_px': e['changed_px'],
            'physical_fit_test': False,
        }
    for i, solid in enumerate(solids):
        for j, other in enumerate(solids[:i]):
            assert solid.distance(other) >= 5, ('chain document overlap', i, j)
    return cut, art, entries


def stand_sprite_sets(entries, combine_zero_modes):
    """Combine the two requested Alpha/Beta stands only, preserving roster order."""
    groups = {}
    for i, entry in enumerate(entries):
        nickname = entry['nickname']
        key = nickname if combine_zero_modes and nickname in COMBINED_ZERO_STANDS else i
        groups.setdefault(key, []).append(entry)
    for key, group in groups.items():
        if isinstance(key, str):
            group.sort(key=lambda e: _mode_short(e['mode']) == '베타')
            assert [_mode_short(e['mode']) for e in group] == ['알파', '베타'], key
    return list(groups.values())


def stand_body_axis(im):
    """Center of the thick core in the head/torso band, in source pixels."""
    alpha = np.asarray(im)[:, :, 3]
    mask = (alpha >= 128).astype('uint8')
    if not mask.any():
        mask = (alpha > 8).astype('uint8')
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    assert count > 1, 'empty stand sprite'
    primary = (labels == 1 + stats[1:, cv2.CC_STAT_AREA].argmax()).astype('uint8')
    # Thin weapons and glow are low-weight even when connected to the torso.
    thickness = cv2.distanceTransform(np.pad(primary, 1), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
    band = thickness[round(im.height * .22):round(im.height * .62)]
    if not band.any():
        band = thickness
    columns = np.square(band).sum(axis=0).cumsum()
    return float(np.searchsorted(columns, columns[-1] / 2)) + .5


def stand_web(axes, anchor, shoulder, width, taper, radius, tab_width, depth):
    """Round the crown and join the sides to the tab with a tangent cubic."""
    center = (axes[0] + axes[-1]) / 2
    left, right = axes[0] - width / 2, axes[-1] + width / 2
    tab_left, tab_right = center - tab_width / 2, center + tab_width / 2
    flare = shoulder - taper
    assert width > tab_width and 0 < radius < min(width / 2, flare - anchor)
    top = []
    for cx, start in [(left + radius, np.pi), (right - radius, 1.5 * np.pi)]:
        top.extend((cx + radius * np.cos(angle), anchor + radius + radius * np.sin(angle))
                   for angle in np.linspace(start, start + np.pi / 2, 25))

    def side(outer, tab):
        control = np.array([(outer, flare), (outer, shoulder - taper * .2),
                            (tab, shoulder - .035), (tab, shoulder)])
        t = np.linspace(0, 1, 49)[:, None]
        return ((1 - t)**3 * control[0] + 3 * (1 - t)**2 * t * control[1]
                + 3 * (1 - t) * t**2 * control[2] + t**3 * control[3]).tolist()

    tip = .5
    bottom = [(tab_right, shoulder + depth - tip), (tab_right - tip, shoulder + depth),
              (tab_left + tip, shoulder + depth), (tab_left, shoulder + depth - tip)]
    return Polygon(top + side(right, tab_right) + bottom + side(left, tab_left)[::-1])


def stand_axis_width(poly, axis, y):
    """Width of the one horizontal ligament actually carrying the tab."""
    cut = poly.intersection(LineString([(poly.bounds[0] - 1, y), (poly.bounds[2] + 1, y)]))
    segments = [line for line in getattr(cut, 'geoms', (cut,)) if line.geom_type == 'LineString']
    if len(segments) > 1:
        # GEOS splits contiguous runs at vertices along the section line.
        cut = linemerge(segments)
    return next((line.length for line in getattr(cut, 'geoms', (cut,))
                 if line.geom_type == 'LineString' and not line.is_empty
                 and line.bounds[0] <= axis <= line.bounds[2]), 0.0)


def stand_documents(entries, settings, draw_path, thickness='3T'):
    """One reinforced character and matching base per stand set."""
    height = settings['art_height_mm']
    border = settings['clear_border_mm']
    top = 10
    sw = float(thickness.removesuffix('T'))
    depth = sw - settings['tab_bottom_clearance_mm']
    tab_width = settings['tab_width_mm']
    web_width = settings.get('support_web_width_mm', 26)
    anchor = top + height * settings.get('support_anchor_ratio', .5)
    taper = settings.get('support_taper_height_mm', 6)
    radius = settings.get('support_round_radius_mm', 3)
    art_gap = settings.get('pair_art_gap_mm', 4)
    bw, bh = settings['base_size_mm']
    br = settings['base_corner_radius_mm']
    sl = settings['slot_length_mm']
    sr = settings['slot_corner_radius_mm']
    sets = []
    column = 8.0
    for group in stand_sprite_sets(entries, settings.get('combine_zero_modes', False)):
        art_x = 0.0
        artworks, bodies, inks, axes = [], [], [], []
        for entry in group:
            with Image.open(entry['prepared']) as source:
                im = source.convert('RGBA')
            ink, body, scale = character_documents(im, height, border, (art_x, top))
            width = im.width * scale
            axes.append(art_x + stand_body_axis(im) * scale)
            bodies.append(body)
            inks.append(ink)
            artwork = {
                'nickname': entry['nickname'], 'world': entry['world'], 'mode': entry['mode'],
                'art_height_mm': height, 'art_width_mm': width,
                'source_ink_px': entry['source_ink_px'], 'print_px': [im.width, im.height],
                'effective_source_ppi': round(entry['source_ink_px'][1] / height * 25.4, 1),
                'art_rect_mm': [art_x, top, art_x + width, top + height],
                'prepared_source': entry['source'], 'prepared_path': entry['prepared_rel'],
                'dropped_components': entry['dropped_components'], 'changed_px': entry['changed_px'],
            }
            artworks.append((entry['prepared'], artwork))
            art_x += width + art_gap

        center = (axes[0] + axes[-1]) / 2
        shoulder = max(body.bounds[3] for body in bodies)
        web = stand_web(axes, anchor, shoulder, web_width, taper, radius, tab_width, depth)
        # The web contacts each printed body and fills the clear lower plate.
        contact = [web.intersection(ink).area for ink in inks]
        assert min(contact) >= web_width, (group[0]['nickname'], 'insufficient body contact', contact)
        solid = unary_union([web, *bodies])
        assert solid.geom_type == 'Polygon' and solid.is_valid, group[0]['nickname']
        solid = Polygon(solid.exterior)
        weakest_y, weakest = min(((y, stand_axis_width(solid, center, y))
                                  for y in np.linspace(anchor, shoulder, 129)), key=lambda row: row[1])
        assert weakest >= tab_width - .002, (group[0]['nickname'], 'interrupted support', weakest)
        for y in [shoulder + .2, shoulder + depth - .6]:
            section = stand_axis_width(solid, center, y)
            assert abs(section - tab_width) < .002, (group[0]['nickname'], y, section)
        seat_y = shoulder - settings['tab_bottom_clearance_mm']
        assert stand_axis_width(solid, center, seat_y) > sl, (group[0]['nickname'], 'insufficient seat width')

        by = max(95, shoulder + depth + 10)
        scy = by + bh / 2
        base = box(center - bw / 2 + br, by + br, center + bw / 2 - br, by + bh - br).buffer(br, quad_segs=32)
        slot = box(center - sl / 2 + sr, scy - sw / 2 + sr,
                   center + sl / 2 - sr, scy + sw / 2 - sr).buffer(sr, quad_segs=16)
        assert slot.within(base) and base.boundary.distance(slot) > 8, group[0]['nickname']
        shift = column - min(solid.bounds[0], base.bounds[0])
        column = max(solid.bounds[2], base.bounds[2]) + shift + 10
        for _, item in artworks:
            x0, y0, x1, y1 = item['art_rect_mm']
            item['art_rect_mm'] = [round(x0 + shift, 4), y0, round(x1 + shift, 4), y1]

        components = [item for _, item in artworks]
        first, last = components[0], components[-1]
        mode = first['mode'] if len(components) == 1 else '알파·베타'
        center_x = round(center + shift, 4)
        single_source = first if len(components) == 1 else {}
        char_meta = {
            **single_source, 'part': 'character', 'nickname': first['nickname'],
            'world': first['world'], 'mode': mode, 'components': components,
            'art_height_mm': height, 'art_width_mm': art_x - art_gap,
            'art_rect_mm': [first['art_rect_mm'][0], top, last['art_rect_mm'][2], top + height],
            'effective_source_ppi': min(item['effective_source_ppi'] for item in components),
            'clear_border_mm': border, 'tab_width_mm': tab_width, 'tab_depth_mm': depth,
            'slot_target_mm': [sl, sw], 'tab_center_mm': [center_x, round(shoulder, 4)],
            'bridge_rise_mm': round(shoulder - anchor, 4),
            'support_web': {'anchor_y_mm': anchor, 'full_width_mm': round(axes[-1] - axes[0] + web_width, 4),
                            'width_per_body_mm': web_width,
                            'body_axes_mm': [round(x + shift, 4) for x in axes],
                            'taper_height_mm': taper, 'round_radius_mm': radius,
                            'body_contact_mm2': [round(area, 2) for area in contact]},
            'weakest_section_mm': {'y_mm': round(weakest_y, 2),
                                   'ligament_widths_mm': [round(weakest, 2)], 'total_mm': round(weakest, 2)},
            'physical_fit_test': False,
        }
        base_meta = {
            'part': 'base', 'nickname': first['nickname'], 'mode': mode,
            'size_mm': [bw, bh], 'corner_radius_mm': br,
            'slot_mm': [sl, sw], 'slot_corner_radius_mm': sr,
            'slot_center_mm': [center_x, round(scy, 4)],
            'slot_to_edge_mm': round(base.boundary.distance(slot), 2),
            'material_thickness_mm': sw, 'physical_fit_test': False,
        }
        result = {**group[0], 'mode': mode, 'char_meta': char_meta, 'base_meta': base_meta}
        sets.append((affinity.translate(solid, xoff=shift), affinity.translate(base, xoff=shift),
                     affinity.translate(slot, xoff=shift), artworks, result))

    page_w = round(column + 5)
    page_h = max((base.bounds[3] + 7 for _, base, _, _, _ in sets), default=130)
    cut, art = fitz.open(), fitz.open()
    cpage = cut.new_page(width=page_w * MM, height=page_h * MM)
    apage = art.new_page(width=page_w * MM, height=page_h * MM)
    for solid, base, slot, artworks, _ in sets:
        for outline in [solid, base, slot]:
            draw_path(cpage, cut_path(outline))
        for source, item in artworks:
            rect = fitz.Rect(*(v * MM for v in item['art_rect_mm']))
            apage.insert_image(rect, filename=str(source))
    return cut, art, [result for _, _, _, _, result in sets]


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
    if mode == '알파·베타':
        return mode
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
            axis = char['design_metadata']['tab_center_mm'][0]
            slot = base['design_metadata']['slot_center_mm'][0]
            char_left, base_left = axis - cb[0], slot - bb[0]
            left = max(char_left, base_left)
            cw = left + max(cb[2] - axis, bb[2] - slot)
            cells.append({'items': [(char, cb), (base, bb)], 'w': cw,
                          'offsets': (left - char_left, left - base_left),
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
    def preview_font(size, heavy=False):
        candidates = [Path('/System/Library/Fonts/AppleSDGothicNeo.ttc'),
                      Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf'),
                      Path('C:/Windows/Fonts') / ('malgunbd.ttf' if heavy else 'malgun.ttf'),
                      Path('/mnt/c/Windows/Fonts') / ('malgunbd.ttf' if heavy else 'malgun.ttf'),
                      Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
        return ImageFont.truetype(str(next(p for p in candidates if p.exists())), int(size * pxmm))
    bold = preview_font(4.4, True)
    reg = preview_font(2.7)
    small = preview_font(2.3)
    dr.text((10 * pxmm, 7 * pxmm), group_title(record) + ' · 인쇄 데이터 기준 실측', font=bold, fill=(40, 40, 46))
    dr.text((10 * pxmm, 15 * pxmm), '제공 렌더를 그대로 인쇄(재작성 없음). 실물 사진이 아니며 실물 끼움·절단은 미검증입니다.', font=small, fill=(110, 110, 118))

    def piece_at(p, b, px, py):
        meta = p['design_metadata']
        pts = [((x - b[0] + px) * pxmm, (y - b[1] + py) * pxmm) for x, y in p['poly'].exterior.coords]
        dr.polygon(pts, fill=(255, 255, 255, 46))
        if meta['part'] != 'base':
            for component in meta.get('components', [meta]):
                ax, ay, _, _ = component['art_rect_mm']
                with Image.open(ROOT / component['prepared_path']) as source:
                    sprite = source.convert('RGBA')
                tw = max(1, round(component['art_width_mm'] * pxmm))
                th = max(1, round(component['art_height_mm'] * pxmm))
                sprite = sprite.resize((tw, th), Image.NEAREST)
                img.paste(sprite, (round((ax - b[0] + px) * pxmm), round((ay - b[1] + py) * pxmm)), sprite)
        dr.polygon(pts, outline=(206, 208, 214, 255), width=2)
        if meta['part'] == 'keyring':
            for hx, hy in meta['hole_centers_mm']:
                cxp, cyp = (hx - b[0] + px) * pxmm, (hy - b[1] + py) * pxmm
                r = meta['hole_diameter_mm'] / 2 * pxmm
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
                char_x, base_x = cell['offsets']
                piece_at(char, cb, x + char_x, y0)
                piece_at(base, bb, x + base_x, y0 + (cb[3] - cb[1]) + gap)
            dr.text((x * pxmm, (y0 + row_h + 2) * pxmm), cell['label'], font=reg, fill=(60, 60, 68))
            x += cw + gap

    footer = ('캐리어 폭 13mm · 위·아래 구멍 각 지름 4mm (링·체인 별매)' if record['kind'] == '줄줄이'
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
