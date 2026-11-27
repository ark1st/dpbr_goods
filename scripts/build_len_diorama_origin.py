"""Len ORIGIN layered slot-in acrylic diorama, V2.

Lineage: V1 (commit 2ac3ad0, scripts/build_len_diorama_origin.py) built one
base plus seven plates with a 2.5 mm clear border. The owner rejected the
assembled look ("too many borders"): the preview painted every clear plate
near-white and drew each one twice, so every element carried a thick halo
plus a second outline, and the two doors and the background added heavy
rectangular frames. V2 keeps the V1 slot-in mechanics (18 mm tabs, 18.8 mm
nominal slots, 0.4 mm bottom clearance, 12 mm load-path floor with the
automatic bud guard) and changes the piece breakdown, the rim and the preview:

* Clear border 2.5 mm -> 1.0 mm (configs/len_diorama_origin.json carries the
  rationale; the quality doc fixes no rim minimum).
* The back panel is ONE plate: the sky raster with both lattice doors butted
  against its sides and the moon/cloud layer registered over the sky. V1
  carried these as four plates (background, moon+clouds, two doors) whose
  rims produced the stacked outlines in the middle and the frames at the sides.
* Tree, serpent and character stay separate shaped plates on their own depth
  rows, so the concept's layering (sky -> tree -> serpent -> character) and
  the diorama depth are kept.
* The assembly preview renders clear acrylic see-through: no body fill and
  one thin edge stroke per plate.

Every raster is embedded as-is at its native aspect and never upscaled past
its native pixels; overlays are only positioned. No fit-test pieces: current
repo policy rejects all test pieces.

The product archive keeps exactly the files the A3 release consumes:
02_MASTER.ai, 03_CUT_ONLY.pdf, validation_report.json per thickness and
preview/assembly.png for 3T. Everything else is generated for validation,
then pruned; the A3 stage rebuilds print/cut/native files at sheet level.
"""
from pathlib import Path
import sys, json, base64, io, hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon, box, LineString
from shapely import affinity, concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from laser_paths import cut_path, audit_path
from vector_utils import runvc, svg_doc, path, poly_path, layer

OUT = ROOT/'output/len_diorama_origin_v2'
TMP = ROOT/'tmp/len_diorama_origin_v2'
CFG = json.loads((ROOT/'configs/len_diorama_origin.json').read_text(encoding='utf-8'))
BOARD = tuple(CFG['board_mm'])
PPI = 300/25.4
RED = '#ff0000'
BLUE = '#0000ff'
SRC = ROOT/'assets/len_orgin'
LOAD_PATH_FLOOR_MM = 12.0
PIECE_COUNT = 1 + len(CFG['pieces'])
SLOT_COUNT = sum(len(p['mounts_mm']) for p in CFG['pieces'])
CUT_PATH_COUNT = PIECE_COUNT + SLOT_COUNT


def write_svg(dest, w, h, content, title=''):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(svg_doc(w, h, content, title), encoding='utf-8')
    return dest


def render(svg, png, scale=2):
    pdf = TMP/(svg.stem+'-'+str(round(scale*100))+'.pdf')
    runvc(['convert', svg, pdf])
    with fitz.open(pdf) as doc:
        doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True).save(str(png))


def rounded(x, y, w, h, r):
    return box(x+r, y+r, x+w-r, y+h-r).buffer(r, quad_segs=24)


def svg_text(x, y, text, size=3.2, color='#5e5a51', anchor='start'):
    import html
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-family="Arial">{html.escape(text)}</text>')


def tab_shape(cx, shoulder, depth):
    half = CFG['tab_width_mm']/2; chamfer = .4
    return Polygon([(cx-half, shoulder-1), (cx+half, shoulder-1),
                    (cx+half, shoulder+depth-chamfer),
                    (cx+half-chamfer, shoulder+depth),
                    (cx-half+chamfer, shoulder+depth),
                    (cx-half, shoulder+depth-chamfer)])


def artwork_layer(items):
    return ''.join(f'<g id="{p["name"]}" transform="translate({p["tx"]:.6f} {p["ty"]:.6f})">{p["ink"]}</g>' for p in items)


def cut_layer(items, stroke=.001):
    # Interior slots first, closed outside profiles second.
    holes = [h for p in items for h in p['holes']]
    return ''.join(path(cut_path(p), 'none', RED, stroke) for p in holes+[p['poly'] for p in items])


def export_native(svg, folder, name='02_MASTER'):
    commands = [{'command': 'document.setUnits', 'params': {'units': 'Millimeters'}},
        {'command': 'document.save', 'params': {'path': str(folder/f'{name}.vectorcraft'), 'format': 'vectorcraft', 'compress': False}},
        {'command': 'document.export', 'params': {'path': str(folder/f'{name}.ai'), 'format': 'ai', 'createLayers': True, 'preserveEditing': True}}]
    cf = TMP/f'{folder.name}-{name}.json'
    cf.write_text(json.dumps(commands), encoding='utf-8')
    runvc(['run', '--in', svg, '--commands', cf])


def export_png(svg, dest):
    cf = TMP/f'{dest.parent.name}-{dest.stem}.json'
    cf.write_text(json.dumps([{'command': 'document.export', 'params': {'path': str(dest), 'format': 'png', 'ppi': 300, 'background': 'transparent', 'includeArtboardFill': False}}]), encoding='utf-8')
    runvc(['run', '--in', svg, '--commands', cf])


