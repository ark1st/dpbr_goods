"""Len ORIGIN layered slot-in acrylic diorama, V10.

Lineage: V1 (commit 2ac3ad0, scripts/build_len_diorama_origin.py) built one
base plus seven plates with a 2.5 mm clear border. The owner rejected the
assembled look ("too many borders"): the preview painted every clear plate
near-white and drew each one twice, so every element carried a thick halo
plus a second outline, and the two doors and the background added heavy
rectangular frames. V2 (73a2823) kept the V1 slot-in mechanics (18 mm tabs,
18.8 mm nominal slots, 0.4 mm bottom clearance, 12 mm load-path floor with the
automatic bud guard) and changed the piece breakdown, the rim and the preview.
V3 (657a484) recomposed the scene to the concept but the owner prefers V2. V4
(a2a83cd) restored the V2 design as its base (this builder = V2 plus V3's pure
bud-guard bug fix: an empty tab window now raises the riser on the tab axis
and every riser is clamped inside the tab window) and applied two owner
requests: the blossom tree printed into the back panel and Len "seated" by
cropping her raster at the seat line. V5 (7459c7f) restructured the scene (Len
whole on a 70 mm serpent's coil, the tree back as ONE cut plate whose 2.5 mm
canopy envelope webbed the blossoms together with clear acrylic) and the owner
rejected it. V6 (62963a8) = V4 with exactly those two changes: Len shown
whole and the printed tree leaning up to the right like the concept. V7
(e8a480e) split the tree into a wood cut piece plus six pink blossom cluster
plates on clear stems.

V8 = the owner's correction ("벚꽃-나무는 하나여야지": the blossom tree must be
ONE piece; "저 문": the assets he wanted separate are the DOORS, which V7
still printed flat on the back panel):

* TREE, one piece: the complete blossom tree - trunk, branches and every
  blossom cluster - as ONE cut piece printed with the original pixels (dark
  wood + pink blossoms), 35 deg clockwise, 88 mm art, standing behind the
  serpent on its own 18 mm tab at row 31 exactly like the V7 tree piece. The
  cut skeleton is the opaque mask opened 1.5 mm (twigs and petals under 3 mm
  of ink are not cut), so the gaps between branch/cluster groups are REAL
  cut-out openings through which the sky and moon show: no clear canopy fill,
  no stems, no separate cluster plates. Every detached cluster is attached
  along its own twig by a 2.75 mm clear connector with the twig printed
  inside; the body is buffered 1.0 mm and closed 1.25 mm; enclosed holes at
  least 2.5 mm wide are cut-out openings unless they would leave a neck under
  2.5 mm or cross the riser - those gaps, and every gap too narrow to cut,
  stay PRINTED with the back panel's blurred local colour instead of clear
  acrylic (pale over the moon, violet elsewhere, no detail baked in).
* DOORS, separate pieces: the two lattice doorways of 06_lattice_doors.png
  (85 mm art, 1.0 mm rim, the lattice printed and its wide holes cut out)
  on one 18 mm tab each at row 47 in front of the back panel, at scene
  x 40.3-70.7 and 209.3-239.8 exactly where V2-V7 printed them.
* The back panel loses the printed doors and keeps the sky, moon, clouds and
  water waves; the sky/wave raster is mirrored into the former door zones so
  the plate keeps its V7 outline.

V9 = the owner's final tweaks ("마지막 수정 문하고 배경 높이만 좀 맞춰주고 벛꽃나무는
문하고 캐릭터사이 왼쪽으로 빼봐": match the doors to the backdrop height; pull the
blossom tree out to the left, between the door and the character):

* DOOR HEIGHT = BACKDROP HEIGHT: both lattice door plates are scaled from
  85 mm to 89.57 mm art so each door's cut top stands at 92.0 mm above the
  base top, exactly the back panel's cut top (95.0 mm assembled). Same tab
  axis (x 55.5 / 224.5, row 47), same slots, 1.0 mm rim, symmetric.
* TREE MOVED LEFT: the same one-piece tree (V8 design unchanged: 35 deg
  clockwise, the cut skeleton is the opaque mask opened 1.5 mm at the 88 mm
  reference scale and carried to the smaller size, the same cluster
  connectors, rim, closing and opening rules in millimetres) stands in the
  gap between the LEFT DOOR and LEN, trunk base at scene x 96 on row 31
  behind the serpent. The 88 mm tree (95 mm wide) cannot fit the 63 mm gap
  without overlapping the door or Len, so it is scaled to 56.0 mm art - the
  largest size keeping at least 1.0 mm between the tree's cut and the door's
  and Len's cuts (a hard check in validate()). The canopy no longer crosses
  behind Len.

V10 = the owner's request ("나무 사이즈 복원하고 문그림하고 배경의 높이가 맞을때까지만
키워": restore the tree's size and grow it only up to the height where the
 door art and the backdrop line up):

* TREE SIZE: the same one-piece tree (V8 design unchanged: 35 deg
  clockwise, the cut skeleton is the opaque mask opened 1.5 mm at the 88 mm
  reference scale, the same cluster connectors, rim, closing and opening
  rules in millimetres) is restored past its V8 size and grown until its cut
  top stands on the shared door/backdrop top line: 103.5 mm art (1.176x the
  V8 88 mm, 1.848x the V9 56 mm), cut 111.3 x 92.0 mm, cut top 91.99 mm
  above the base top (94.99 mm assembled; the doors and the back panel stand
  at 92.0 / 95.0). The trunk base stays at scene x 96 on row 31 (no slot
  change). At this size the tree cannot fit the 62 mm gap between the left
  door and Len: it stands alone on its row (no same-row collision; hard
  check), its right half sits behind the serpent (row 23) as in V8, its
  canopy reaches 35.8 mm behind Len's cut (row 12) and 68 mm2 of upper-left
  blossoms pass behind the left door's top-right corner (row 47) - front-view
  overlaps between different depth rows, measured and reported, not
  asserted. The cut top never exceeds the shared line, the printed trunk
  base keeps >= 1.0 mm from the serpent's printed ink near the base line and
  the trunk-base region (z <= 8 mm) stays clear of the left door's cut (hard
  checks in validate()).

Everything else is V9 exactly, see configs/len_diorama_origin.json: whole
seated Len, serpent, moon, base, slots, 1.0 mm clear border on every plate,
the see-through assembly preview, native pixels (LANCZOS to the 300 ppi print
size, never upscaled; the tree's rotation is the only resampling step and
acts at native resolution before that downsample). No fit-test pieces: current
repo policy rejects all test pieces.

The product archive keeps exactly the files the A3 release consumes:
02_MASTER.ai, 03_CUT_ONLY.pdf, validation_report.json per thickness and
preview/assembly.png for 3T. Everything else is generated for validation,
then pruned; the A3 stage rebuilds print/cut/native files at sheet level.
"""
from pathlib import Path
import sys, json, base64, io, hashlib, math
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from scipy.ndimage import gaussian_filter1d
from shapely.geometry import Polygon, box, LineString, Point
from shapely import affinity, concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from laser_paths import cut_path, audit_path
from vector_utils import runvc, svg_doc, path, poly_path, layer

OUT = ROOT/'output/len_diorama_origin_v10'
TMP = ROOT/'tmp/len_diorama_origin_v10'
CFG = json.loads((ROOT/'configs/len_diorama_origin.json').read_text(encoding='utf-8'))
TRUNK_CLEARANCE_MM = CFG['tree_one_piece']['trunk_clearance_mm']
BOARD = tuple(CFG['board_mm'])
PPI = 300/25.4
RED = '#ff0000'
BLUE = '#0000ff'
SRC = ROOT/'assets/len_orgin'
LOAD_PATH_FLOOR_MM = 12.0
RISER_WIDTH_MM = LOAD_PATH_FLOOR_MM+.25
MIN_FEATURE_MM = CFG['tree_one_piece']['min_feature_mm']
PIECE_COUNT = 1 + len(CFG['pieces'])
SLOT_COUNT = sum(len(p['mounts_mm']) for p in CFG['pieces'])
CUT_PATH_COUNT = PIECE_COUNT+SLOT_COUNT   # main() adds the cut-out openings


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


def rotate_alpha(im, deg):
    """Rotate RGBA CLOCKWISE by `deg` at native resolution without dark fringes.

    Positive angles turn the picture clockwise on screen (the 12 o'clock point
    moves right). V4/V5 built the matrix the other way round, so their
    "clockwise" tree actually leaned counter-clockwise; V6 fixed the sign.

    RGB is premultiplied before the cubic warp and unpremultiplied after it, so
    transparent pixels (which store the source's dark ground colour) cannot
    bleed into the blossoms' edges. """
    a = np.asarray(im).astype(np.float32)
    al = a[..., 3:4]/255.0
    pm = np.concatenate([a[..., :3]*al, a[..., 3:4]], 2)
    th = math.radians(deg); c, s = math.cos(th), math.sin(th)
    H, W = al.shape[:2]
    xs = [c*x-s*y for x, y in [(0, 0), (W, 0), (0, H), (W, H)]]
    ys = [s*x+c*y for x, y in [(0, 0), (W, 0), (0, H), (W, H)]]
    x0, y0 = min(xs), min(ys)
    M = np.float32([[c, -s, -x0], [s, c, -y0]])
    rot = cv2.warpAffine(pm, M, (int(math.ceil(max(xs)-x0)), int(math.ceil(max(ys)-y0))),
                         flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    A = rot[..., 3:4]/255.0
    out = np.concatenate([np.where(A > 1e-4, rot[..., :3]/np.maximum(A, 1e-4), 0), A*255], 2).clip(0, 255).astype('uint8')
    return Image.fromarray(out, 'RGBA')


def source_pixels(spec):
    """Native pixels of one island or whole alpha-cropped raster after the
    print-preparation steps that act before any scaling.

    `rotate_deg` rotates clockwise (premultiplied alpha, cubic, native pixels)
    and re-crops the alpha box; `crop_below_fraction` (V4's seat crop, unused
    since V6: Len is shown whole) would drop everything below a fraction of
    the figure height. Returns the image, its source alpha bbox, the pixel height
    the configured art height refers to, and the processing note."""
    source = SRC/spec['file']
    im = Image.open(source)
    if im.mode != 'RGBA': im = im.convert('RGBA')
    a = np.asarray(im)
    processing = []
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
        processing.append('island separated from the bundled sheet by connected-component label; neighbour-bbox fragments alpha-zeroed, island pixels untouched')
    else:
        ys, xs = np.nonzero(a[..., 3] > 8)
        assert len(ys), source
        x0, y0 = int(xs.min()), int(ys.min())
        im = im.crop((x0, y0, int(xs.max())+1, int(ys.max())+1))
        bbox = [x0, y0, im.size[0], im.size[1]]
    ref_h = im.size[1]
    if spec.get('rotate_deg'):
        before = int((np.asarray(im)[..., 3] > 8).sum())
        im = rotate_alpha(im, spec['rotate_deg'])
        ys, xs = np.nonzero(np.asarray(im)[..., 3] > 8)
        im = im.crop((int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1))
        m = (np.asarray(im)[..., 3] > 8).astype('uint8')
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        specks = int((st[1:, 4] <= 6).sum())
        if specks:
            m[lab > 0] = (st[lab[lab > 0], 4] > 6).astype('uint8')
            arr = np.asarray(im).copy(); arr[m == 0, 3] = 0; im = Image.fromarray(arr, 'RGBA')
        processing.append(f"rotated {spec['rotate_deg']:g} deg clockwise at native resolution (premultiplied alpha, cubic); alpha box re-cropped; {specks} cubic-ringing specks <= 6 px removed; opaque px {before} -> {int((np.asarray(im)[..., 3] > 8).sum())}")
    if spec.get('crop_below_fraction'):
        f = spec['crop_below_fraction']; full = im.size[1]; keep = int(round(f*full))
        im = im.crop((0, 0, im.size[0], keep))
        processing.append(f'art below {f:.3f} of the figure height (the seat line) cropped in-memory: {keep} of {full} px kept so the seat rests on the base line')
    return im, bbox, ref_h, '; '.join(processing)


def load_raster(spec, border=None, clip_mm=None):
    """Embed one island or one whole alpha-cropped raster at exact print scale.

    `border` (standalone plates) asserts that every printed pixel lies within
    the clear rim of a kept contour, so no speck can print outside the cut.
    `clip_mm` crops the raster (native pixels, before resampling) to a box in
    millimetres from its own top-left so an overlay can be confined to its
    base raster without resampling."""
    source = SRC/spec['file']
    im, bbox, ref_h, processing = source_pixels(spec)
    ext = spec.get('extend_sky_mm')
    if ext:
        s0 = spec['art_height_mm']/ref_h
        l, r = int(round(ext['left']/s0)), int(round(ext['right']/s0))
        arr = cv2.copyMakeBorder(np.asarray(im), 0, 0, l, r, cv2.BORDER_REFLECT_101)
        im = Image.fromarray(arr, 'RGBA')
        bbox = [bbox[0]-l, bbox[1], bbox[2]+l+r, bbox[3]]
        processing += f"; sky/wave art extended into the former door zones by mirroring the raster's own edge columns (BORDER_REFLECT_101): {l} px = {l*s0:.2f} mm left, {r} px = {r*s0:.2f} mm right, no resampling"
    h = spec['art_height_mm']; s = h/ref_h
    clip_note = None
    if clip_mm is not None:
        x0, y0 = (int(math.ceil(v/s-1e-9)) for v in clip_mm[:2])
        x1, y1 = (int(math.floor(v/s+1e-9)) for v in clip_mm[2:])
        assert 0 <= x0 < x1 <= im.size[0] and 0 <= y0 < y1 <= im.size[1], (spec['file'], clip_mm, im.size)
        im = im.crop((x0, y0, x1, y1))
        clip_note = f'clipped to the base raster box: kept {[round(v, 3) for v in clip_mm]} mm of its own top-left'
    pw, ph = im.size
    w = pw*s; h = ph*s
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
        'processing': processing, 'clip': clip_note,
        'art_height_mm_config': spec['art_height_mm'], 'rotate_deg': spec.get('rotate_deg', 0),
        'crop_below_fraction': spec.get('crop_below_fraction'),
        'opaque_px': int((np.asarray(res)[:, :, 3] > 8).sum()),
        'res_alpha': ra[:, :, 3].copy(), 'mean_rgb': ra[solid][:, :3].mean(0),
        'native_cap': bool(tw < pw-1 or (tw == pw and th == ph and round(w*PPI) > pw)),
        'effective_ppi': round(tw/(w/25.4))}