def load_raster(spec, border=None):
    """Embed one island or one whole alpha-cropped raster at exact print scale.

    `border` (standalone plates) asserts that every printed pixel lies within
    the clear rim of a kept contour, so no speck can print outside the cut.
    """
    source = SRC/spec['file']
    im = Image.open(source)
    if im.mode != 'RGBA': im = im.convert('RGBA')
    a = np.asarray(im)
    processing = None
    if spec.get('island_at_px'):
        n, labels, stats, _ = cv2.connectedComponentsWithStats((a[..., 3] > 8).astype('uint8'), 8)
        ex, ey = spec['island_at_px']
        sel = [i for i in range(1, n) if abs(int(stats[i, 0])-ex) < 40 and abs(int(stats[i, 1])-ey) < 40]
        assert sel, (spec['file'], ex, ey)
        idx = max(sel, key=lambda i: int(stats[i, 4]))
        assert int(stats[idx, 4]) > 10000, (spec['file'], ex, ey, [int(stats[i, 4]) for i in sel])
        bx, by, bw, bh = (int(v) for v in stats[idx, :4])
        crop = a[by:by+bh, bx:bx+bw].copy()
        crop[labels[by:by+bh, bx:bx+bw] != idx, 3] = 0
        im = Image.fromarray(crop, 'RGBA')
        bbox = [bx, by, bw, bh]
        processing = 'island separated from the bundled sheet by connected-component label; neighbour-bbox fragments alpha-zeroed, island pixels untouched'
    else:
        ys, xs = np.nonzero(a[..., 3] > 8)
        assert len(ys), source
        x0, y0 = int(xs.min()), int(ys.min())
        im = im.crop((x0, y0, int(xs.max())+1, int(ys.max())+1))
        bbox = [x0, y0, im.size[0], im.size[1]]
    pw, ph = im.size
    h = spec['art_height_mm']; s = h/ph; w = pw*s
    mask = (np.asarray(im)[:, :, 3] > 8).astype('uint8')
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = [Polygon(c[:, 0, :].astype(float)*[s, s]).buffer(0) for c in contours if cv2.contourArea(c) > 6]
    assert polys, source
    kept = np.zeros(mask.shape, np.uint8)
    for c in contours:
        if cv2.contourArea(c) > 6: cv2.drawContours(kept, [c], -1, 1, -1)
    far = cv2.distanceTransform(1-kept, cv2.DIST_L2, 3)*s
    reach = (border-.05) if border is not None else .5
    assert not ((far >= reach) & (mask > 0)).any(), (source.name, 'stray ink beyond', reach, 'mm of a kept contour')
    if border is not None:
        main = max(polys, key=lambda p: p.area)
        for p in polys:
            if p is not main: assert main.distance(p) < border-.1, (source.name, p.bounds)
    # Embed at the exact 300 ppi print size, but never upscale beyond the
    # native pixels: a raster below 300 ppi ships as-is.
    tw, th = max(1, min(round(w*PPI), pw)), max(1, min(round(h*PPI), ph))
    res = im.resize((tw, th), Image.LANCZOS)
    ra = np.asarray(res); solid = ra[:, :, 3] > 128
    buf = io.BytesIO(); res.save(buf, 'PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    ink = (f'<image x="0" y="0" width="{w:.6f}" height="{h:.6f}" '
           f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    return {'file': source.name,
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_px': [pw, ph], 'source_bbox_px': bbox,
        'resample_px': [tw, th],
        'w': w, 'h': h, 'ink': ink, 'art': unary_union(polys),
        'processing': processing,
        'opaque_px': int((np.asarray(res)[:, :, 3] > 8).sum()),
        'res_alpha': ra[:, :, 3].copy(), 'mean_rgb': ra[solid][:, :3].mean(0),
        'native_cap': bool(tw < pw-1 or (tw == pw and th == ph and round(w*PPI) > pw)),
        'effective_ppi': round(tw/(w/25.4))}


def overlay_offset(anchor, bw, bh, ow, oh, top_margin):
    """Overlay top-left in the base raster's image coordinates (y down)."""
    if anchor == 'left_edge_bottom': return -ow, bh-oh
    if anchor == 'right_edge_bottom': return bw, bh-oh
    if anchor == 'top_center': return (bw-ow)/2, top_margin
    raise ValueError(f'Unknown overlay anchor {anchor}')


def load_piece(spec):
    """One plate: a base raster plus overlays butted/registered onto it.

    Overlays are only positioned (no resampling beyond their own 300 ppi cap);
    their silhouettes join the plate's art union so the cut encloses them.
    """
    rasters = []
    base = load_raster(spec, border=CFG['clear_border_mm'] if not spec.get('overlays') else None)
    rasters.append(dict(base, dx=0.0, dy=0.0, anchor='base'))
    ink = base['ink']
    # A merged plate's body is the union of raster footprints: alpha
    # silhouettes sit half a pixel inside their image and never exactly meet
    # at a butt joint. Standalone plates keep the alpha silhouette so the
    # cut hugs the art.
    art = base['art'] if not spec.get('overlays') else box(0, 0, base['w'], base['h'])
    for ov in spec.get('overlays', []):
        r = load_raster(ov)
        dx, dy = overlay_offset(ov['anchor'], base['w'], base['h'], r['w'], r['h'], ov.get('top_margin_mm', 0))
        moved = box(dx, dy, dx+r['w'], dy+r['h'])
        assert art.distance(moved) < 1e-6, (spec['id'], ov['file'], 'overlay detached from the plate body')
        if ov['anchor'] == 'top_center':
            assert art.buffer(1e-6).contains(moved), (spec['id'], ov['file'], 'overlay leaves the base raster')
        ink += f'<g transform="translate({dx:.6f} {dy:.6f})">{r["ink"]}</g>'
        art = unary_union([art, moved])
        rasters.append(dict(r, dx=dx, dy=dy, anchor=ov['anchor'], note=ov.get('note')))
    if spec.get('overlays'): assert art.geom_type == 'Polygon', (spec['id'], art.geom_type)
    return {'id': spec['id'], 'src_name': base['file'],
        'w': base['w'], 'h': base['h'], 'ink': ink, 'art': art, 'rasters': rasters,
        'opaque_px': sum(r['opaque_px'] for r in rasters),
        'processing': None if len(rasters) == 1 else 'overlays positioned on the base raster: '+', '.join(r['file'] for r in rasters[1:])}


def load_base(preset):
    """Wave base art printed as-is, vertically centred, slot ink cleared.

    The raster has no alpha channel: it is a full-bleed opaque strip, so the
    plate cut is the base rectangle itself and only the slot windows need the
    ink knocked out (1.5 mm beyond each slot), as the PAD builder did.
    """
    source = SRC/'07_base_art.png'
    im = Image.open(source)
    if im.mode != 'RGBA': im = im.convert('RGBA')
    a = np.asarray(im)
    ys, xs = np.nonzero(a[..., 3] > 8)
    assert len(ys), source
    x0, y0 = int(xs.min()), int(ys.min())
    im = im.crop((x0, y0, int(xs.max())+1, int(ys.max())+1)); pw, ph = im.size
    aw = CFG['base_art_mm'][0]
    s = aw/pw; h = ph*s
    assert abs(h-CFG['base_art_mm'][1]) < .05, (h, CFG['base_art_mm'][1])
    tw, th = max(1, min(round(aw*PPI), pw)), max(1, min(round(h*PPI), ph))
    res = im.resize((tw, th), Image.LANCZOS)
    arr = np.asarray(res).copy()
    # Art-local coordinates: the image top row is the plate BACK edge, the
    # same flip positioned() applies when placing the ink on the board.
    inset_x = CFG['base_art_inset_mm']
    inset_y = (CFG['base_mm'][1]-h)/2
    cleared = []
    for pid, mx, my in [(p['id'], m[0], m[1]) for p in CFG['pieces'] for m in p['mounts_mm']]:
        cx_img = mx-inset_x
        cy_img = inset_y+h-my
        window = rounded(cx_img-CFG['slot_length_mm']/2, cy_img-preset['slot_width_mm']/2,
                         CFG['slot_length_mm'], preset['slot_width_mm'],
                         CFG['slot_corner_radius_mm']).buffer(2.0)
        # 2.0 mm clip = 1.5 mm spec plus slack exceeding the LANCZOS upsample
        # transition band at the window's hard alpha edge (PAD convention).
        outline = np.round(np.asarray(window.exterior.coords)*np.array([tw/aw, th/h])).astype(np.int32)
        cv2.fillPoly(arr, [outline], (0, 0, 0, 0))
        cleared.append({'id': pid, 'center_img_px': [int(cx_img*tw/aw), int(cy_img*th/h)]})
    cleared_im = Image.fromarray(arr, 'RGBA')
    buf = io.BytesIO(); cleared_im.save(buf, 'PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    ink = (f'<image x="0" y="0" width="{aw:.6f}" height="{h:.6f}" '
           f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    return {'src_name': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_px': [pw, ph], 'source_bbox_px': [x0, y0, pw, ph], 'resample_px': [tw, th],
        'w': aw, 'h': h, 'ink': ink, 'opaque_px': int((np.asarray(cleared_im)[:, :, 3] > 8).sum()),
        'native_cap': bool(tw < pw-1 or (tw == pw and th == ph and round(aw*PPI) > pw)),
        'effective_ppi': round(tw/(aw/25.4)),
        'processing': 'slot windows ink-cleared 1.5 mm by builder (in-memory)'}


def _window_section(g, y, cx, half):
    seg = g.intersection(LineString([(cx-half-4.001, y), (cx+half+4.001, y)]))
    if seg.is_empty: return 0.0, []
    parts = list(seg.geoms) if seg.geom_type == 'MultiLineString' else [seg]
    return seg.length, parts


def bud_guard(g, tab_cx, half, rise, shoulder, a_id):
    """The low slab hides the tab seam, but a floating pose can cross the
    slab top as one narrow ligament - the whole figure would then hang on
    that bud. Raise a slim riser under it until the buffered silhouette
    alone meets the load-path floor."""
    boxes = {}; recs = {}
    for cx in tab_cx:
        samples = []
        for i in range(160):
            y = shoulder-rise-.125-.25*i
            if y < shoulder-40: break
            w, parts = _window_section(g, y, cx, half)
            samples.append((w, y, parts))
            if w >= CFG['tab_width_mm']-.001: break
        if not samples or min(s[0] for s in samples) >= LOAD_PATH_FLOOR_MM-.05:
            continue
        worst = min(samples, key=lambda s: s[0])
        if not worst[2]: continue
        pinch_top = min(y for w, y, _ in samples if w < LOAD_PATH_FLOOR_MM)
        load = max(worst[2], key=lambda p: p.length)
        mx = (load.bounds[0]+load.bounds[2])/2
        rw = LOAD_PATH_FLOOR_MM+.25
        top = pinch_top-.25
        boxes[cx] = box(mx-rw/2, top, mx+rw/2, shoulder)
        recs[round(cx, 2)] = {'riser_width_mm': round(rw, 2),
            'riser_top_above_slot_mm': round(shoulder-top, 2),
            'worst_section_before_mm': round(worst[0], 2),
            'worst_at_above_slot_mm': round(shoulder-worst[1], 2)}
        print(f"bud guard: {a_id} cx={cx:.1f} worst {worst[0]:.2f} mm at "
              f"{shoulder-worst[1]:.2f} mm above slot -> riser {rw:.2f} mm wide "
              f"to {shoulder-top:.2f} mm", flush=True)
    return list(boxes.values()), recs


def standee(a, base_thickness, mounts, plinth_rise=8, simplify_tol=.015, border=None):
    border = CFG['clear_border_mm'] if border is None else border; art = a['art']
    body = art.buffer(border, quad_segs=28)
    if body.geom_type != 'Polygon': body = concave_hull(body, ratio=.5)
    body = Polygon(body.exterior)
    shoulder = art.bounds[3]+border
    depth = base_thickness-CFG['tab_bottom_clearance_mm']
    mean_x = sum(m[0] for m in mounts)/len(mounts)
    half = CFG['tab_width_mm']/2
    tabs = []; bridges = []; tab_cx = []
    for mx, my in mounts:
        cx = (mx-mean_x)+a['w']/2
        tab_cx.append(cx)
        tabs.append(tab_shape(cx, shoulder, depth))
        bridges.append(box(cx-half-4, shoulder-plinth_rise, cx+half+4, shoulder))
    union = unary_union([body]+bridges)
    if union.geom_type == 'Polygon': union = Polygon(union.exterior)
    guard, guard_recs = bud_guard(union, tab_cx, half, plinth_rise, shoulder, a['id'])
    if guard: union = unary_union([union]+guard)
    body = union.intersection(box(-80, -80, BOARD[0]+80, shoulder))
    if body.geom_type == 'Polygon': body = Polygon(body.exterior)
    union = unary_union([body]+tabs)
    if union.geom_type == 'Polygon': union = Polygon(union.exterior)
    shape = union.simplify(simplify_tol, preserve_topology=True)
    assert shape.geom_type == 'Polygon' and shape.is_valid and not shape.interiors
    assert shape.contains(art)
    clearance = shape.boundary.distance(art)
    assert border-simplify_tol-.005 <= clearance <= border+.05, (a['id'], clearance)
    for cx in tab_cx:
        section = shape.intersection(LineString([(cx-30, shoulder+.15), (cx+30, shoulder+.15)]))
        assert abs(section.length-CFG['tab_width_mm']) < .001, (a['id'], cx, section.length)
    # Load path: between the slot line and the first full-width section the
    # buffered silhouette inside every mount window must meet the floor.
    for cx in tab_cx:
        y = shoulder-plinth_rise-.125
        while y > shoulder-40:
            w, _ = _window_section(shape, y, cx, half)
            if w >= CFG['tab_width_mm']-.001: break
            assert w >= LOAD_PATH_FLOOR_MM-.2, (a['id'], round(shoulder-y, 2), round(w, 2))
            y -= .25
    assert depth > 1 and abs(shape.bounds[3]-shoulder-depth) < .001
    return {'poly': shape, 'tab_cx': tab_cx, 'shoulder': shoulder, 'depth': depth,
        'mount_mean_x': mean_x, 'clearance': clearance, 'border': border, 'bud_guard': guard_recs}


def base_slots(preset):
    L = CFG['slot_length_mm']; r = CFG['slot_corner_radius_mm']; sw = preset['slot_width_mm']
    slots = []
    for p in CFG['pieces']:
        for mx, my in p['mounts_mm']:
            slots.append((p['id'], mx, my, rounded(mx-L/2, my-sw/2, L, sw, r)))
    return slots


def standing_cuts(shapes):
    """Cut silhouettes as the plates stand in the assembly (front view, y up)."""
    out = {}
    for p in CFG['pieces']:
        s = shapes[p['id']]; mts = p['mounts_mm']
        txs = [mx-cx for (mx, my), cx in zip(mts, s['tab_cx'])]
        assert max(txs)-min(txs) < 1e-9, (p['id'], txs)
        g = affinity.translate(s['poly'], txs[0], 0)
        g = affinity.scale(g, xfact=1, yfact=-1, origin=(0, 0))
        out[p['id']] = (affinity.translate(g, 0, s['shoulder']), mts[0][1])
    return out


def assembly_clearance(shapes):
    """Plates sharing one depth row share one physical plane: their standing
    cuts must never touch. Art may overhang the base outline by at most
    12 mm."""
    st = standing_cuts(shapes)
    rows = {}
    for pid, (g, my) in st.items(): rows.setdefault(my, []).append((pid, g))
    mind = None; worst = None
    for my, members in rows.items():
        for i in range(len(members)):
            for j in range(i+1, len(members)):
                d = members[i][1].distance(members[j][1])
                if mind is None or d < mind: mind, worst = d, (members[i][0], members[j][0])
    for pid, (g, my) in st.items():
        b = g.bounds
        assert b[0] >= -12 and b[2] <= CFG['base_mm'][0]+12, (pid, b[0], b[2])
    assert mind is None or mind >= 2, (worst, mind)
    over = {pid: round(max(0, -g.bounds[0])+max(0, g.bounds[2]-CFG['base_mm'][0]), 2)
            for pid, (g, my) in st.items() if g.bounds[0] < 0 or g.bounds[2] > CFG['base_mm'][0]}
    return (round(mind, 2) if mind is not None else None), worst, over


def front_coverage(shapes):
    """Front-view occlusion sweep, reported (not asserted) for ORIGIN.

    ORIGIN is a deliberately stacked centre scene (tree across the moon,
    serpent behind the character): polygon occlusion is by design and
    overstates visual blocking (wide hair silhouettes). The numbers are
    recorded for review; composition acceptance is the vision-checked
    assembly preview against the supplied concept art. All structural
    checks (row clearance, overhang, load path, gaps) stay hard.
    """
    st = standing_cuts(shapes)
    out = {}
    for pid, (g, my) in st.items():
        blockers = [gg for q, (gg, myy) in st.items() if myy < my]
        u = unary_union(blockers) if blockers else None
        b = g.bounds
        band = g.intersection(box(b[0], b[3]-.3*(b[3]-b[1]), b[2], b[3]))
        total = (u.intersection(g).area/g.area) if u else 0.
        top = (u.intersection(band).area/band.area) if u else 0.
        out[pid] = {'total_pct': round(total*100, 1), 'top30_pct': round(top*100, 1)}
    return out


def positioned(assets, shapes, preset):
    base = rounded(0, 0, *CFG['base_mm'], CFG['base_corner_radius_mm'])
    slots = base_slots(preset)
    for pid, mx, my, s in slots:
        assert base.contains(s) and base.boundary.distance(s) > 8, (pid, mx, my)
    for i in range(len(slots)):
        for j in range(i+1, len(slots)):
            gap = slots[i][3].distance(slots[j][3])
            assert gap >= 2.99, (slots[i][:3], slots[j][:3], gap)
    items = []
    for p in CFG['pieces']:
        a = assets[p['id']]; s = shapes[p['id']]
        poly = s['poly']; bx, by = poly.bounds[0], poly.bounds[1]
        x, y = p['board_xy_mm']; tx, ty = x-bx, y-by
        items.append({'name': p['id'], 'poly': affinity.translate(poly, tx, ty),
                      'tx': tx, 'ty': ty, 'ink': a['ink'], 'holes': [],
                      'rasters': [dict(r, x=tx+r['dx'], y=ty+r['dy']) for r in a['rasters']],
                      'opaque_px': a['opaque_px']})
    tx, ty = CFG['base_board_xy_mm']; inset_x = CFG['base_art_inset_mm']; b = assets['base']
    inset_y = (CFG['base_mm'][1]-b['h'])/2
    # The raster's image-top is the plate's BACK edge; cut y0 is the front
    # edge, so the image is placed vertically mirrored to line up with the
    # cut outline and the slot windows cleared by load_base.
    flip = f'translate({inset_x:.6f} {inset_y+b["h"]:.6f}) scale(1 -1)'
    items.append({'name': 'base', 'poly': affinity.translate(base, tx, ty), 'tx': tx, 'ty': ty,
                  'ink': f'<g transform="{flip}">{b["ink"]}</g>',
                  'holes': [affinity.translate(s[3], tx, ty) for s in slots],
                  'rasters': [dict(b, x=tx+inset_x, y=ty+inset_y, anchor='base')],
                  'opaque_px': b['opaque_px']})
    for p in items:
        assert box(8, 8, BOARD[0]-8, BOARD[1]-6).contains(p['poly']), (p['name'], p['poly'].bounds)
    gap = min(p['poly'].distance(q['poly']) for i, p in enumerate(items) for q in items[:i])
    assert gap >= 6, gap
    return items, gap


def make_board(assets, shapes, preset, folder):
    items, gap = positioned(assets, shapes, preset)
    w, h = BOARD
    ink = layer('3_ARTWORK', artwork_layer(items))
    reference = layer('2_CORNER_REFERENCE', f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="{BLUE}" stroke-width="0.3"/>')
    cutting = layer('1_LASER_CUT', cut_layer(items))
    master = write_svg(folder/'02_MASTER.svg', w, h, ink+reference+cutting)
    printing = write_svg(folder/'01_PRINT.svg', w, h, ink+reference)
    write_svg(folder/'03_CUT_ONLY.svg', w, h, cutting)
    export_native(master, folder)
    export_png(printing, folder/'01_PRINT_300ppi.png')
    runvc(['convert', printing, folder/'01_PRINT.pdf'])
    runvc(['convert', folder/'03_CUT_ONLY.svg', folder/'03_CUT_ONLY.pdf'])
    depths = sorted({round(m[1], 1) for p in CFG['pieces'] for m in p['mounts_mm']})
    bd = assets['backdrop']
    labels = (svg_text(13, 396, f'LEN DIORAMA ORIGIN V2 / {preset["name"]} / {PIECE_COUNT} PIECES', 4.0)
        + svg_text(13, 403, f'BASE / {CFG["base_mm"][0]:.0f} x {CFG["base_mm"][1]:.1f} cut / wave art {assets["base"]["w"]:.0f} x {assets["base"]["h"]:.1f} centred + 2.5 clear rim', 3.1)
        + svg_text(13, 410, f'{SLOT_COUNT} SLOTS 18.8 x {preset["slot_width_mm"]:.2f} / rows y {depths} (backdrop: 3 tabs)', 3.1)
        + svg_text(13, 417, f'BACKDROP {shapes["backdrop"]["poly"].bounds[2]-shapes["backdrop"]["poly"].bounds[0]:.0f}x{bd["h"]:.0f} (sky + doors + moon/clouds)  TREE {assets["tree"]["w"]:.0f}x{assets["tree"]["h"]:.0f}  SNAKE {assets["snake"]["w"]:.0f}x{assets["snake"]["h"]:.0f}  CHARACTER {assets["character"]["w"]:.0f}x{assets["character"]["h"]:.0f}  / clear rim {CFG["clear_border_mm"]:.1f} (tree {shapes["tree"]["border"]:.1f})', 3.0))
    preview = write_svg(folder/'preview/flat_layout.svg', w, h,
        f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'+ink+reference+cut_layer(items, .17)+labels)
    render(preview, folder/'preview/flat_layout.png', 2.2)
    preview.unlink()
    return items, gap


def assembly(assets, shapes, preset, folder):
    """Axonometric assembly preview from the real cut polygons; illustrative.

    Clear acrylic is drawn see-through on the concept's dark mauve ground:
    plate bodies get no fill and a single thin lit-edge stroke stands for the
    cut edge (V1 filled every plate near-white and drew each one twice, which
    produced the white halos and the double outlines; on a light ground even
    an unfilled plate reads as white). Tabs are clipped at the shoulder line
    because they sit inside the base slots. Plates are drawn back to front:
    backdrop, tree, serpent, character.
    """
    ox, oy = 62, 212; dx, dy = .22, -.26
    bw, bh = CFG['base_mm']
    bt = preset['base_thickness_mm']
    base = rounded(0, 0, bw, bh, CFG['base_corner_radius_mm'])
    slots = base_slots(preset)
    inset_x = CFG['base_art_inset_mm']; inset_y = (bh-assets['base']['h'])/2; b = assets['base']
    EDGE = '#f2b9ff'; EDGE_W = .26; SIDE = 'rgba(236,170,255,.42)'; SLOT = 'rgba(242,185,255,.55)'
    TEXT = '#efe6f7'
    parts = [f'<rect width="400" height="260" fill="#5f4f82"/>',
             '<ellipse cx="212" cy="236" rx="182" ry="10" fill="rgba(40,28,66,.45)"/>',
             '<ellipse cx="212" cy="226" rx="200" ry="26" fill="rgba(214,170,236,.16)"/>']
    # Slab: bottom outline, the visible lit front side band, then the clear top.
    bottom = affinity.affine_transform(base, [1, dx, 0, dy, ox, oy])
    top = affinity.affine_transform(base, [1, dx, 0, dy, ox, oy-bt])
    parts.append(path(poly_path(bottom), 'none', EDGE, EDGE_W))
    parts.append(path(poly_path(bottom.difference(top)), SIDE, EDGE, EDGE_W))
    stage = path(poly_path(top), 'none', EDGE, EDGE_W)
    stage += f'<g transform="translate({ox+inset_x:.6f} {oy-bt+inset_y+b["h"]:.6f}) scale(1 -1)">{b["ink"]}</g>'
    for _, _, _, s in slots:
        slot = affinity.affine_transform(s, [1, dx, 0, dy, ox, oy-bt])
        stage += path(poly_path(slot), 'rgba(40,28,66,.35)', SLOT, .18)
    parts.append(stage)
    for spec in CFG['pieces']:
        pid = spec['id']
        mx = sum(m[0] for m in spec['mounts_mm'])/len(spec['mounts_mm'])
        my = spec['mounts_mm'][0][1]
        a = assets[pid]; s = shapes[pid]
        X = ox+mx+dx*my-a['w']/2; Y = oy+dy*my-bt-s['shoulder']
        body = s['poly'].intersection(box(-200, -200, 600, s['shoulder']))
        if body.geom_type != 'Polygon': body = max(body.geoms, key=lambda g: g.area)
        parts.append(f'<g transform="translate({X:.4f} {Y:.4f})">'
                     + path(poly_path(body), 'none', EDGE, EDGE_W) + a['ink'] + '</g>')
    parts.append(svg_text(13, 15, 'LEN DIORAMA ORIGIN V2', 5, TEXT))
    parts.append(svg_text(13, 23, f'base {bw:.0f} x {bh:.1f} mm / {PIECE_COUNT} pieces / clear rim {CFG["clear_border_mm"]:.1f} mm (tree {shapes["tree"]["border"]:.1f}) / clear acrylic drawn see-through on a dark ground', 3.4))
    parts.append(svg_text(13, 252, f'V2 / {preset["name"]} / one back panel: sky + lattice doors + moon and clouds / tree, serpent, character plates', 3.1))
    svg = write_svg(folder/'preview/assembly.svg', 400, 260, ''.join(parts))
    render(svg, folder/'preview/assembly.png', 2.7)
    svg.unlink()


def validate(assets, shapes, preset, items, gap, folder):
    mind, worst, over = assembly_clearance(shapes)
    cov = front_coverage(shapes)
    im = Image.open(folder/'01_PRINT_300ppi.png')
    assert im.mode == 'RGBA' and im.size == tuple(round(v*PPI) for v in BOARD)
    assert abs(im.info['dpi'][0]-300) < .1
    arr = np.asarray(im)
    blue = (arr[:, :, 2] > 240)&(arr[:, :, 0] < 10)&(arr[:, :, 1] < 10)&(arr[:, :, 3] > 150)
    w, h = BOARD
    for x, y in [(w/2, 4), (w/2, h-4), (4, h/2), (w-4, h/2)]:
        xx, yy = round(x*PPI), round(y*PPI)
        assert blue[yy-3:yy+4, xx-3:xx+4].any()
    # Four margins: no non-blue ink near the sheet edges (ref line is blue).
    m = round(3.7*PPI)
    strips = [arr[:m, :, :], arr[-m:, :, :], arr[:, :m, :], arr[:, -m:, :]]
    nonblue = lambda a: int(((a[:, :, 3] > 10)&~((a[:, :, 2] > 240)&(a[:, :, 0] < 10)&(a[:, :, 1] < 10))).sum())
    assert [nonblue(s) for s in strips] == [0, 0, 0, 0]
    reader = PdfReader(folder/'02_MASTER.ai'); page = reader.pages[0]
    assert abs(float(page.mediabox.width)*25.4/72-BOARD[0]) < .01
    assert abs(float(page.mediabox.height)*25.4/72-BOARD[1]) < .01
    names = [r.get_object()['/Name'] for r in reader.trailer['/Root']['/OCProperties']['/OCGs']]
    assert names == ['3_ARTWORK', '2_CORNER_REFERENCE', '1_LASER_CUT']
    text = (folder/'03_CUT_ONLY.svg').read_text(encoding='utf-8')
    assert text.count('<path ') == CUT_PATH_COUNT and text.count(' Z"') == CUT_PATH_COUNT and BLUE not in text
    assert len(items) == PIECE_COUNT and sum(len(p['holes']) for p in items) == SLOT_COUNT
    for p in items:
        for hole in p['holes']: assert p['poly'].contains(hole)
    for p in CFG['pieces']:
        for r in assets[p['id']]['rasters']:
            assert abs(r['w']/r['h']-r['source_px'][0]/r['source_px'][1]) < 1e-9
            x0, y0, x1, y1 = r['art'].bounds
            quant = 1/max(1, min(r['source_px'])-1)
            assert abs((x1-x0)/(y1-y0)-r['source_px'][0]/r['source_px'][1]) < .003+quant, (p['id'], r['file'])
    b = assets['base']
    assert abs(b['w']/b['h']-b['source_px'][0]/b['source_px'][1]) < .003
    # Slot centres carry no ink; tab tips are unprinted.
    for p in items:
        if p['name'] == 'base':
            mask = np.zeros(arr.shape[:2], np.uint8)
            for hole in p['holes']:
                outline = np.round(np.asarray(hole.buffer(1.5).exterior.coords)*PPI).astype(np.int32)
                cv2.fillPoly(mask, [outline], 1)
            assert not arr[:, :, 3][mask.astype(bool)].any(), 'Ink must clear every slot by 1.5 mm'
        else:
            s = shapes[p['name']]
            for cx in s['tab_cx']:
                x, y = p['tx']+cx, p['ty']+s['shoulder']+s['depth']/2
                assert arr[round(y*PPI), round(x*PPI), 3] == 0
    # Each embedded raster actually printed where it sits. Overlays on the
    # opaque sky are recognised by colour under their own opaque mask: a
    # pixel count there would also count the sky beneath them.
    for p in items:
        for r in p['rasters']:
            x0, y0 = round(r['x']*PPI), round(r['y']*PPI)
            region = arr[y0:y0+round(r['h']*PPI), x0:x0+round(r['w']*PPI), 3]
            rpx = r['resample_px']
            if r['anchor'] != 'base':
                mask = np.asarray(Image.fromarray(r['res_alpha']).resize((region.shape[1], region.shape[0]), Image.BILINEAR)) > 128
                printed = arr[y0:y0+region.shape[0], x0:x0+region.shape[1], :3][mask].astype(float)
                assert len(printed) >= .5*int((r['res_alpha'] > 128).sum()), (p['name'], r['file'], 'overlay missing')
                delta = float(np.linalg.norm(printed.mean(0)-r['mean_rgb']))
                assert delta < 30, (p['name'], r['file'], 'overlay colour', round(delta, 1))
                continue
            if (region.shape[1], region.shape[0]) != tuple(rpx):
                region = np.asarray(Image.fromarray(region).resize(tuple(rpx), Image.BILINEAR))
            cnt = int((region > 8).sum())
            assert .55*r['opaque_px'] <= cnt <= 1.6*r['opaque_px'], (p['name'], r['file'], cnt, r['opaque_px'])
    depths = sorted({m[1] for p in CFG['pieces'] for m in p['mounts_mm']})
    heights = {pid: round(preset['base_thickness_mm']+assets[pid]['h']+shapes[pid]['border'], 2)
               for pid in assets if pid != 'base'}
    report = {'revision': CFG['revision'], 'product': CFG['product'], 'concept_title': CFG['concept_title'],
        'character': CFG['character'], 'source_pack': CFG['source_pack'],
        'preset': preset, 'canvas_mm': list(BOARD),
        'base_mm': CFG['base_mm'], 'base_art_mm': [round(b['w'], 3), round(b['h'], 3)],
        'base_art_inset_mm': CFG['base_art_inset_mm'],
        'base_art_vertical': CFG['base_art_vertical'],
        'base_corner_radius_mm': CFG['base_corner_radius_mm'],
        'clear_border_mm': CFG['clear_border_mm'], 'clear_border_rationale': CFG['clear_border_rationale'],
        'clear_border_per_piece_mm': {p['id']: shapes[p['id']]['border'] for p in CFG['pieces']},
        'pieces': PIECE_COUNT, 'finished_size_mm': CFG['finished_size_mm'],
        'assembled_height_mm': heights, 'depth_rows_mm': [round(d, 2) for d in depths],
        'cut_closed_paths': CUT_PATH_COUNT, 'hole_paths_first': True, 'slot_count': SLOT_COUNT,
        'tab_width_mm': CFG['tab_width_mm'],
        'tab_depth_mm': shapes['backdrop']['depth'],
        'slot_length_mm': CFG['slot_length_mm'], 'slot_width_mm': preset['slot_width_mm'],
        'dimensions_are': 'nominal 18.8 x T cut-path centerlines; kerf and fit compensation is applied by scripts/build_a3_release.py (len_slot_fit, issue #1 policy)',
        'fit_status': 'UNTESTED; no fit-test pieces by repo policy',
        'physical_fit_test': False, 'test_pieces_included': False,
        'minimum_piece_gap_mm': gap, 'ai_layers': names,
        'same_row_standing_clearance_mm': mind, 'same_row_worst_pair': list(worst) if worst else None,
        'same_row_note': 'every plate stands on its own depth row; no same-row pairs exist',
        'art_overhang_beyond_base_mm': over,
        'front_view_coverage_pct': cov,
        'front_view_policy': CFG['front_view_policy'],
        'load_path_floor_mm': LOAD_PATH_FLOOR_MM,
        'bud_guard_risers': {p['id']: shapes[p['id']]['bud_guard']
            for p in CFG['pieces'] if shapes[p['id']]['bud_guard']},
        'blue_reference_four_sides': True, 'unprinted_tabs_and_slots': True,
        'slot_ink_clearance_checked_mm': 1.5, 'margins_nonblue_ink': True,
        'base_plate': 'supplied raster 07_base_art printed as-is, vertically centred '
                      'on a 2.5 mm clear rim; 6 slot windows ink-cleared 1.5 mm in-memory '
                      'by the builder (no separate prepared copy, no placeholder-slot surgery)',
        'piece_breakdown': {
            'backdrop': 'one plate: 05_background sky with both 06_lattice_doors islands butted against its sides (bottoms aligned) and the whole 04_moon_clouds layer (both islands) registered 5 mm below the sky top; 3 tabs',
            'tree': '03_blossom_tree silhouette plate, 1 tab',
            'snake': '02_snake silhouette plate, 1 tab',
            'character': '01_character silhouette plate, 1 tab'},
        'layer_order_back_to_front': ['backdrop', 'tree', 'snake', 'character'],
        'revision_changes_vs_v1': CFG['revision_note'],
        'preview_rendering': 'clear acrylic see-through on a dark mauve ground: plate bodies unfilled, one 0.26 mm lit-edge stroke per plate, tabs clipped at the shoulder (inside the slots); base slab shows its front side band',
        'unused_source_islands': CFG['unused_source_islands'],
        'assets': {p['id']: {'file': assets[p['id']]['src_name'],
            'sha256': assets[p['id']]['rasters'][0]['sha256'],
            'rasters': [{'file': r['file'], 'sha256': r['sha256'], 'anchor': r['anchor'],
                'offset_mm': [round(r['dx'], 3), round(r['dy'], 3)],
                'source_bbox_px': r['source_bbox_px'], 'source_px': r['source_px'],
                'resample_px': r['resample_px'],
                'art_width_mm': round(r['w'], 3), 'art_height_mm': round(r['h'], 3),
                'effective_ppi': r['effective_ppi'], 'native_cap': r['native_cap'],
                'processing': r['processing'], 'note': r.get('note')}
                for r in assets[p['id']]['rasters']],
            'art_width_mm': round(assets[p['id']]['w'], 3), 'art_height_mm': round(assets[p['id']]['h'], 3),
            'minimum_art_to_cut_mm': shapes[p['id']]['clearance'],
            'clear_border_mm': shapes[p['id']]['border'],
            'resample': 'LANCZOS; exact 300 ppi print size, never upscaled past native pixels', 'redrawn': False,
            'processing': assets[p['id']]['processing']}
            for p in CFG['pieces']}}
    report['assets']['base'] = {'file': b['src_name'], 'sha256': b['sha256'],
        'source_px': b['source_px'], 'source_bbox_px': b['source_bbox_px'],
        'resample_px': b['resample_px'],
        'art_width_mm': round(b['w'], 3), 'art_height_mm': round(b['h'], 3),
        'resample': 'LANCZOS; exact 300 ppi print size, never upscaled past native pixels', 'redrawn': False,
        'native_cap': b['native_cap'],
        'effective_ppi': b['effective_ppi'],
        'processing': b['processing']}
    (folder/'validation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def prune_archive(folder, keep_preview):
    """Keep exactly the archive set the A3 release consumes (PAD snapshot shape)."""
    keep = {'02_MASTER.ai', '03_CUT_ONLY.pdf', 'validation_report.json'}
    for file in sorted(folder.iterdir()):
        if file.is_file() and file.name not in keep:
            file.unlink()
    preview = folder/'preview'
    if preview.is_dir():
        for file in sorted(preview.iterdir()):
            if not (keep_preview and file.name == 'assembly.png'):
                file.unlink()
        if not any(preview.iterdir()):
            preview.rmdir()


def main():
    OUT.mkdir(parents=True, exist_ok=True); TMP.mkdir(parents=True, exist_ok=True)
    presets = CFG['presets']
    assets = {p['id']: load_piece(p) for p in CFG['pieces']}
    reports = []
    for preset in presets:
        folder = OUT/preset['name']; (folder/'preview').mkdir(parents=True, exist_ok=True)
        assets['base'] = load_base(preset)
        shapes = {p['id']: standee(assets[p['id']], preset['base_thickness_mm'], p['mounts_mm'], p.get('plinth_rise_mm', 8), p.get('simplify_mm', .015), p.get('clear_border_mm', CFG['clear_border_mm'])) for p in CFG['pieces']}
        items, gap = make_board(assets, shapes, preset, folder)
        assembly(assets, shapes, preset, folder)
        report = validate(assets, shapes, preset, items, gap, folder); reports.append(report)
        print(json.dumps({'preset': preset['name'], 'pieces': PIECE_COUNT, 'cut_paths': CUT_PATH_COUNT,
            'same_row_mm': report['same_row_standing_clearance_mm'],
            'coverage': report['front_view_coverage_pct'],
            'risers': report['bud_guard_risers'],
            'art': {k: round(v['w'], 1) for k, v in assets.items() if k != 'base'},
            'plate_bounds': {k: [round(x, 1) for x in v['poly'].bounds] for k, v in shapes.items()},
            'base': [round(assets['base']['w'], 1), round(assets['base']['h'], 1)]}, ensure_ascii=False), flush=True)
        prune_archive(folder, keep_preview=preset is presets[0])
    print(json.dumps({'product': CFG['product'], 'archive': [str(p.relative_to(ROOT)) for p in sorted(OUT.rglob('*')) if p.is_file()]}), flush=True)


if __name__ == '__main__':
    main()