def overlay_offset(anchor, bw, bh, ow, oh, top_margin, xy_mm=None):
    """Overlay top-left in the base raster's image coordinates (y down)."""
    if anchor == 'left_edge_bottom': return -ow, bh-oh
    if anchor == 'right_edge_bottom': return bw, bh-oh
    if anchor == 'top_center': return (bw-ow)/2, top_margin
    if anchor == 'xy_mm': return float(xy_mm[0]), float(xy_mm[1])
    raise ValueError(f'Unknown overlay anchor {anchor}')


def load_piece(spec):
    """One plate: a base raster plus overlays butted/registered onto it.

    Overlays are only positioned (no resampling beyond their own 300 ppi cap);
    their silhouettes join the plate's art union so the cut encloses them. An
    `xy_mm` overlay may overhang its base raster; the overhang is clipped in
    native pixels before resampling, so the plate keeps its rectangular cut.
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
        clip_mm = None
        if ov['anchor'] == 'xy_mm':
            im, _, ref_h, _ = source_pixels(ov); s = ov['art_height_mm']/ref_h
            ow, oh = im.size[0]*s, im.size[1]*s
            dx, dy = overlay_offset(ov['anchor'], base['w'], base['h'], ow, oh, 0, ov['xy_mm'])
            x0, y0, x1, y1 = max(0.0, -dx), max(0.0, -dy), min(ow, base['w']-dx), min(oh, base['h']-dy)
            assert x1 > x0 and y1 > y0, (spec['id'], ov['file'], 'overlay misses the base raster')
            if (x0, y0, x1, y1) != (0.0, 0.0, ow, oh): clip_mm = (x0, y0, x1, y1)
        r = load_raster(ov, clip_mm=clip_mm)
        dx, dy = overlay_offset(ov['anchor'], base['w'], base['h'], r['w'], r['h'], ov.get('top_margin_mm', 0), ov.get('xy_mm'))
        moved = box(dx, dy, dx+r['w'], dy+r['h'])
        assert art.distance(moved) < 1e-6, (spec['id'], ov['file'], 'overlay detached from the plate body')
        if ov['anchor'] in ('top_center', 'xy_mm'):
            assert art.buffer(1e-6).contains(moved), (spec['id'], ov['file'], 'overlay leaves the base raster')
        ink += f'<g transform="translate({dx:.6f} {dy:.6f})">{r["ink"]}</g>'
        art = unary_union([art, moved])
        rasters.append(dict(r, dx=dx, dy=dy, anchor=ov['anchor'], note=ov.get('note')))
    if spec.get('overlays'): assert art.geom_type == 'Polygon', (spec['id'], art.geom_type)
    return {'id': spec['id'], 'src_name': base['file'],
        'w': base['w'], 'h': base['h'], 'ink': ink, 'art': art, 'rasters': rasters,
        'opaque_px': sum(r['opaque_px'] for r in rasters),
        'processing': None if len(rasters) == 1 else 'overlays positioned on the base raster: '+', '.join(r['file'] for r in rasters[1:])}


def closing(p, r):
    return p.buffer(r, quad_segs=28).buffer(-r, quad_segs=28)


def neck_width(poly):
    """Narrowest connection of a plate: twice the erosion radius that first
    splits it into real parts (zero-area buffer slivers do not count)."""
    for k in range(1, 16):
        e = poly.buffer(-k*.25, quad_segs=16)
        parts = [g for g in (e.geoms if hasattr(e, 'geoms') else ([] if e.is_empty else [e])) if g.area > 1e-3]
        if len(parts) > 1: return 2*(k*.25-.125)
    return None


class OnePieceTree:
    """The complete blossom tree as one cut piece (V8 design, V10 size). All
    masks live on the native pixels of the 35 deg clockwise rotation V6-V8
    already used. The cut skeleton is the opaque mask opened 1.5 mm at the
    88 mm reference scale (`skeleton_ref_mm`): exactly the twigs and petals
    V8 cut are cut at any art height, while the rim, closing, connectors and
    opening rules are applied in millimetres at the configured art height."""

    def __init__(self, cfg):
        self.cfg = cfg
        spec = {'file': cfg['file'], 'art_height_mm': cfg['art_height_mm'], 'rotate_deg': cfg['rotate_deg']}
        self.im, self.bbox, self.ref_h, self.processing = source_pixels(spec)
        a = np.asarray(self.im)
        self.rgba = a
        self.s = cfg['art_height_mm']/self.ref_h
        self.pxmm = 1/self.s
        self.skeleton_ref_mm = cfg.get('skeleton_ref_mm', cfg['art_height_mm'])
        self.pxmm_skel = self.ref_h/self.skeleton_ref_mm
        self.opaque = a[..., 3] > 128
        r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
        red_dominant = (r-np.maximum(g, b) >= 45) & (r >= 110)
        self.wood = self.opaque & ~red_dominant
        self.H, self.W = self.opaque.shape

    def kernel(self, mm, pxmm=None):
        r = max(1, int(round(mm*(self.pxmm if pxmm is None else pxmm))))
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))

    def trunk_base_x(self):
        """Canvas x (mm) of the lowest wood pixel: the trunk base, V7's tab axis."""
        ys, xs = np.nonzero(self.wood)
        low = xs[ys >= ys.max()-max(1, int(round(.5*self.pxmm)))]
        return float(low.mean()*self.s)

    def skeleton(self):
        cfg = self.cfg
        S = cv2.morphologyEx(self.opaque.astype('uint8'), cv2.MORPH_OPEN, self.kernel(cfg['skeleton_open_mm'], self.pxmm_skel)) > 0
        n, lab, st, _ = cv2.connectedComponentsWithStats(S.astype('uint8'), 8)
        main = max(range(1, n), key=lambda i: st[i, 4])
        main_mask = lab == main
        frags = []
        for i in range(1, n):
            area = st[i, 4]*self.s*self.s
            if i != main and area >= cfg['fragment_min_mm2']:
                frags.append((i, area, lab == i))
        kept = main_mask.copy()
        for _, _, fm in frags: kept |= fm
        info = {'skeleton_open_mm': cfg['skeleton_open_mm'], 'skeleton_ref_mm': self.skeleton_ref_mm,
            'art_height_mm': cfg['art_height_mm'], 'scale_vs_reference': round(cfg['art_height_mm']/self.skeleton_ref_mm, 4), 'opaque_px': int(self.opaque.sum()),
            'skeleton_px': int(S.sum()), 'main_skeleton_px': int(main_mask.sum()),
            'detached_clusters': len(frags), 'detached_cluster_px': int(sum(f[2].sum() for f in frags)),
            'detached_cluster_areas_mm2': sorted((round(f[1], 1) for f in frags), reverse=True),
            'specks_cut_away_px': int(S.sum()-kept.sum())}
        return kept, main_mask, frags, info

    def geodesic(self, main_mask, frags):
        """Arrival-time geodesic distance from the main skeleton inside the
        opaque mask, then one twig path per detached cluster (backtracked)."""
        T = np.full((self.H, self.W), -1, 'int32'); T[main_mask] = 0
        frontier = main_mask.copy(); k = 0
        pending = {i: None for i, _, _ in frags}
        while frontier.any() and any(v is None for v in pending.values()):
            k += 1
            nxt = (cv2.dilate(frontier.astype('uint8'), np.ones((3, 3), 'uint8')) > 0) & self.opaque & (T < 0)
            T[nxt] = k; frontier = nxt
            for i, _, fm in frags:
                if pending[i] is None and (fm & nxt).any(): pending[i] = k
        paths, recs = {}, {}
        for i, area, fm in frags:
            ys, xs = np.nonzero(fm & (T >= 0))
            assert len(ys), ('detached cluster unreachable inside the opaque mask', i)
            j = int(np.argmin(T[ys, xs])); y, x = int(ys[j]), int(xs[j])
            path = [(x, y)]
            while T[y, x] > 0:
                y, x = next((y+dy, x+dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if 0 <= y+dy < self.H and 0 <= x+dx < self.W and T[y+dy, x+dx] == T[y, x]-1)
                path.append((x, y))
            paths[i] = path
            recs[int(i)] = {'cluster_mm2': round(area, 2), 'twig_path_mm': round(len(path)*self.s, 2)}
        return paths, recs


def mask_polygons(mask, s, sigma_px):
    """Smoothed polygons of a boolean mask: (outer union, enclosed holes)."""
    cnts, hier = cv2.findContours(mask.astype('uint8'), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    hier = hier[0] if hier is not None else []
    outers, holes = [], []
    for i, c in enumerate(cnts):
        if len(c) < 4 or cv2.contourArea(c) <= 1: continue
        pts = c[:, 0, :].astype(float)
        if len(pts) > 8:
            pts = np.stack([gaussian_filter1d(pts[:, 0], sigma_px, mode='wrap'), gaussian_filter1d(pts[:, 1], sigma_px, mode='wrap')], 1)
        p = Polygon(pts*[s, s]).buffer(0)
        if p.geom_type != 'Polygon': p = max(p.geoms, key=lambda g: g.area)
        if p.interiors: p = Polygon(p.exterior).buffer(0)
        (holes if len(hier) and hier[i][3] != -1 else outers).append(p)
    return unary_union(outers), holes


def opening_of(p, r):
    return p.buffer(-r, quad_segs=16).buffer(r, quad_segs=16)


def one_piece_body(skeleton, connectors, rules):
    """Cut body of a one-piece plate: skeleton buffered by the rim plus the
    connectors, closed so sky slits under the minimum feature vanish, with
    enclosed holes kept as cut-out openings only when they measure at least
    the minimum feature wide and leave every neck at least that wide. With
    `regularize` (doors) thin material features are widened to the minimum.
    Returns outer, openings, filled gaps (printed), gaps dropped for a neck."""
    rim, mf, om = rules['rim_mm'], rules['min_feature_mm'], rules['opening_min_mm']
    body = unary_union([skeleton.buffer(rim, quad_segs=28)]+connectors)
    assert body.geom_type == 'Polygon', ('one-piece body disconnected', len(body.geoms))
    body = closing(body, rules['closing_mm'])
    assert body.geom_type == 'Polygon', ('closing disconnected the body', len(body.geoms))
    outer = Polygon(body.exterior)
    openings, filled, dropped = [], [], []
    for ring in sorted(body.interiors, key=lambda r: -Polygon(r).area):
        o = Polygon(ring); w = neck_width(o)
        if w is None or w < om-.01:
            filled.append(o); continue
        holed = Polygon(outer.exterior, [q.exterior for q in openings]+[o.exterior])
        nw = neck_width(holed)
        if nw is not None and nw < mf-.01:
            dropped.append(o); continue
        openings.append(o)
    if rules.get('regularize'):
        R = mf/2+.05
        for _ in range(3):
            holed = Polygon(outer.exterior, [o.exterior for o in openings])
            thin = holed.difference(closing(opening_of(holed, R), R))
            if thin.is_empty or thin.area < 1e-6: break
            grown = unary_union([holed, thin.buffer(.25, quad_segs=16)])
            if grown.geom_type != 'Polygon': grown = max(grown.geoms, key=lambda g: g.area)
            grown = closing(grown, rules['closing_mm'])
            if grown.geom_type != 'Polygon': grown = max(grown.geoms, key=lambda g: g.area)
            outer = Polygon(grown.exterior)
            kept = []
            for ring in grown.interiors:
                o = Polygon(ring); w = neck_width(o)
                (kept if w is not None and w >= om-.01 else filled).append(o)
            openings = kept
    outer = opening_of(outer, .01)
    openings = [opening_of(o, .01) for o in openings if not opening_of(o, .01).is_empty]
    return outer, openings, filled, dropped


def sky_sampler(backdrop, sigma_mm=15.0):
    """Colour of the back panel behind a one-piece plate with its detail
    removed: the extended sky raster Gaussian-blurred over `sigma_mm` (waves
    and stars averaged into the gradient) plus the moon/cloud layer as one
    uniform pale colour through its own blurred mask, so the printed gaps of
    the tree and doors take the local sky or moon tone without any wave line,
    cloud edge or crater being baked into the plate."""
    def decode(r):
        return np.asarray(Image.open(io.BytesIO(base64.b64decode(r['ink'].split('base64,')[1].split('"')[0]))).convert('RGBA')).astype('float32')
    sky = decode(backdrop['rasters'][0])[..., :3]; ov = backdrop['rasters'][1]
    moon = decode(ov)
    h, w = sky.shape[:2]; sx, sy = w/backdrop['w'], h/backdrop['h']
    rgb = cv2.GaussianBlur(sky, (0, 0), sigmaX=sigma_mm/sx, sigmaY=sigma_mm/sy)
    solid = moon[..., 3] > 200
    colour = moon[..., :3][solid].mean(0) if solid.any() else np.array([240., 225., 235.])
    mh, mw = moon.shape[:2]
    ox, oy = int(round(ov['dx']*sx)), int(round(ov['dy']*sy))
    mask = np.zeros((h, w), 'float32')
    x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(w, ox+mw), min(h, oy+mh)
    mask[y0:y1, x0:x1] = (moon[y0-oy:y1-oy, x0-ox:x1-ox, 3] > 128).astype('float32')
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=(sigma_mm/2)/sx, sigmaY=(sigma_mm/2)/sy)[..., None]
    rgb = rgb*(1-mask)+colour*mask
    left = 140.0-backdrop['w']/2; top = CFG['clear_border_mm']+backdrop['h']
    def sample(scene_x, scene_z):
        mx = ((scene_x-left)/backdrop['w']*(w-1)).astype('float32')
        my = ((top-scene_z)/backdrop['h']*(h-1)).astype('float32')
        return cv2.remap(rgb, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    sample.sigma_mm = sigma_mm
    sample.moon_colour = [int(v) for v in colour]
    return sample


def one_piece_print(asset, shape, sampler):
    """Print raster of a one-piece plate: the original pixels inside the body
    (0.6 mm from every cut edge and opening, outside the riser), and every
    enclosed gap - everything inside the piece that is not printed art, not
    the 1.0 mm clear band along a cut edge and not a clear connector halo -
    printed with the sampled sky colour up to the art. Nothing prints outside
    the body, so twigs and petals the cut skeleton dropped never print inside
    an opening, and the outer rim stays clear (no pale halo)."""
    H, W = asset['canvas_px']
    s = asset['w']/W
    band = shape['body'].buffer(-CFG['clear_border_mm'], quad_segs=16)
    halos = [c.difference(asset['art']) for c in asset['connectors']]
    fill = band.difference(unary_union([asset['art']]+halos+[o.buffer(CFG['clear_border_mm'], quad_segs=16) for o in shape['openings']]+shape['risers']))
    fill = fill.intersection(box(0, 0, asset['w'], asset['h']))
    bodymask = shape['body'].buffer(-.6, quad_segs=16)
    for o in shape['openings']: bodymask = bodymask.difference(o.buffer(.6, quad_segs=16))
    for r in shape['risers']: bodymask = bodymask.difference(r)
    def raster(poly):
        m = np.zeros((H, W), 'uint8')
        for g in (poly.geoms if poly.geom_type != 'Polygon' else [poly]):
            if g.geom_type == 'Polygon' and not g.is_empty:
                cv2.fillPoly(m, [np.round(np.asarray(g.exterior.coords)/s).astype('int32')], 1)
                for ring in g.interiors: cv2.fillPoly(m, [np.round(np.asarray(ring.coords)/s).astype('int32')], 0)
        return m > 0
    fm, bm = raster(fill), raster(bodymask)
    cols, rows = np.meshgrid(np.arange(W), np.arange(H))
    sky = sampler(shape['scene_left']+cols*s, shape['shoulder']-rows*s)
    a = asset['rgba'].astype(np.float32); al = a[..., 3:4]/255.0
    out = a.copy()
    # Semi-transparent source pixels (soft petal and twig fringes) print only
    # inside the printed gaps, where they are composited; elsewhere they would
    # become translucent pale halos over the dark sky, so they stay clear.
    out[..., 3] = np.where(bm & ((a[..., 3] > 128) | fm), a[..., 3], 0)
    out[..., :3][fm] = a[..., :3][fm]*al[fm]+sky[fm]*(1-al[fm])
    out[..., 3][fm] = 255
    im = Image.fromarray(out.clip(0, 255).astype('uint8'), 'RGBA')
    raster_ = embed_canvas(im, asset['w'], asset['h'], asset['art'], dict(asset['raster_extra'],
        processing=asset['processing']+f'; print: original pixels inside the body 0.6 mm from every cut edge, every enclosed gap printed with the back panel tone (sky blurred over {sampler.sigma_mm} mm + uniform moon colour {sampler.moon_colour} through its blurred mask) sampled at the same scene position, up to the art, 1.0 mm clear band along the cut and riser left clear'))
    # The tree's own ink (original pixels) without the printed sky fill, at the
    # embedded resolution: the V10 trunk-base clearance to the serpent is judged
    # on this, not on the pale gap fill.
    art_alpha = np.where(fm, 0, out[..., 3]).astype('uint8')
    raster_['art_alpha'] = np.asarray(Image.fromarray(art_alpha).resize(tuple(raster_['resample_px']), Image.BILINEAR))
    return {'ink': raster_['ink'], 'rasters': [raster_], 'opaque_px': raster_['opaque_px'], 'fill_region': fill,
        'fill_px': int(fm.sum()), 'printed_sky_mm2': round(fill.area, 1)}


def load_tree(tree, spec):
    """The tree as ONE cut piece: skeleton + connectors as the cut silhouette,
    the complete tree printed, gaps printed with sky where not cut out."""
    cfg = tree.cfg
    kept, main_mask, frags, info = tree.skeleton()
    paths, path_recs = tree.geodesic(main_mask, frags)
    connectors = []
    for path in paths.values():
        pts = np.array(path, float)
        if len(pts) > 4:
            pts = np.stack([gaussian_filter1d(pts[:, 0], cfg['path_sigma_px'], mode='nearest'), gaussian_filter1d(pts[:, 1], cfg['path_sigma_px'], mode='nearest')], 1)
        line = LineString(pts*tree.s).simplify(cfg['path_simplify_mm'], preserve_topology=False)
        if len(line.coords) >= 2: connectors.append(line.buffer(cfg['connector_width_mm']/2, quad_segs=12))
        else: connectors.append(Point(line.coords[0]).buffer(cfg['connector_width_mm']/2, quad_segs=12))
    skeleton, _ = mask_polygons(kept, tree.s, cfg['contour_sigma_px'])
    outer, openings, filled, dropped = one_piece_body(skeleton, connectors, cfg)
    H, W = tree.H, tree.W; w, h = W*tree.s, H*tree.s
    ys, xs = np.nonzero(tree.opaque)
    info.update({'connectors': len(connectors), 'connector_width_mm': cfg['connector_width_mm'],
        'connector_twig_paths_mm': sorted((r['twig_path_mm'] for r in path_recs.values()), reverse=True),
        'connector_twig_path_total_mm': round(sum(r['twig_path_mm'] for r in path_recs.values()), 1),
        'openings': len(openings), 'openings_mm': [{'area_mm2': round(o.area, 1), 'min_width_mm': neck_width(o),
            'box_mm': [round(v, 1) for v in o.bounds]} for o in sorted(openings, key=lambda o: -o.area)],
        'enclosed_gaps_of_body': len(filled)+len(dropped), 'enclosed_gaps_area_mm2': round(sum(o.area for o in filled+dropped), 1),
        'gaps_too_narrow_to_cut': len(filled), 'gaps_dropped_for_neck': len(dropped),
        'minimum_feature_mm': neck_width(outer), 'outer_perimeter_mm': round(outer.length, 1),
        'canvas_mm': [round(w, 2), round(h, 2)], 'ink_box_mm': [round(xs.min()*tree.s, 2), round(ys.min()*tree.s, 2), round((xs.max()+1)*tree.s, 2), round((ys.max()+1)*tree.s, 2)],
        'art_area_mm2': round(skeleton.area, 1), 'body_area_mm2': round(outer.area, 1)})
    return {'id': spec['id'], 'src_name': '03_blossom_tree.png', 'w': w, 'h': h, 'ink': '',
        'art': skeleton, 'opaque_px': 0, 'tab_x_mm': tree.trunk_base_x(), 'body_override': outer,
        'openings': openings, 'one_piece': True, 'canvas_px': [H, W], 'rgba': tree.rgba, 'outer': outer, 'connectors': connectors,
        'processing': tree.processing+f"; V10 one-piece tree: the V8 cut skeleton (opaque mask opened {cfg['skeleton_open_mm']} mm at the {cfg['skeleton_ref_mm']} mm reference scale, so the same twigs and petals V8 cut are cut) scaled to {cfg['art_height_mm']} mm art, main skeleton + every detached cluster of at least {cfg['fragment_min_mm2']} mm2 kept, {len(connectors)} twig connectors {cfg['connector_width_mm']} mm wide, rim {cfg['rim_mm']} mm closed {cfg['closing_mm']} mm at the new size, {len(openings)} cut-out openings, narrow gaps printed with sky",
        'split_info': info,
        'raster_extra': {'dx': 0.0, 'dy': 0.0, 'anchor': 'base', 'source_bbox_px': tree.bbox, 'source_file': '03_blossom_tree.png',
            'art_height_mm_config': CFG['tree_one_piece']['art_height_mm'], 'rotate_deg': CFG['tree_one_piece']['rotate_deg']}}


def load_door(spec):
    """One lattice doorway as its own cut piece (V8 asset, V9 height)."""
    cfg = CFG['tree_one_piece']['doors']
    im, bbox, ref_h, processing = source_pixels(spec)
    a = np.asarray(im); s = spec['art_height_mm']/ref_h
    op = a[..., 3] > 128
    H, W = op.shape
    silhouette, holes = mask_polygons(op, s, cfg['contour_sigma_px'])
    assert silhouette.geom_type == 'Polygon', ('door silhouette disconnected', len(silhouette.geoms))
    outer, openings, filled, dropped = one_piece_body(silhouette, [], cfg)
    info = {'lattice_holes_in_source': len(holes), 'openings': len(openings),
        'openings_mm': [{'area_mm2': round(o.area, 1), 'min_width_mm': neck_width(o), 'box_mm': [round(v, 1) for v in o.bounds]} for o in sorted(openings, key=lambda o: -o.area)],
        'enclosed_gaps_of_body': len(filled)+len(dropped), 'minimum_feature_mm': neck_width(outer), 'outer_perimeter_mm': round(outer.length, 1),
        'canvas_mm': [round(W*s, 2), round(H*s, 2)], 'art_area_mm2': round(silhouette.area, 1), 'body_area_mm2': round(outer.area, 1)}
    return {'id': spec['id'], 'src_name': '06_lattice_doors.png', 'w': W*s, 'h': H*s, 'ink': '',
        'art': silhouette, 'opaque_px': 0, 'tab_x_mm': W*s/2, 'body_override': outer,
        'openings': openings, 'one_piece': True, 'canvas_px': [H, W], 'rgba': a, 'outer': outer, 'connectors': [],
        'processing': processing+f"; V9 door piece: silhouette buffered {cfg['rim_mm']} mm closed {cfg['closing_mm']} mm, thin features widened to {cfg['min_feature_mm']} mm, {len(openings)} lattice openings cut, the other lattice gaps printed with sky; art {spec['art_height_mm']} mm (V8 85 mm) so the cut top stands level with the back panel",
        'split_info': info,
        'raster_extra': {'dx': 0.0, 'dy': 0.0, 'anchor': 'base', 'source_bbox_px': bbox, 'source_file': '06_lattice_doors.png',
            'art_height_mm_config': spec['art_height_mm'], 'rotate_deg': 0}}


def embed_canvas(im, w, h, art, extra):
    """Embed a native-pixel canvas (the one-piece tree or a door) at print scale."""
    pw, ph = im.size
    tw, th = max(1, min(round(w*PPI), pw)), max(1, min(round(h*PPI), ph))
    res = im.resize((tw, th), Image.LANCZOS)
    ra = np.asarray(res); solid = ra[:, :, 3] > 128
    buf = io.BytesIO(); res.save(buf, 'PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    ink = (f'<image x="0" y="0" width="{w:.6f}" height="{h:.6f}" '
           f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    source = SRC/extra['source_file']
    return dict({'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_px': [pw, ph], 'source_bbox_px': None, 'resample_px': [tw, th],
        'w': w, 'h': h, 'ink': ink, 'art': art, 'canvas': True,
        'clip': None, 'crop_below_fraction': None,
        'opaque_px': int((ra[:, :, 3] > 8).sum()),
        'res_alpha': ra[:, :, 3].copy(), 'mean_rgb': ra[solid][:, :3].mean(0) if solid.any() else np.zeros(3),
        'native_cap': bool(tw < pw-1 or (tw == pw and th == ph and round(w*PPI) > pw)),
        'effective_ppi': round(tw/(w/25.4))}, **extra)


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
        pinch_top = min(y for w, y, _ in samples if w < LOAD_PATH_FLOOR_MM)
        rw = LOAD_PATH_FLOOR_MM+.25
        if worst[2]:
            load = max(worst[2], key=lambda p: p.length)
            mx = (load.bounds[0]+load.bounds[2])/2
        else:
            mx = cx   # V3 fix: empty window between the legs -> riser on the tab axis
        mx = min(max(mx, cx-half+rw/2), cx+half-rw/2)   # V3 fix: keep the riser inside the tab window
        top = pinch_top-.25
        boxes[cx] = box(mx-rw/2, top, mx+rw/2, shoulder)
        recs[round(cx, 2)] = {'riser_width_mm': round(rw, 2),
            'riser_top_above_slot_mm': round(shoulder-top, 2),
            'worst_section_before_mm': round(worst[0], 2),
            'worst_at_above_slot_mm': round(shoulder-worst[1], 2),
            'riser_axis': 'tab axis (window empty between the legs)' if not worst[2] else 'narrowest ligament'}
        print(f"bud guard: {a_id} cx={cx:.1f} worst {worst[0]:.2f} mm at "
              f"{shoulder-worst[1]:.2f} mm above slot -> riser {rw:.2f} mm wide "
              f"to {shoulder-top:.2f} mm", flush=True)
    return list(boxes.values()), recs


def standee(a, base_thickness, mounts, plinth_rise=8, simplify_tol=.015, border=None):
    border = CFG['clear_border_mm'] if border is None else border; art = a['art']
    if a.get('body_override') is not None:
        body = a['body_override']
        shoulder = a['shoulder_override'] if a.get('shoulder_override') is not None else art.bounds[3]+border
    else:
        body = art.buffer(border, quad_segs=28)
        if body.geom_type != 'Polygon': body = concave_hull(body, ratio=.5)
        body = Polygon(body.exterior)
        shoulder = art.bounds[3]+border
    depth = base_thickness-CFG['tab_bottom_clearance_mm']
    mean_x = sum(m[0] for m in mounts)/len(mounts)
    half = CFG['tab_width_mm']/2
    tab_x = a['tab_x_mm'] if a.get('tab_x_mm') is not None else a['w']/2
    tabs = []; bridges = []; tab_cx = []
    for mx, my in mounts:
        cx = (mx-mean_x)+tab_x
        tab_cx.append(cx)
        tabs.append(tab_shape(cx, shoulder, depth))
        if plinth_rise > 0:
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
    # Cut-out openings: inside the body, clear of the risers and tabs; any
    # opening a riser would cross stays solid (printed) instead.
    openings = []
    for o in a.get('openings', []):
        if any(o.intersects(g) for g in guard) or not shape.contains(o) or o.intersects(art):
            continue
        assert shape.exterior.distance(o) >= 0 and min(r.distance(o) for r in guard) >= 0
        openings.append(o)
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
        'mount_mean_x': mean_x, 'clearance': clearance, 'border': border, 'bud_guard': guard_recs,
        'tab_x_mm': tab_x, 'body': body, 'openings': openings, 'risers': list(guard)}


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
    mind = None; worst = None; pairs = []
    for my, members in sorted(rows.items()):
        for i in range(len(members)):
            for j in range(i+1, len(members)):
                d = members[i][1].distance(members[j][1])
                pairs.append({'row_mm': my, 'pair': [members[i][0], members[j][0]], 'standing_cut_distance_mm': round(d, 2)})
                if mind is None or d < mind: mind, worst = d, (members[i][0], members[j][0])
    for pid, (g, my) in st.items():
        b = g.bounds
        assert b[0] >= -12 and b[2] <= CFG['base_mm'][0]+12, (pid, b[0], b[2])
    assert mind is None or mind >= 2, (worst, mind)
    over = {pid: round(max(0, -g.bounds[0])+max(0, g.bounds[2]-CFG['base_mm'][0]), 2)
            for pid, (g, my) in st.items() if g.bounds[0] < 0 or g.bounds[2] > CFG['base_mm'][0]}
    return (round(mind, 2) if mind is not None else None), worst, over, sorted(pairs, key=lambda r: r['standing_cut_distance_mm'])


def tree_clearance(shapes, assets):
    """V10: the tree stands between the left door and Len with its trunk base
    left of the serpent, grown until its cut top meets the shared door/backdrop
    top line. Hard checks: the cut top does not exceed that line; the tree
    shares its row with no other plate and keeps at least 2 mm from every
    same-row standing cut (plates collide only within one depth row); the tab
    axis is left of the serpent's printed ink near the base line and the
    tree's own PRINTED ink there (not the pale gap fill) keeps at least
    TRUNK_CLEARANCE_MM from it; the tree's cut below 8 mm (the trunk base)
    keeps at least that clearance from the left door's cut so the trunk stands
    visibly in the gap. Reported, not asserted: the tree's cut crossing the
    left door's zone above the trunk, Len's cut, the serpent's cut and the
    right door's cut in the front view - the serpent and Len stand in front of
    the tree, the left door in front of its upper-left blossoms."""
    st = standing_cuts(shapes)
    tree = st['tree'][0].intersection(box(-300, 0, 600, 300))
    line = round(max(st[d][0].bounds[3] for d in ('backdrop', 'door_left', 'door_right')), 2)
    out = {'shared_door_backdrop_cut_top_above_base_top_mm': line,
        'tree_cut_top_above_base_top_mm': round(tree.bounds[3], 3),
        'tree_minus_shared_top_line_mm': round(tree.bounds[3]-line, 3)}
    assert tree.bounds[3] <= line+1e-6, ('tree cut top above the shared door/backdrop top line', round(tree.bounds[3], 3), line)
    same_row = sorted(pid for pid, (g, my) in st.items() if my == st['tree'][1] and pid != 'tree')
    out['tree_row_mm'] = st['tree'][1]; out['same_row_plates'] = same_row
    for pid in same_row:
        d = tree.distance(st[pid][0].intersection(box(-300, 0, 600, 300)))
        out[f'same_row_distance_to_{pid}_mm'] = round(d, 2)
        assert d >= 2, ('tree collides with a same-row plate', pid, round(d, 3))
    front = {}
    for pid in ('door_left', 'door_right', 'character', 'snake'):
        g = st[pid][0].intersection(box(-300, 0, 600, 300))
        ov = tree.intersection(g)
        rec = {'row_mm': st[pid][1], 'cut_overlap_mm2': round(ov.area, 1)}
        if tree.intersects(g):
            rec['x_overlap_mm'] = [round(max(tree.bounds[0], g.bounds[0]), 2), round(min(tree.bounds[2], g.bounds[2]), 2)]
        front[pid] = rec
    out['front_view_overlap_with_other_rows'] = front
    out['tree_cut_pct_behind_the_serpent'] = round(100*front['snake']['cut_overlap_mm2']/tree.area, 1)
    out['tree_cut_pct_behind_len'] = round(100*front['character']['cut_overlap_mm2']/tree.area, 1)
    geo = _scene_geometry(assets, shapes)
    # The trunk base: the tree's own ink (not the pale gap fill) within 8 mm
    # of the tab axis on the serpent side, near the base line (z <= 8 mm).
    res = .25
    gt, gs = geo['tree'], geo['snake']
    tree_ink = _ink_mask(gt['art']['rasters'][0], gt['left'], gt['shape']['shoulder'], res, key='art_alpha')
    snake_ink = _ink_mask(gs['art']['rasters'][0], gs['left'], gs['shape']['shoulder'], res)
    rows = slice(int(round((100-8)/res)), tree_ink.shape[0]); cols = slice(0, int(round((gt['mx']+8)/res))+1)
    tree_base = np.zeros_like(tree_ink); tree_base[rows, cols] = tree_ink[rows, cols]
    far = cv2.distanceTransform((~snake_ink[rows]).astype('uint8'), cv2.DIST_L2, 5)*res
    d = float(far[tree_base[rows]].min()) if tree_base.any() else None
    out['printed_trunk_base_to_serpent_ink_near_the_base_line_mm'] = round(d, 2) if d is not None else None
    assert d is not None and d >= TRUNK_CLEARANCE_MM, ('trunk base ink nears the serpent ink', d)
    snake_cols = np.nonzero(snake_ink[rows].any(0))[0]
    snake_left = float(snake_cols.min()*res)
    out['trunk_base_x_mm'] = round(gt['mx'], 2)
    out['serpent_printed_ink_left_edge_near_the_base_line_mm'] = round(snake_left, 2)
    assert gt['mx'] < snake_left, ('trunk base not left of the serpent', gt['mx'], snake_left)
    low = box(-300, 0, 600, 8)
    dd = tree.intersection(low).distance(st['door_left'][0].intersection(low))
    out['trunk_base_region_z8_to_left_door_cut_mm'] = round(dd, 2)
    assert dd >= TRUNK_CLEARANCE_MM, ('trunk base region nears the left door cut', dd)
    base_line = box(-300, 0, 600, 2.0)
    cross = tree.intersection(base_line).intersection(st['snake'][0].intersection(base_line))
    out['clear_rims_crossing_the_serpent_cut_at_the_base_line_mm2'] = round(cross.area, 2)
    return out


def front_coverage(shapes):
    """Front-view occlusion sweep, reported (not asserted) for ORIGIN.

    ORIGIN is a deliberately stacked centre scene (blossom plates behind the
    tree, tree across the moon, serpent behind the character): polygon
    occlusion is by design and overstates visual blocking. The numbers are
    recorded for review; composition acceptance is the vision-checked
    assembly preview against the supplied concept art. All structural
    checks (row clearance, overhang, load path, gaps, rims, minimum feature)
    stay hard.
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
    slot_gaps = []
    for i in range(len(slots)):
        for j in range(i+1, len(slots)):
            gap = slots[i][3].distance(slots[j][3])
            slot_gaps.append((round(gap, 3), slots[i][0], slots[j][0]))
            assert gap >= 2.99, (slots[i][:3], slots[j][:3], gap)
    items = []
    for p in CFG['pieces']:
        a = assets[p['id']]; s = shapes[p['id']]
        poly = s['poly']; bx, by = poly.bounds[0], poly.bounds[1]
        x, y = p['board_xy_mm']; tx, ty = x-bx, y-by
        items.append({'name': p['id'], 'poly': affinity.translate(poly, tx, ty),
                      'tx': tx, 'ty': ty, 'ink': a['ink'], 'holes': [affinity.translate(o, tx, ty) for o in s['openings']],
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
    return items, gap, min(slot_gaps)


def make_board(assets, shapes, preset, folder):
    items, gap, slot_gap = positioned(assets, shapes, preset)
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
    bd = assets['backdrop']; ch = assets['character']; tr = assets['tree']; ti = tr['split_info']
    dl, dr = assets['door_left'], assets['door_right']
    nop = sum(len(shapes[p['id']]['openings']) for p in CFG['pieces'])
    labels = (svg_text(13, 396, f'LEN DIORAMA ORIGIN V10 / {preset["name"]} / {PIECE_COUNT} PIECES', 4.0)
        + svg_text(13, 403, f'BASE / {CFG["base_mm"][0]:.0f} x {CFG["base_mm"][1]:.1f} cut / wave art {assets["base"]["w"]:.0f} x {assets["base"]["h"]:.1f} centred + 2.5 clear rim', 3.1)
        + svg_text(13, 410, f'{SLOT_COUNT} SLOTS 18.8 x {preset["slot_width_mm"]:.2f} / rows y {depths} (backdrop: 3 tabs) / {nop} cut-out openings', 3.1)
        + svg_text(13, 417, f'BACKDROP {shapes["backdrop"]["poly"].bounds[2]-shapes["backdrop"]["poly"].bounds[0]:.0f}x{bd["h"]:.0f} (sky extended into the door zones + moon/clouds printed on it)  TREE one piece {tr["w"]:.0f}x{tr["h"]:.0f} canvas ({CFG["tree_one_piece"]["art_height_mm"]:.1f} mm art = V8 88 mm restored and grown to the door/backdrop top line, V8 skeleton at the {CFG["tree_one_piece"]["skeleton_ref_mm"]:g} mm reference, rotated {CFG["tree_one_piece"]["rotate_deg"]:g} deg clockwise, wood + blossoms printed, {ti["openings"]} openings, {ti["connectors"]} connectors {ti["connector_width_mm"]} mm, {tr["rasters"][0]["effective_ppi"]} ppi)  DOORS L/R {dl["w"]:.1f}x{dl["h"]:.1f} / {dr["w"]:.1f}x{dr["h"]:.1f} ({dl["rasters"][0]["art_height_mm_config"]:.2f} mm art, cut tops level with the back panel, lattice openings cut)  SNAKE {assets["snake"]["w"]:.0f}x{assets["snake"]["h"]:.0f}  CHARACTER whole {ch["w"]:.0f}x{ch["h"]:.1f} ({ch["rasters"][0]["art_height_mm_config"]:.0f} mm art, no crop, clear riser in the tab window)  / clear rim {CFG["clear_border_mm"]:.1f}', 3.0))
    preview = write_svg(folder/'preview/flat_layout.svg', w, h,
        f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'+ink+reference+cut_layer(items, .17)+labels)
    render(preview, folder/'preview/flat_layout.png', 2.2)
    preview.unlink()
    return items, gap, slot_gap


def assembly(assets, shapes, preset, folder):
    """Axonometric assembly preview from the real cut polygons; illustrative.

    Clear acrylic is drawn see-through on the concept's dark mauve ground:
    plate bodies get no fill and a single thin lit-edge stroke stands for the
    cut edge (V1 filled every plate near-white and drew each one twice, which
    produced the white halos and the double outlines; on a light ground even
    an unfilled plate reads as white). Tabs are clipped at the shoulder line
    because they sit inside the base slots. Cut-out openings (the V9 tree;
    the doors' lattice holes are all printed) are drawn with the same lit edge
    so the sky shows through them. Plates are drawn back to front by depth
    row: backdrop, doors, tree, serpent, whole seated character.
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
    for spec in sorted(CFG['pieces'], key=lambda q: -q['mounts_mm'][0][1]):
        pid = spec['id']
        mx = sum(m[0] for m in spec['mounts_mm'])/len(spec['mounts_mm'])
        my = spec['mounts_mm'][0][1]
        a = assets[pid]; s = shapes[pid]
        X = ox+mx+dx*my-s['tab_x_mm']; Y = oy+dy*my-bt-s['shoulder']
        body = s['poly'].intersection(box(-200, -200, 600, s['shoulder']))
        if body.geom_type != 'Polygon': body = max(body.geoms, key=lambda g: g.area)
        edges = path(poly_path(body), 'none', EDGE, EDGE_W)+''.join(path(poly_path(o), 'none', EDGE, EDGE_W) for o in s['openings'])
        parts.append(f'<g transform="translate({X:.4f} {Y:.4f})">' + edges + a['ink'] + '</g>')
    # Front-view inset (V9): the owner's V9/V10 requests are front-view
    # properties (door tops level with the back panel, the tree between the
    # left door and Len and now as tall as both); the axonometric parallax
    # above shifts deeper plates to the right and would misreport them.
    # Printed rasters back to front at their true scene positions, cut edges
    # as thin lit lines.
    ZT, sc = 100.0, .33
    inset = [f'<rect x="248" y="8" width="{280*sc+4:.2f}" height="{100*sc+4:.2f}" fill="#4a3d6b"/>',
             f'<g transform="translate(250 10) scale({sc})">',
             f'<rect width="280" height="{ZT}" fill="#3b3058"/>',
             f'<g transform="translate({inset_x:.6f} {ZT+inset_y+b["h"]:.6f}) scale(1 -1)">{b["ink"]}</g>']
    for spec in sorted(CFG['pieces'], key=lambda q: -q['mounts_mm'][0][1]):
        pid = spec['id']; a = assets[pid]; s = shapes[pid]
        mx = sum(m[0] for m in spec['mounts_mm'])/len(spec['mounts_mm'])
        left = mx-(s['tab_x_mm'] if s['tab_x_mm'] is not None else a['w']/2)
        inset.append(f'<g transform="translate({left:.4f} {ZT-s["shoulder"]:.4f})">{a["ink"]}</g>')
    inset.append(f'<g transform="translate(0 {ZT}) scale(1 -1)">')
    for pid, (g, my) in standing_cuts(shapes).items():
        body = g.intersection(box(-300, 0, 600, 300))
        inset.append(path(poly_path(body), 'none', EDGE, EDGE_W/sc))
    inset.append(f'<line x1="0" y1="92" x2="280" y2="92" stroke="#ffffff" stroke-width="{.5/sc:.3f}"/></g></g>')
    parts.extend(inset)
    parts.append(svg_text(13, 15, 'LEN DIORAMA ORIGIN V10', 5, TEXT))
    parts.append(svg_text(13, 23, f'base {bw:.0f} x {bh:.1f} mm / {PIECE_COUNT} pieces / clear rim {CFG["clear_border_mm"]:.1f} mm on every plate / clear acrylic drawn see-through on a dark ground', 3.4))
    parts.append(svg_text(250, 46, 'front view: back panel, doors and the tree top out together at 95.0 mm assembled (white line = cut tops, 92.0 mm above the base)', 2.4, TEXT))
    parts.append(svg_text(250, 49.5, f'tree {CFG["tree_one_piece"]["art_height_mm"]:.1f} mm art (V8 88 mm restored, grown to the line), trunk at x 96 left of the serpent, canopy behind the serpent and Len\'s left edge', 2.4, TEXT))
    ti = assets['tree']['split_info']; nopen = sum(len(shapes[p['id']]['openings']) for p in CFG['pieces'])
    parts.append(svg_text(13, 246, f'V10 / {preset["name"]} / back panel: sky + moon and clouds (doors no longer printed on it) / tree as ONE cut piece (trunk, branches and blossoms printed on it, {ti["openings"]} cut-out openings, {ti["connectors"]} twig connectors {ti["connector_width_mm"]} mm wide, {CFG["tree_one_piece"]["art_height_mm"]:.1f} mm art) grown to the door/backdrop top line with its trunk base in the gap between the left door and Len, behind the serpent / two lattice door plates as tall as the back panel at the sides in front of it', 3.1))
    parts.append(svg_text(13, 253, f'/ serpent plate / whole Len plate, feet on the base line, carried by a clear riser in the tab window / {nopen} cut-out openings in total, {CUT_PATH_COUNT} closed cut paths / 7 pieces, {SLOT_COUNT} slots', 3.1))
    svg = write_svg(folder/'preview/assembly.svg', 400, 260, ''.join(parts))
    render(svg, folder/'preview/assembly.png', 2.7)
    svg.unlink()


def _scene_geometry(assets, shapes):
    """Scene x from the base's left edge, scene y = height above the base top,
    for every plate as it stands (art bbox centred on its mount x)."""
    out = {}
    for spec in CFG['pieces']:
        a = assets[spec['id']]; s = shapes[spec['id']]
        mx = sum(m[0] for m in spec['mounts_mm'])/len(spec['mounts_mm']); my = spec['mounts_mm'][0][1]
        tabx = s['tab_x_mm'] if s.get('tab_x_mm') is not None else a['w']/2
        out[spec['id']] = {'art': a, 'shape': s, 'mx': mx, 'my': my, 'tabx': tabx,
            'left': mx-tabx, 'right': mx-tabx+a['w'], 'top': s['shoulder'], 'row': my}
    return out


def _visible_pct(raster, x0, ytop, sc, front_cuts, ra=None):
    """Share of a raster's opaque pixels not hidden by the standing cuts of the
    plates in front of it (front view). x0/ytop: raster top-left in scene mm
    (y up from the base top), sc: mm per pixel."""
    ra = (raster['res_alpha'] > 128) if ra is None else ra
    h, w = ra.shape
    vis = ra.copy()
    for g in front_cuts:
        minx, miny, maxx, maxy = g.bounds
        for yy in range(h):
            z = ytop-(yy+.5)*sc
            if z < miny or z > maxy: continue
            seg = g.intersection(LineString([(x0, z), (x0+w*sc, z)]))
            if seg.is_empty: continue
            parts = list(seg.geoms) if seg.geom_type == 'MultiLineString' else [seg]
            for part in parts:
                xs = [p[0] for p in part.coords]; i0 = max(0, int((min(xs)-x0)/sc)); i1 = min(w, int((max(xs)-x0)/sc)+1)
                vis[yy, i0:i1] = False
    total = int(ra.sum()); seen = int(vis.sum())
    return round(100*seen/total, 1) if total else None, vis


def _ink_mask(raster, x0, ztop, res=.25, key='res_alpha'):
    """Printed pixels of one raster as a scene grid (x from the base's left
    edge, z up from the base top) at `res` mm per cell; the raster is
    nearest-neighbour resampled from its own pixel size to the grid."""
    ra = (raster[key] > 128).astype('uint8')
    h, w = ra.shape; sc = raster['h']/h
    nx = int(math.ceil(CFG['base_mm'][0]/res))+1; nz = int(math.ceil(100/res))+1
    m = np.zeros((nz, nx), bool)
    ix0 = int(round(x0/res)); iz0 = int(round((100-ztop)/res))
    tw, th = max(1, int(round(w*sc/res))), max(1, int(round(h*sc/res)))
    up = cv2.resize(ra, (tw, th), interpolation=cv2.INTER_NEAREST) > 0
    j0 = max(0, iz0); j1 = min(nz, iz0+th); i0 = max(0, ix0); i1 = min(nx, ix0+tw)
    if j1 > j0 and i1 > i0:
        m[j0:j1, i0:i1] = up[j0-iz0:j1-iz0, i0-ix0:i1-ix0]
    return m


def composition_report(assets, shapes, tree_info, tree_clear):
    """Measure the V10 scene from the real rasters and cut polygons: where every
    plate stands and how tall its cut really is (door and tree tops against the
    back panel), the one-piece tree's position, its front-view overlaps with the
    plates on other rows and the trunk-base clearances, its openings,
    connectors and printed gaps, the moon's visibility, and how the character
    meets the base line."""
    geo = _scene_geometry(assets, shapes)
    out = {'scene_width_mm': CFG['base_mm'][0], 'row_order_front_to_back': [p['id'] for p in sorted(CFG['pieces'], key=lambda q: q['mounts_mm'][0][1])], 'pieces': {}}
    for pid, g in geo.items():
        a = g['art']; s = g['shape']
        cut_top = g['top']-s['poly'].bounds[1]
        out['pieces'][pid] = {'art_mm': [round(a['w'], 2), round(a['h'], 2)], 'plate_cut_bounds_mm': [round(x, 2) for x in s['poly'].bounds],
            'art_center_x_mm': round(g['mx'], 2), 'art_span_x_mm': [round(g['left'], 2), round(g['right'], 2)],
            'depth_row_mm': g['my'], 'cut_top_above_base_top_mm': round(cut_top, 2),
            'assembled_height_mm': round(CFG['presets'][0]['base_thickness_mm']+cut_top, 2), 'art_top_above_base_top_mm': round(g['top'], 2),
            'effective_ppi': [r['effective_ppi'] for r in a['rasters']], 'clear_border_mm': s['border'],
            'tab_cx_mm': [round(g['mx']-g['tabx']+cx, 2) for cx in s['tab_cx']],
            'minimum_art_to_cut_mm': round(s['clearance'], 3), 'minimum_feature_mm': neck_width(s['poly']),
            'cut_out_openings': len(s['openings'])}
        if s['openings']:
            holed = Polygon(s['poly'].exterior, [o.exterior for o in s['openings']])
            out['pieces'][pid]['minimum_feature_with_openings_mm'] = neck_width(holed)
    standing = standing_cuts(shapes)
    bd = assets['backdrop']; sky = bd['rasters'][0]; comp = out['pieces']['backdrop']
    out['height_match'] = {'backdrop_cut_top_above_base_top_mm': comp['cut_top_above_base_top_mm'],
        'door_left_cut_top_above_base_top_mm': out['pieces']['door_left']['cut_top_above_base_top_mm'],
        'door_right_cut_top_above_base_top_mm': out['pieces']['door_right']['cut_top_above_base_top_mm'],
        'door_minus_backdrop_mm': {d: round(out['pieces'][d]['cut_top_above_base_top_mm']-comp['cut_top_above_base_top_mm'], 3) for d in ('door_left', 'door_right')},
        'backdrop_assembled_height_mm': comp['assembled_height_mm'],
        'tree_cut_top_above_base_top_mm': out['pieces']['tree']['cut_top_above_base_top_mm'],
        'tree_assembled_height_mm': out['pieces']['tree']['assembled_height_mm'],
        'tree_minus_backdrop_mm': round(out['pieces']['tree']['cut_top_above_base_top_mm']-comp['cut_top_above_base_top_mm'], 3),
        'tree_height_rule': CFG['tree_one_piece']['height_rule'],
        'rule': 'V10: both door plates stand as tall as the back panel (cut tops aligned when assembled) and the tree is grown until its cut top stands on the same line without exceeding it. Heights are real cut tops above the base top plus the 3 mm base; the V8 report counted art top + one rim (94.0 / 88.8) and omitted the 1.0 mm rim under every plate.'}
    out['tree_piece_clearance_mm'] = dict(tree_clear, rule=CFG['tree_one_piece']['clearance_rule'])
    comp['sky_mm'] = [round(sky['w'], 2), round(sky['h'], 2)]
    comp['sky_span_x_mm'] = [round(geo['backdrop']['left'], 2), round(geo['backdrop']['right'], 2)]
    comp['sky_extension'] = {'rule': CFG['tree_one_piece'].get('sky_extension_rule', 'see pieces.backdrop.extend_sky_mm'), 'processing': sky['processing']}
    sky_left = geo['backdrop']['mx']-sky['w']/2
    cuts_in_front = lambda row: [g for pid, (g, my) in standing.items() if my < row]
    ink_masks = {}
    for pid, g in geo.items():
        s = g['shape']; a = g['art']
        ink_masks[pid] = _ink_mask(a['rasters'][0], g['left'], s['shoulder'])
    def ink_in_front(row):
        parts = [ink_masks[pid] for pid, g in geo.items() if g['my'] < row]
        return np.any(parts, axis=0) if parts else None
    def visible_ink(pid):
        m = ink_masks[pid]; front = ink_in_front(geo[pid]['my'])
        total = int(m.sum())
        if not total: return None
        seen = int((m & ~front).sum()) if front is not None else total
        return round(100*seen/total, 1)
    def visible(raster, row, x0, ytop):
        sc = raster['h']/raster['res_alpha'].shape[0]
        return _visible_pct(raster, x0, ytop, sc, cuts_in_front(row))
    moon = next(r for r in bd['rasters'] if r['file'] == '04_moon_clouds.png')
    al = (moon['res_alpha'] > 128).astype('uint8')
    dt = cv2.distanceTransform(al, cv2.DIST_L2, 5)
    cy, cx = divmod(int(dt.argmax()), al.shape[1]); radius = float(dt.max())
    scm = moon['h']/al.shape[0]
    disc_x = sky_left+moon['dx']+cx*scm; disc_z = sky['h']-moon['dy']-cy*scm
    comp['moon_disc'] = {'center_x_mm': round(disc_x, 2), 'center_y_above_base_mm': round(disc_z, 2),
        'diameter_mm': round(2*radius*scm, 2), 'offset_from_scene_axis_x140_mm': round(disc_x-140, 2)}
    yy, xx = np.mgrid[0:al.shape[0], 0:al.shape[1]]
    disc = ((xx-cx)*scm)**2+((yy-cy)*scm)**2 <= (radius*scm)**2
    _, vism = visible(moon, geo['backdrop']['my'], sky_left+moon['dx'], sky['h']-moon['dy'])
    comp['moon_disc']['visible_pct_in_front_view'] = round(100*int((disc & (vism > 0)).sum())/int(disc.sum()), 1)
    front = ink_in_front(geo['backdrop']['my'])
    res = .25; disc_cells = 0; disc_seen = 0; disc_open_tree = 0; disc_tree_body = 0
    tg = geo['tree']; ts = shapes['tree']; tr_left = tg['left']
    tree_body = affinity.scale(affinity.translate(ts['poly'], tr_left, 0), 1, -1, origin=(0, 0))
    tree_body = affinity.translate(tree_body, 0, ts['shoulder'])
    tree_holed = Polygon(tree_body.exterior, [affinity.translate(affinity.scale(affinity.translate(o, tr_left, 0), 1, -1, origin=(0, 0)), 0, ts['shoulder']).exterior for o in ts['openings']])
    for zz in np.arange(0, 100, res):
        for xx in np.arange(0, CFG['base_mm'][0], res):
            if (xx-disc_x)**2+(zz-disc_z)**2 <= (radius*scm)**2:
                disc_cells += 1
                pt = Point(xx+.125, zz+.125)
                if tree_holed.contains(pt):
                    disc_tree_body += 1
                    if not ink_masks['tree'][int(round((100-zz)/res)), int(round(xx/res))]: disc_open_tree += 1
                if not front[int(round((100-zz)/res)), int(round(xx/res))]: disc_seen += 1
    comp['moon_disc']['visible_pct_against_printed_ink_of_front_plates'] = round(100*disc_seen/disc_cells, 1) if disc_cells else None
    comp['moon_disc']['pct_behind_the_tree_plate_body'] = round(100*disc_tree_body/disc_cells, 1) if disc_cells else None
    comp['moon_disc']['pct_of_moon_under_the_tree_plate_s_printed_gaps'] = round(100*disc_open_tree/disc_cells, 1) if disc_cells else None
    comp['moon_disc']['note'] = 'visible_pct counts moon cells not covered by the PRINTED ink of the plates in front (the tree plate\'s clear connectors and rim do not count as ink); pct_behind_the_tree_plate_body counts cells covered by the tree plate material (rim, connectors, printed gaps); the moon shows through the tree where the plate is absent (cut-out openings and inlets), and the printed gaps carry the blurred local colour of the moon behind them'
    # One-piece tree.
    tr = assets['tree']; ra = tr['rasters'][0]; tinfo = dict(tr['split_info'])
    sc = ra['h']/ra['res_alpha'].shape[0]
    pct, _ = visible(ra, tg['my'], tg['left'], ts['shoulder'])
    ys, xs = np.nonzero(ra['res_alpha'] > 128)
    def scene_box(b):
        return {'x': [round(tr_left+b[0], 2), round(tr_left+b[2], 2)], 'z_above_base_top': [round(ts['shoulder']-b[3], 2), round(ts['shoulder']-b[1], 2)]}
    tinfo.update({'rotate_deg_clockwise': CFG['tree_one_piece']['rotate_deg'], 'configured_art_height_mm': CFG['tree_one_piece']['art_height_mm'],
        'scale_vs_v8_88mm': round(CFG['tree_one_piece']['art_height_mm']/88.0, 4), 'scale_vs_v9_56mm': round(CFG['tree_one_piece']['art_height_mm']/56.0, 4),
        'cut_top_vs_shared_door_backdrop_line_mm': tree_clear['tree_minus_shared_top_line_mm'],
        'shared_door_backdrop_cut_top_above_base_top_mm': tree_clear['shared_door_backdrop_cut_top_above_base_top_mm'],
        'front_view_overlap_with_other_rows': tree_clear['front_view_overlap_with_other_rows'],
        'unrotated_alpha_box_px': ra['source_bbox_px'][2:], 'source_density_ppi': round(ra['source_bbox_px'][3]/(CFG['tree_one_piece']['art_height_mm']/25.4)),
        'embedded_ppi': ra['effective_ppi'], 'resample_px': ra['resample_px'], 'native_cap': ra['native_cap'],
        'ink_box_mm': [round(xs.min()*sc, 2), round(ys.min()*sc, 2), round((xs.max()+1)*sc, 2), round((ys.max()+1)*sc, 2)],
        'ink_box_in_scene_mm': scene_box([xs.min()*sc, ys.min()*sc, (xs.max()+1)*sc, (ys.max()+1)*sc]),
        'plate_cut_bounds_mm': [round(v, 2) for v in ts['poly'].bounds], 'plate_cut_bounds_in_scene_mm': scene_box(ts['poly'].bounds),
        'openings_in_scene_mm': [dict(scene_box(o['box_mm']), area_mm2=o['area_mm2'], min_width_mm=o['min_width_mm']) for o in tinfo['openings_mm']],
        'openings_total_area_mm2': round(sum(o['area_mm2'] for o in tinfo['openings_mm']), 1),
        'minimum_art_to_cut_mm': round(ts['clearance'], 3), 'minimum_feature_mm': neck_width(ts['poly']),
        'minimum_feature_with_openings_mm': neck_width(Polygon(ts['poly'].exterior, [o.exterior for o in ts['openings']])) if ts['openings'] else None,
        'tab_x_scene_mm': round(tg['mx']-tg['tabx']+ts['tab_cx'][0], 2), 'depth_row_mm': tg['my'],
        'cut_top_above_base_top_mm': out['pieces']['tree']['cut_top_above_base_top_mm'], 'assembled_height_mm': out['pieces']['tree']['assembled_height_mm'],
        'standing_cut_bounds_in_scene_mm': {'x': [round(tr_left+ts['poly'].bounds[0], 2), round(tr_left+ts['poly'].bounds[2], 2)], 'z_above_base_top': [round(ts['shoulder']-ts['poly'].bounds[3], 2), round(ts['shoulder']-ts['poly'].bounds[1], 2)]},
        'clearance_to_door_and_character_mm': tree_clear,
        'visible_pct_in_front_view_not_hidden_by_front_plates': pct,
        'visible_pct_of_printed_ink_not_hidden_by_printed_ink_of_front_plates': visible_ink('tree'),
        'bud_guard_riser': ts['bud_guard'], 'printed_sky_fill_mm2': round(tr['fill_region'].area, 1), 'processing': ra['processing']})
    tinfo['open_area_fraction_of_canopy_envelope'] = tree_info['open_fraction_of_canopy_hull']
    tinfo['canopy_envelope_mm2'] = tree_info['canopy_hull_mm2']
    out['tree_piece'] = tinfo
    doors = []
    for pid in ('door_left', 'door_right'):
        a = assets[pid]; s = shapes[pid]; g = geo[pid]; ra = a['rasters'][0]; sc = ra['h']/ra['res_alpha'].shape[0]
        pct, _ = visible(ra, g['my'], g['left'], s['shoulder'])
        ys, xs = np.nonzero(ra['res_alpha'] > 128)
        doors.append({'id': pid, 'art_mm': [round(a['w'], 2), round(a['h'], 2)], 'canvas_mm': [round(a['w'], 2), round(a['h'], 2)],
            'cut_top_above_base_top_mm': out['pieces'][pid]['cut_top_above_base_top_mm'], 'configured_art_height_mm': a['rasters'][0]['art_height_mm_config'], 'scale_vs_v8_85mm': round(a['rasters'][0]['art_height_mm_config']/85.0, 4),
            'ink_box_in_scene_mm': {'x': [round(g['left']+xs.min()*sc, 2), round(g['left']+(xs.max()+1)*sc, 2)], 'z_above_base_top': [round(s['shoulder']-(ys.max()+1)*sc, 2), round(s['shoulder']-ys.min()*sc, 2)]},
            'plate_cut_bounds_mm': [round(v, 2) for v in s['poly'].bounds],
            'plate_cut_bounds_in_scene_mm': {'x': [round(g['left']+s['poly'].bounds[0], 2), round(g['left']+s['poly'].bounds[2], 2)], 'z_above_base_top': [round(s['shoulder']-s['poly'].bounds[3], 2), round(s['shoulder']-s['poly'].bounds[1], 2)]},
            'tab_x_scene_mm': round(g['mx'], 2), 'depth_row_mm': g['my'], 'assembled_height_mm': out['pieces'][pid]['assembled_height_mm'],
            'lattice_openings_cut': a['split_info']['openings'], 'lattice_openings_mm': a['split_info']['openings_mm'],
            'lattice_holes_in_source': a['split_info']['lattice_holes_in_source'], 'printed_sky_fill_mm2': round(a['fill_region'].area, 1),
            'minimum_art_to_cut_mm': round(s['clearance'], 3), 'minimum_feature_mm': neck_width(s['poly']),
            'minimum_feature_with_openings_mm': out['pieces'][pid].get('minimum_feature_with_openings_mm'),
            'visible_pct_in_front_view_not_hidden_by_front_plates': pct,
            'visible_pct_of_printed_ink_not_hidden_by_printed_ink_of_front_plates': visible_ink(pid),
            'processing': ra['processing']})
    out['doors'] = doors
    ch = assets['character']; cr = ch['rasters'][0]; cs = shapes['character']; g = geo['character']
    ra = cr['res_alpha'] > 128; ph, pw = ra.shape; sc = ch['h']/ph
    low = ra[int(ph*(1-4.0/ch['h'])):, :].any(0); cols = np.nonzero(low)[0]
    runs = []
    for c in cols:
        if runs and c == runs[-1][1]+1: runs[-1][1] = c
        else: runs.append([c, c])
    feet = []
    for a, b in runs:
        rows = np.nonzero(ra[:, a:b+1].any(1))[0]
        feet.append({'scene_x_mm': [round(g['left']+a*sc, 2), round(g['left']+(b+1)*sc, 2)],
                     'lowest_ink_above_base_top_mm': round(cs['border']+(ph-rows.max()-1)*sc, 2)})
    riser = cs['bud_guard'].get(round(cs['tab_cx'][0], 2), {})
    out['character_seating'] = {'configured_art_height_mm': cr['art_height_mm_config'], 'crop_below_fraction': cr['crop_below_fraction'],
        'whole_figure': cr['crop_below_fraction'] is None, 'kept_art_mm': [round(ch['w'], 2), round(ch['h'], 2)],
        'lowest_ink_above_base_top_mm': cs['border'], 'clear_rim_below_lowest_ink_mm': cs['border'],
        'feet_and_sword_runs_at_the_base_line': feet,
        'plinth_rise_mm': next(p for p in CFG['pieces'] if p['id'] == 'character').get('plinth_rise_mm', 8),
        'tab_cx_scene_mm': out['pieces']['character']['tab_cx_mm'],
        'tab_window_body_width_at_base_line_mm': round(_window_section(cs['poly'], cs['shoulder']-.125, cs['tab_cx'][0], CFG['tab_width_mm']/2)[0], 2),
        'bud_guard_riser': cs['bud_guard'],
        'clear_riser_mm': {'width': riser.get('riser_width_mm'), 'top_above_slot_line': riser.get('riser_top_above_slot_mm'),
                           'axis': riser.get('riser_axis'), 'note': 'unprinted clear acrylic inside the tab window between the legs; the only support below the hips'},
        'processing': cr['processing']}
    out['rules'] = {k: CFG['tree_one_piece'][k] for k in ('skeleton_rule', 'connector_rule', 'opening_rule', 'print_rule', 'trunk_rule')}
    out['rules']['doors'] = CFG['tree_one_piece']['doors']['rule']
    return out


def validate(assets, shapes, preset, items, gap, slot_gap, split):
    mind, worst, over, pairs = assembly_clearance(shapes)
    tclear = tree_clearance(shapes, assets)
    cov = front_coverage(shapes)
    folder = OUT/preset['name']
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
    assert len(items) == PIECE_COUNT and sum(len(p['holes']) for p in items) == SLOT_COUNT+sum(len(shapes[p['id']]['openings']) for p in CFG['pieces'])
    for p in items:
        for hole in p['holes']: assert p['poly'].contains(hole)
    for p in CFG['pieces']:
        for r in assets[p['id']]['rasters']:
            assert abs(r['w']/r['h']-r['source_px'][0]/r['source_px'][1]) < 1e-9
            if r['crop_below_fraction'] or r.get('canvas'): continue
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
    # One-piece plates (the tree; the doors): every printed pixel inside its
    # plate (outside the cut-out openings) with at least 0.5 mm of clear
    # acrylic around it, the
    # minimum feature on the outer profile and across the openings, every
    # opening at least the minimum feature wide, and no clear fill inside
    # the body apart from the rim, the connectors and the riser.
    for p in CFG['pieces']:
        if not p.get('one_piece'): continue
        a = assets[p['id']]; s = shapes[p['id']]; ra = a['rasters'][0]
        pm = np.zeros(arr.shape[:2], np.uint8)
        item = next(q for q in items if q['name'] == p['id'])
        ext = np.round(np.asarray(item['poly'].exterior.coords)*PPI).astype('int32')
        cv2.fillPoly(pm, [ext], 1)
        for o in item['holes']:
            cv2.fillPoly(pm, [np.round(np.asarray(o.exterior.coords)*PPI).astype('int32')], 0)
        x0, y0 = round(item['rasters'][0]['x']*PPI), round(item['rasters'][0]['y']*PPI)
        ink = np.zeros(arr.shape[:2], bool)
        rw, rh = round(ra['w']*PPI), round(ra['h']*PPI)
        alpha_img = np.asarray(Image.fromarray(ra['res_alpha']).resize((rw, rh), Image.BILINEAR)) > 128
        ink[y0:min(y0+rh, arr.shape[0]), x0:min(x0+rw, arr.shape[1])] = alpha_img[:max(0, min(rh, arr.shape[0]-y0)), :max(0, min(rw, arr.shape[1]-x0))]
        assert (ink & (pm == 0)).sum() == 0, (p['id'], 'ink outside the cut or inside an opening')
        dt = cv2.distanceTransform(pm, cv2.DIST_L2, 3)/PPI
        assert dt[ink].min() >= .5, (p['id'], 'ink closer than 0.5 mm to the cut', float(dt[ink].min()))
        nf = neck_width(s['poly'])
        assert nf is None or nf >= MIN_FEATURE_MM, (p['id'], 'minimum feature', nf)
        assert s['poly'].contains(a['art'])
        if s['openings']:
            holed = Polygon(s['poly'].exterior, [o.exterior for o in s['openings']])
            nf2 = neck_width(holed)
            assert nf2 is None or nf2 >= MIN_FEATURE_MM, (p['id'], 'minimum feature across openings', nf2)
            for o in s['openings']:
                assert s['poly'].contains(o) and not o.intersects(a['art']) and not any(o.intersects(r) for r in s['risers'])
                ow = neck_width(o)
                assert ow is None or ow >= MIN_FEATURE_MM, (p['id'], 'opening narrower than the minimum feature', ow)
                for q in s['openings']:
                    if q is not o: assert not o.intersects(q), (p['id'], 'openings touch')
                stats, _ = audit_path(cut_path(o))
                assert stats['segments'] <= max(100, 1.5*stats['perimeter_mm']), (p['id'], 'opening', stats)
        stats, _ = audit_path(cut_path(s['poly']))
        assert stats['segments'] <= max(100, 1.5*stats['perimeter_mm']), (p['id'], stats)
        # No clear acrylic fill inside the body: every pixel of the fill
        # region (body 0.75 mm inside every cut edge, openings excluded,
        # riser excluded; eroded 0.2 mm for the native-to-300 ppi resample)
        # carries ink.
        fm = np.zeros(arr.shape[:2], np.uint8)
        fill = affinity.translate(a['fill_region'], item['tx'], item['ty']).buffer(-.2, quad_segs=8)
        for g in (fill.geoms if fill.geom_type != 'Polygon' else [fill]):
            if g.is_empty: continue
            cv2.fillPoly(fm, [np.round(np.asarray(g.exterior.coords)*PPI).astype('int32')], 1)
            for ring in g.interiors: cv2.fillPoly(fm, [np.round(np.asarray(ring.coords)*PPI).astype('int32')], 0)
        sel = fm.astype(bool)
        assert sel.sum() > 0 and ink[sel].all(), (p['id'], 'clear fill inside the body', int((~ink[sel]).sum()))
        a['clear_fill_check'] = {'fill_px_at_300ppi': int(fm.sum()), 'unprinted_fill_px': int((~ink[sel]).sum())}
        # Nothing else inside the body is clear: body minus the 1.0 mm band
        # along the cut, minus the art, the connector halos, the printed gaps
        # and the riser must be empty inside the canvas (beyond it nothing can
        # print: that is the outer rim of widened frame bars).
        band = s['body'].buffer(-1.0, quad_segs=16)
        halos = unary_union([c.difference(a['art']) for c in a['connectors']]) if a['connectors'] else Polygon()
        rest = band.difference(unary_union([a['fill_region'], halos, a['art']]+[o.buffer(1.0, quad_segs=16) for o in s['openings']]+s['risers']))
        rest = rest.intersection(box(0, 0, a['w'], a['h']))
        assert rest.area < .5, (p['id'], 'clear region inside the body that is neither rim, connector nor printed gap', round(rest.area, 2))
        a['clear_fill_check']['other_clear_area_mm2'] = round(rest.area, 3)
    # Each embedded raster actually printed where it sits. Overlays on the
    # opaque sky are recognised by colour under their own opaque mask: a
    # pixel count there would also count the sky beneath them.
    for p in items:
        for k, r in enumerate(p['rasters']):
            x0, y0 = round(r['x']*PPI), round(r['y']*PPI)
            region = arr[y0:y0+round(r['h']*PPI), x0:x0+round(r['w']*PPI), 3]
            rpx = r['resample_px']
            if r['anchor'] != 'base':
                mask = np.asarray(Image.fromarray(r['res_alpha']).resize((region.shape[1], region.shape[0]), Image.BILINEAR)) > 128
                for later in p['rasters'][k+1:]:
                    if later['anchor'] == 'base': continue
                    lm = np.zeros(arr.shape[:2], bool)
                    lx, ly = round(later['x']*PPI), round(later['y']*PPI)
                    lm[ly:ly+round(later['h']*PPI), lx:lx+round(later['w']*PPI)] = np.asarray(Image.fromarray(later['res_alpha']).resize((round(later['w']*PPI), round(later['h']*PPI)), Image.BILINEAR)) > 128
                    mask &= ~lm[y0:y0+region.shape[0], x0:x0+region.shape[1]]
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
    # Real cut tops above the base top plus the base thickness (V9); the V8
    # report counted art top + one rim and omitted the rim under every plate.
    heights = {pid: round(preset['base_thickness_mm']+shapes[pid]['shoulder']-shapes[pid]['poly'].bounds[1], 2)
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
        'minimum_slot_gap_mm': slot_gap,
        'dimensions_are': 'nominal 18.8 x T cut-path centerlines; kerf and fit compensation is applied by scripts/build_a3_release.py (len_slot_fit, issue #1 policy)',
        'fit_status': 'UNTESTED; no fit-test pieces by repo policy',
        'physical_fit_test': False, 'test_pieces_included': False,
        'minimum_piece_gap_mm': gap, 'ai_layers': names,
        'same_row_standing_clearance_mm': mind, 'same_row_worst_pair': list(worst) if worst else None,
        'same_row_pairs': pairs,
        'same_row_note': f"the two door plates share row {sorted({p['mounts_mm'][0][1] for p in CFG['pieces'] if p['id'].startswith('door_')})} far apart; every same-row pair of standing cuts keeps at least 2 mm; the tree (row 31) stands alone on its row, so the grown tree (V10) overlaps the serpent, Len and the left door in the front view only across rows (see tree_visual_clearance_mm)",
        'tree_visual_clearance_mm': tclear,
        'door_backdrop_height_match': 'see composition.height_match (V10: both door cut tops and the tree cut top level with the back panel cut top)',
        'art_overhang_beyond_base_mm': over,
        'front_view_coverage_pct': cov,
        'front_view_policy': CFG['front_view_policy'],
        'load_path_floor_mm': LOAD_PATH_FLOOR_MM, 'riser_width_mm': RISER_WIDTH_MM, 'minimum_feature_mm': MIN_FEATURE_MM, 'opening_min_mm': CFG['tree_one_piece']['opening_min_mm'],
        'cut_out_openings': {p['id']: len(shapes[p['id']]['openings']) for p in CFG['pieces'] if shapes[p['id']]['openings']},
        'cut_out_opening_paths_drawn_first_with_slots': True,
        'bud_guard_risers': {p['id']: shapes[p['id']]['bud_guard']
            for p in CFG['pieces'] if shapes[p['id']]['bud_guard']},
        'blue_reference_four_sides': True, 'unprinted_tabs_and_slots': True,
        'slot_ink_clearance_checked_mm': 1.5, 'margins_nonblue_ink': True,
        'base_plate': f'supplied raster 07_base_art printed as-is, vertically centred '
                      'on a 2.5 mm clear rim; {SLOT_COUNT} slot windows ink-cleared 1.5 mm in-memory '
                      'by the builder (no separate prepared copy, no placeholder-slot surgery)',
        'piece_breakdown': {
            'backdrop': 'one plate: 05_background sky/wave raster mirrored into the two former door zones (30.4 / 30.5 mm) with the whole 04_moon_clouds layer (both islands) registered 5 mm below the sky top; no doors and no tree printed on it (V8); 3 tabs; its cut top 92.0 mm above the base top is the height both doors (V9) and the tree (V10) match',
            'tree': f"V10: the complete blossom tree (trunk, branches, every blossom cluster) as ONE cut piece printed with the original pixels, 35 deg clockwise; the V8 cut skeleton (opaque mask opened 1.5 mm at the 88 mm reference scale) restored past the V8 size and grown to {CFG['tree_one_piece']['art_height_mm']:.1f} mm art so the cut top stands on the shared door/backdrop top line, trunk base at scene x 96 behind the serpent as in V9 (slot unchanged); cut-out openings between branch/cluster groups, twig connectors 2.75 mm, narrow gaps printed with the sky colour; alone on row 31, its canopy behind the serpent and Len's left edge and a few upper-left blossoms behind the left door's corner (front view, reported)",
            'door_left, door_right': f"V9: the two lattice doorways of 06_lattice_doors.png as their own cut plates (89.57 mm art, V8 85 mm scaled 1.0538x so the cut top stands 92.0 mm above the base top level with the back panel, 1.0 mm rim, lattice openings printed), one 18 mm tab each at row {sorted({p['mounts_mm'][0][1] for p in CFG['pieces'] if p['id'].startswith('door_')})[0]} in front of the back panel on their V2-V8 axes",
            'snake': '02_snake silhouette plate, 1 tab (V2/V4 position)',
            'character': '01_character silhouette plate, 1 tab; the whole 84 mm figure (no crop), boot rims on the base line, bud-guard clear riser inside the tab window between the legs (V2/V4 scale and x)'},
        'layer_order_back_to_front': ['backdrop (sky extended into the door zones, moon/clouds)', 'door_left, door_right (lattice doorways)', 'tree (one piece)', 'snake', 'character'],
        'row_order_front_to_back': [p['id'] for p in sorted(CFG['pieces'], key=lambda q: q['mounts_mm'][0][1])]+['backdrop'],
        'composition': composition_report(assets, shapes, split, tclear),
        'revision_note': CFG['revision_note'],
        'preview_rendering': 'clear acrylic see-through on a dark mauve ground: plate bodies unfilled, one 0.26 mm lit-edge stroke per plate, tabs clipped at the shoulder (inside the slots); base slab shows its front side band',
        'unused_source_islands': CFG['unused_source_islands'],
        'assets': {p['id']: {'file': assets[p['id']]['src_name'],
            'sha256': assets[p['id']]['rasters'][0]['sha256'],
            'rasters': [{'file': r['file'], 'sha256': r['sha256'], 'anchor': r['anchor'],
                'offset_mm': [round(r['dx'], 3), round(r['dy'], 3)],
                'source_bbox_px': r['source_bbox_px'], 'source_px': r['source_px'],
                'resample_px': r['resample_px'],
                'art_width_mm': round(r['w'], 3), 'art_height_mm': round(r['h'], 3),
                'configured_art_height_mm': r['art_height_mm_config'], 'rotate_deg': r['rotate_deg'],
                'crop_below_fraction': r['crop_below_fraction'],
                'effective_ppi': r['effective_ppi'], 'native_cap': r['native_cap'],
                'processing': r['processing'], 'clip': r['clip'], 'note': r.get('note')}
                for r in assets[p['id']]['rasters']],
            'art_width_mm': round(assets[p['id']]['w'], 3), 'art_height_mm': round(assets[p['id']]['h'], 3),
            'minimum_art_to_cut_mm': shapes[p['id']]['clearance'],
            'minimum_feature_mm': neck_width(shapes[p['id']]['poly']),
            'clear_border_mm': shapes[p['id']]['border'],
            'resample': 'LANCZOS; exact 300 ppi print size, never upscaled past native pixels', 'redrawn': False,
            'processing': assets[p['id']]['processing'],
            **({'split_info': assets[p['id']]['split_info']} if assets[p['id']].get('split_info') else {}),
            **({'clear_fill_check': assets[p['id']]['clear_fill_check']} if assets[p['id']].get('clear_fill_check') else {})}
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
    global CUT_PATH_COUNT
    presets = CFG['presets']
    tree = OnePieceTree(CFG['tree_one_piece'])
    assets = {}
    for p in CFG['pieces']:
        if p['id'] == 'tree': assets[p['id']] = load_tree(tree, p)
        elif p['id'].startswith('door_'): assets[p['id']] = load_door(p)
        elif not p.get('one_piece'): assets[p['id']] = load_piece(p)
    CUT_PATH_COUNT = PIECE_COUNT+SLOT_COUNT+sum(len(a['openings']) for a in assets.values() if a.get('one_piece'))
    hull = assets['tree']['outer'].convex_hull
    tree_info = {'open_fraction_of_canopy_hull': round(1-assets['tree']['outer'].area/hull.area, 3), 'canopy_hull_mm2': round(hull.area, 1)}
    reports = []
    tree_mount = next(p for p in CFG['pieces'] if p['id'] == 'tree')['mounts_mm'][0][0]
    for preset in presets:
        folder = OUT/preset['name']; (folder/'preview').mkdir(parents=True, exist_ok=True)
        assets['base'] = load_base(preset)
        shapes = {p['id']: standee(assets[p['id']], preset['base_thickness_mm'], p['mounts_mm'], p.get('plinth_rise_mm', 8), p.get('simplify_mm', .015), p.get('clear_border_mm', CFG['clear_border_mm'])) for p in CFG['pieces']}
        # One-piece plates print after the risers are known so the riser stays clear.
        sample = sky_sampler(assets['backdrop'], CFG['tree_one_piece']['gap_colour_blur_mm'])
        for p in CFG['pieces']:
            if not p.get('one_piece'): continue
            s = shapes[p['id']]; a = assets[p['id']]
            mx = sum(m[0] for m in p['mounts_mm'])/len(p['mounts_mm'])
            s_ = dict(s, scene_left=mx-(s['tab_x_mm'] if s['tab_x_mm'] is not None else a['w']/2))
            assets[p['id']].update(one_piece_print(a, s_, sample))
            a['split_info']['printed_sky_mm2'] = assets[p['id']]['printed_sky_mm2']
        items, gap, slot_gap = make_board(assets, shapes, preset, folder)
        assembly(assets, shapes, preset, folder)
        report = validate(assets, shapes, preset, items, gap, slot_gap, tree_info); reports.append(report)
        print(json.dumps({'preset': preset['name'], 'pieces': PIECE_COUNT, 'cut_paths': CUT_PATH_COUNT,
            'same_row_mm': report['same_row_standing_clearance_mm'], 'slot_gap_mm': slot_gap,
            'coverage': report['front_view_coverage_pct'],
            'risers': report['bud_guard_risers'],
            'art': {k: round(v['w'], 1) for k, v in assets.items() if k != 'base'},
            'openings': {k: len(v['openings']) for k, v in shapes.items()},
            'plate_bounds': {k: [round(x, 1) for x in v['poly'].bounds] for k, v in shapes.items()},
            'base': [round(assets['base']['w'], 1), round(assets['base']['h'], 1)]}, ensure_ascii=False), flush=True)
        prune_archive(folder, keep_preview=preset is presets[0])
    ti = assets['tree']['split_info']
    print(json.dumps({'product': CFG['product'], 'tree': {k: ti[k] for k in ('detached_clusters', 'connectors', 'connector_twig_path_total_mm', 'openings', 'openings_mm', 'printed_sky_mm2', 'minimum_feature_mm')},
        'doors': {d: {k: assets[d]['split_info'][k] for k in ('lattice_holes_in_source', 'openings', 'minimum_feature_mm', 'printed_sky_mm2')} for d in ('door_left', 'door_right')},
        'archive': [str(p.relative_to(ROOT)) for p in sorted(OUT.rglob('*')) if p.is_file()]}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
