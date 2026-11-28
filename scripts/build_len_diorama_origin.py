"""Len ORIGIN layered slot-in acrylic diorama, V7.

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
rejected it ("이거 아니야 v4에서 잘림 문제만 해결하고 나무를 예시 이미지처럼
대각선 배치 해달라고"). V6 (62963a8) = V4 with exactly those two changes: Len
shown whole and the printed tree leaning up to the right like the concept.

V7 = the owner's decision on the tree ("벚꽃하고 나무는 별도 에셋으로 분리해줘"):
the blossom tree is neither printed on the back panel (V4/V6) nor one
clear-webbed cut piece (V5). 03_blossom_tree.png is split by colour into

* a TREE piece: the dark trunk and branches (wood pixels), twigs under 0.5 mm
  pruned, 1.0 mm rim, standing on its own 18 mm tab on its own depth row
  with its base behind the serpent, 35 deg clockwise like V6 but 88 mm art so
  the whole tree stands on the base line inside the sky;
* seven BLOSSOM pieces: pink petal clusters grouped around the branch tips by
  seed discs, each its own plate with a 1.0 mm rim, no webbing between
  clusters, mounted on the base BEHIND the tree plate on three depth rows
  (see configs/len_diorama_origin.json) on a 12.25 mm clear stem, so the
  branches cross in front of them and the gaps between clusters show the sky
  and moon like the concept's open arching tree.

Everything else is V6 exactly, see configs/len_diorama_origin.json:

* Clear border 1.0 mm on every plate.
* The back panel is ONE plate: the sky raster with both lattice doors butted
  against its sides and the moon/cloud layer registered over the sky.
* Tree, serpent and character stay shaped plates on their own depth rows, so
  the concept's layering (sky -> blossoms -> tree -> serpent -> character) and
  the diorama depth are kept.
* The assembly preview renders clear acrylic see-through: no body fill and
  one thin edge stroke per plate.
* Len is shown WHOLE: no seat crop. Both boot rims rest on the base line and
  the bud guard carries the plate on a clear riser inside the tab window.

Every raster keeps its native pixels (LANCZOS to the 300 ppi print size, never
upscaled); the tree's rotation is the only resampling step and acts at native
resolution before that downsample. No fit-test pieces: current repo policy
rejects all test pieces.

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
from shapely.geometry import Polygon, box, LineString
from shapely import affinity, concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from laser_paths import cut_path, audit_path
from vector_utils import runvc, svg_doc, path, poly_path, layer

OUT = ROOT/'output/len_diorama_origin_v7'
TMP = ROOT/'tmp/len_diorama_origin_v7'
CFG = json.loads((ROOT/'configs/len_diorama_origin.json').read_text(encoding='utf-8'))
BOARD = tuple(CFG['board_mm'])
PPI = 300/25.4
RED = '#ff0000'
BLUE = '#0000ff'
SRC = ROOT/'assets/len_orgin'
LOAD_PATH_FLOOR_MM = 12.0
STEM_WIDTH_MM = LOAD_PATH_FLOOR_MM+.25
MIN_FEATURE_MM = CFG['tree_split']['min_feature_mm']
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


class TreeSplit:
    """Colour split of the rotated blossom tree into the wood skeleton and the
    petal clusters (V7). All masks live on the native pixels of the 35 deg
    clockwise rotation V6 already used; millimetres follow the configured art
    height so the split is computed once for both thicknesses."""

    def __init__(self, split_cfg):
        self.cfg = split_cfg
        spec = {'file': split_cfg['file'], 'art_height_mm': split_cfg['art_height_mm'], 'rotate_deg': split_cfg['rotate_deg']}
        self.im, self.bbox, self.ref_h, self.processing = source_pixels(spec)
        a = np.asarray(self.im)
        self.rgb = a[..., :3].astype(int)
        self.alpha = a[..., 3]
        self.s = split_cfg['art_height_mm']/self.ref_h
        self.pxmm = 1/self.s
        op = self.alpha > 128
        r, g, b = self.rgb[..., 0], self.rgb[..., 1], self.rgb[..., 2]
        red_dominant = (r-np.maximum(g, b) >= 45) & (r >= 110)
        self.petal = op & red_dominant
        self.wood = op & ~red_dominant
        self.opaque = op
        self.H, self.W = op.shape
        self.kernel_cache = {}

    def kernel(self, mm):
        r = max(1, int(round(mm*self.pxmm)))
        if r not in self.kernel_cache:
            self.kernel_cache[r] = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
        return self.kernel_cache[r]

    def morph(self, mask, op, mm):
        return cv2.morphologyEx(mask.astype('uint8'), op, self.kernel(mm)) > 0

    def smooth(self, mask, mm):
        return self.morph(self.morph(mask, cv2.MORPH_CLOSE, mm), cv2.MORPH_OPEN, mm)

    def main_component(self, mask):
        n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'), 8)
        assert n > 1, 'empty mask'
        main = max(range(1, n), key=lambda i: st[i, 4])
        return (lab == main), int(st[main, 4])

    def polygon(self, mask, sigma_px):
        """Outer contour of a mask as a smooth polygon: the pixel staircase is
        Gaussian-smoothed along the contour so laser_paths can fit it within
        the segment gate; enclosed holes are dropped (no interior rings)."""
        cnts, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cnts, key=cv2.contourArea)[:, 0, :].astype(float)
        if len(c) > 8:
            c = np.stack([gaussian_filter1d(c[:, 0], sigma_px, mode='wrap'), gaussian_filter1d(c[:, 1], sigma_px, mode='wrap')], 1)
        p = Polygon(c*[self.s, self.s]).buffer(0)
        if p.geom_type != 'Polygon': p = max(p.geoms, key=lambda g: g.area)
        if p.interiors: p = Polygon(p.exterior).buffer(0)
        assert p.geom_type == 'Polygon' and p.is_valid and not p.interiors, p.geom_type
        return p

    def filled(self, poly):
        m = np.zeros((self.H, self.W), 'uint8')
        ext = np.round(np.asarray(poly.exterior.coords)/self.s).astype('int32')
        cv2.fillPoly(m, [ext], 1)
        return m > 0

    def skeleton(self):
        cfg = self.cfg
        wood = self.smooth(self.wood, cfg['wood_smooth_mm'])
        opened = self.morph(wood, cv2.MORPH_OPEN, cfg['wood_open_mm'])
        sk, px = self.main_component(opened)
        return sk, {'wood_px': int(self.wood.sum()), 'wood_smoothed_px': int(wood.sum()),
            'wood_kept_px': px, 'wood_pruned_px': int(self.wood.sum())-int((sk & self.wood).sum()),
            'dropped_wood_islands_px': int(opened.sum())-px}

    def clusters(self):
        cfg = self.cfg
        pm = self.smooth(self.petal, cfg['wood_smooth_mm'])
        yy, xx = np.mgrid[0:self.H, 0:self.W]
        xm = (xx+.5)*self.s; ym = (yy+.5)*self.s
        seeds = [tuple(c['seed_mm']) for c in cfg['clusters']]
        d = np.stack([np.hypot(xm-sx, ym-sy) for sx, sy in seeds])
        nearest = d.argmin(0)
        out = []
        for i, c in enumerate(cfg['clusters']):
            region = (nearest == i) & (d[i] <= c['radius_mm'])
            # Keep clusters apart by a sky gap: petals within half the gap of
            # the Voronoi boundary between two seeds are not cut.
            others = np.delete(d, i, axis=0).min(0)
            region &= (others-d[i]) >= 2*cfg['cluster_gap_mm']
            m = self.morph(region & pm, cv2.MORPH_CLOSE, cfg['rim_closing_mm'])
            n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype('uint8'), 8)
            keep = np.zeros_like(m)
            for k in range(1, n):
                if st[k, 4]*self.s*self.s >= cfg['min_cluster_island_mm2']: keep |= (lab == k)
            # A cluster is ONE plate: the largest component; larger satellites
            # are dropped with the small islands rather than cut separately.
            keep, main_px = self.main_component(keep)
            dropped = int(m.sum())-int(keep.sum())
            out.append((keep, {'petal_px_in_disc': int((region & pm).sum()), 'cluster_px': int(keep.sum()), 'islands_dropped_px': dropped}))
        return out


def closing(p, r):
    return p.buffer(r, quad_segs=28).buffer(-r, quad_segs=28)


def neck_width(poly):
    """Narrowest connection of a plate: twice the erosion radius that first
    splits it (tab corners excluded by starting above the shoulder)."""
    for k in range(1, 16):
        e = poly.buffer(-k*.25, quad_segs=16)
        n = len(e.geoms) if hasattr(e, 'geoms') else (0 if e.is_empty else 1)
        if n > 1: return 2*(k*.25-.125)
    return None


def embed_canvas(im, w, h, art, extra):
    """Embed a native-pixel canvas (tree piece or blossom piece) at print scale."""
    pw, ph = im.size
    tw, th = max(1, min(round(w*PPI), pw)), max(1, min(round(h*PPI), ph))
    res = im.resize((tw, th), Image.LANCZOS)
    ra = np.asarray(res); solid = ra[:, :, 3] > 128
    buf = io.BytesIO(); res.save(buf, 'PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    ink = (f'<image x="0" y="0" width="{w:.6f}" height="{h:.6f}" '
           f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    source = SRC/'03_blossom_tree.png'
    return dict({'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_px': [pw, ph], 'source_bbox_px': None, 'resample_px': [tw, th],
        'w': w, 'h': h, 'ink': ink, 'art': art, 'canvas': True,
        'processing': None, 'clip': None,
        'art_height_mm_config': CFG['tree_split']['art_height_mm'], 'rotate_deg': CFG['tree_split']['rotate_deg'],
        'crop_below_fraction': None,
        'opaque_px': int((ra[:, :, 3] > 8).sum()),
        'res_alpha': ra[:, :, 3].copy(), 'mean_rgb': ra[solid][:, :3].mean(0) if solid.any() else np.zeros(3),
        'native_cap': bool(tw < pw-1 or (tw == pw and th == ph and round(w*PPI) > pw)),
        'effective_ppi': round(tw/(w/25.4))}, **extra)


def load_tree(split, spec):
    """The tree piece: wood skeleton as the cut silhouette and the print."""
    cfg = split.cfg
    sk, info = split.skeleton()
    art = split.polygon(sk, cfg['contour_sigma_px'])
    H, W = split.H, split.W
    # The print is the original pixels inside the kept skeleton mask.
    arr = np.asarray(split.im).copy()
    arr[~sk, 3] = 0
    im = Image.fromarray(arr, 'RGBA')
    # Tab under the lowest point of the skeleton (the trunk base).
    ys, xs = np.nonzero(sk)
    low = xs[ys >= ys.max()-max(1, int(round(.5*split.pxmm)))]
    tab_x = float(low.mean()*split.s)
    w, h = W*split.s, H*split.s
    body = closing(art.buffer(CFG['clear_border_mm'], quad_segs=28), cfg['rim_closing_mm'])
    if body.geom_type != 'Polygon': body = max(body.geoms, key=lambda g: g.area)
    body = Polygon(body.exterior) if body.interiors else body
    raster = embed_canvas(im, w, h, art, {'dx': 0.0, 'dy': 0.0, 'anchor': 'base', 'source_bbox_px': split.bbox,
        'processing': split.processing+'; V7 tree piece: wood mask (not red-dominant) closed %.1f mm, opened %.1f mm (twigs under that ink width pruned), '
                      'largest component kept; print = original pixels inside the kept skeleton' % (cfg['wood_smooth_mm'], cfg['wood_open_mm'])})
    return {'id': spec['id'], 'src_name': '03_blossom_tree.png', 'w': w, 'h': h, 'ink': raster['ink'],
        'art': art, 'rasters': [raster], 'opaque_px': raster['opaque_px'],
        'tab_x_mm': tab_x, 'body_override': body, 'split_info': info,
        'processing': 'tree piece: wood skeleton separated from the blossoms by colour'}


def load_blossom(split, spec, cluster_mask, info, base_y_mm):
    """One blossom cluster as a standee: cluster silhouette plus a clear stem
    down to the base line, centred on its own tab axis."""
    cfg = split.cfg
    art0 = split.polygon(cluster_mask, cfg['contour_sigma_px'])
    x0, y0, x1, y1 = art0.bounds
    cluster_body = closing(art0.buffer(CFG['clear_border_mm'], quad_segs=28), cfg['rim_closing_mm'])
    if cluster_body.geom_type != 'Polygon': cluster_body = max(cluster_body.geoms, key=lambda g: g.area)
    cluster_body = Polygon(cluster_body.exterior) if cluster_body.interiors else cluster_body
    half = STEM_WIDTH_MM/2
    # Stem axis = the lowest point of the buffered cluster within the tab
    # window around the widest run near the cluster's bottom, so the bud
    # guard's riser (centred on that same lowest section) coincides with the
    # stem instead of standing beside it.
    stem_x = float(spec['stem_x_mm'])
    cols = np.nonzero((np.arange(split.W)*split.s >= stem_x-half) & (np.arange(split.W)*split.s <= stem_x+half))[0]
    rows = np.nonzero(cluster_mask[:, cols].any(1))[0]
    assert len(rows), (spec['id'], 'stem misses the cluster')
    stem_top = rows.max()*split.s-2.0
    # The clear stem runs up through every narrow section of the cluster inside
    # the tab window (inside the cluster it is a no-op: the body already fills
    # that area), so the bud guard never has to raise a riser beside it.
    for i in range(400):
        w, _ = _window_section(cluster_body, stem_top, stem_x, CFG['tab_width_mm']/2)
        if w >= STEM_WIDTH_MM-.001 or stem_top <= y0+.5: break
        stem_top -= .25
    assert w >= STEM_WIDTH_MM-.001, (spec['id'], 'cluster never reaches the stem width inside the tab window', round(stem_x, 2), round(w, 2))
    # Canvas centred on the stem axis, wide enough for the whole cluster.
    W = 2*max(stem_x-x0, x1-stem_x)
    W = math.ceil(W/split.s)*split.s
    left = stem_x-W/2
    H = math.ceil((base_y_mm-y0)/split.s)*split.s
    px = [int(round(left/split.s)), int(round(y0/split.s)), int(round((left+W)/split.s)), int(round((y0+H)/split.s))]
    assert px[2] > px[0] and px[3] > px[1] and px[3] <= split.H, (spec['id'], px)
    left, y0 = px[0]*split.s, px[1]*split.s
    w, h = (px[2]-px[0])*split.s, (px[3]-px[1])*split.s
    def window(array):
        out = np.zeros((px[3]-px[1], px[2]-px[0])+array.shape[2:], array.dtype)
        ix0, iy0 = max(0, px[0]), max(0, px[1]); ix1, iy1 = min(split.W, px[2]), min(split.H, px[3])
        out[iy0-px[1]:iy1-px[1], ix0-px[0]:ix1-px[0]] = array[iy0:iy1, ix0:ix1]
        return out
    # Print every opaque pixel inside the cluster contour (petals and the twigs
    # between them); everything else on the canvas stays clear.
    inside = window(split.filled(art0)[..., None])[..., 0] > 0
    crop = window(np.asarray(split.im))
    crop[~inside, 3] = 0
    im = Image.fromarray(crop, 'RGBA')
    art = affinity.translate(art0, -left, -y0)
    stem = box(w/2-half, stem_top-y0, w/2+half, h)
    body = unary_union([affinity.translate(cluster_body, -left, -y0), stem])
    if body.geom_type != 'Polygon': body = max(body.geoms, key=lambda g: g.area)
    body = Polygon(body.exterior) if body.interiors else body
    assert body.geom_type == 'Polygon' and art.difference(body).area < 1e-6, (spec['id'], body.geom_type, art.difference(body).area)
    ys, xs = np.nonzero(cluster_mask)
    raster = embed_canvas(im, w, h, art, {'dx': 0.0, 'dy': 0.0, 'anchor': 'base', 'source_bbox_px': [split.bbox[0]+px[0], split.bbox[1]+px[1], px[2]-px[0], px[3]-px[1]],
        'processing': split.processing+f"; V7 blossom piece '{spec['cluster']}': petals inside the seed disc {spec['seed_mm']} mm r {spec['radius_mm']} mm (Voronoi among seeds) closed {cfg['rim_closing_mm']} mm, islands under {cfg['min_cluster_island_mm2']} mm2 dropped; print = every opaque pixel inside the cluster contour; clear stem {STEM_WIDTH_MM} mm from the cluster down to the base line"})
    opaque_inside = int((inside & (window(split.opaque[..., None])[..., 0] > 0)).sum())
    return {'id': spec['id'], 'src_name': '03_blossom_tree.png', 'w': w, 'h': h, 'ink': raster['ink'],
        'art': art, 'rasters': [raster], 'opaque_px': raster['opaque_px'],
        'tab_x_mm': w/2, 'body_override': body, 'shoulder_override': h,
        'split_info': dict(info, cluster_box_mm=[round(v, 2) for v in art0.bounds], canvas_box_mm=[round(left, 2), round(y0, 2), round(left+w, 2), round(y0+h, 2)],
            stem_top_mm=round(stem_top, 2), stem_length_mm=round(h-(stem_top-y0), 2), stem_x_mm=round(stem_x, 2),
            opaque_px_inside_contour=opaque_inside, contour_area_mm2=round(art0.area, 1)),
        'processing': f"blossom piece '{spec['cluster']}' on a clear stem"}


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
        'tab_x_mm': tab_x, 'body': body}


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
    bd = assets['backdrop']; ch = assets['character']; tr = assets['tree']
    nb = sum(1 for p in CFG['pieces'] if p['id'].startswith('blossom_'))
    labels = (svg_text(13, 396, f'LEN DIORAMA ORIGIN V7 / {preset["name"]} / {PIECE_COUNT} PIECES', 4.0)
        + svg_text(13, 403, f'BASE / {CFG["base_mm"][0]:.0f} x {CFG["base_mm"][1]:.1f} cut / wave art {assets["base"]["w"]:.0f} x {assets["base"]["h"]:.1f} centred + 2.5 clear rim', 3.1)
        + svg_text(13, 410, f'{SLOT_COUNT} SLOTS 18.8 x {preset["slot_width_mm"]:.2f} / rows y {depths} (backdrop: 3 tabs)', 3.1)
        + svg_text(13, 417, f'BACKDROP {shapes["backdrop"]["poly"].bounds[2]-shapes["backdrop"]["poly"].bounds[0]:.0f}x{bd["h"]:.0f} (sky + doors + moon/clouds printed on it)  TREE piece {tr["w"]:.0f}x{tr["h"]:.0f} canvas ({CFG["tree_split"]["art_height_mm"]:.0f} mm art rotated {CFG["tree_split"]["rotate_deg"]:g} deg clockwise, wood only, {tr["rasters"][0]["effective_ppi"]} ppi)  {nb} BLOSSOM pieces on 12.25 mm clear stems  SNAKE {assets["snake"]["w"]:.0f}x{assets["snake"]["h"]:.0f}  CHARACTER whole {ch["w"]:.0f}x{ch["h"]:.1f} ({ch["rasters"][0]["art_height_mm_config"]:.0f} mm art, no crop, clear riser in the tab window)  / clear rim {CFG["clear_border_mm"]:.1f}', 3.0))
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
    because they sit inside the base slots. Plates are drawn back to front by
    depth row: backdrop, blossom plates (three rows), tree, serpent,
    whole seated character.
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
        parts.append(f'<g transform="translate({X:.4f} {Y:.4f})">'
                     + path(poly_path(body), 'none', EDGE, EDGE_W) + a['ink'] + '</g>')
    parts.append(svg_text(13, 15, 'LEN DIORAMA ORIGIN V7', 5, TEXT))
    parts.append(svg_text(13, 23, f'base {bw:.0f} x {bh:.1f} mm / {PIECE_COUNT} pieces / clear rim {CFG["clear_border_mm"]:.1f} mm on every plate / clear acrylic drawn see-through on a dark ground', 3.4))
    parts.append(svg_text(13, 252, f'V7 / {preset["name"]} / one back panel: sky + lattice doors + moon and clouds / tree as its own cut piece (trunk and branches) standing diagonally behind the serpent / {sum(1 for p in CFG["pieces"] if p["id"].startswith("blossom_"))} blossom cluster plates on clear stems behind the branches, gaps show the sky and moon / serpent plate / whole Len plate, feet on the base line, carried by a clear riser in the tab window', 3.1))
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
            'left': mx-tabx, 'right': mx-tabx+a['w'], 'top': s['shoulder']+a['h'], 'row': my}
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


def _ink_mask(raster, x0, ztop, res=.25):
    """Printed pixels of one raster as a scene grid (x from the base's left
    edge, z up from the base top) at `res` mm per cell."""
    ra = raster['res_alpha'] > 128
    h, w = ra.shape; sc = raster['h']/h
    nx = int(math.ceil(CFG['base_mm'][0]/res))+1; nz = int(math.ceil(100/res))+1
    m = np.zeros((nz, nx), bool)
    ix0 = int(round(x0/res)); iz0 = int(round((100-ztop)/res))
    sx = max(1, int(round(sc/res)))
    up = np.repeat(np.repeat(ra, sx, axis=0), sx, axis=1)
    j0 = max(0, iz0); j1 = min(nz, iz0+up.shape[0]); i0 = max(0, ix0); i1 = min(nx, ix0+up.shape[1])
    if j1 > j0 and i1 > i0:
        m[j0:j1, i0:i1] = up[j0-iz0:j1-iz0, i0-ix0:i1-ix0]
    return m


def composition_report(assets, shapes, split):
    """Measure the V7 scene from the real rasters and cut polygons: where every
    plate stands, how the tree piece and the blossom plates sit relative to
    the moon and the plates in front of them, how the clear stems are placed,
    and how the whole character meets the base line (feet, riser)."""
    geo = _scene_geometry(assets, shapes)
    out = {'scene_width_mm': CFG['base_mm'][0], 'row_order_front_to_back': [p['id'] for p in sorted(CFG['pieces'], key=lambda q: q['mounts_mm'][0][1])], 'pieces': {}}
    for pid, g in geo.items():
        a = g['art']; s = g['shape']
        out['pieces'][pid] = {'art_mm': [round(a['w'], 2), round(a['h'], 2)], 'plate_cut_bounds_mm': [round(x, 2) for x in s['poly'].bounds],
            'art_center_x_mm': round(g['mx'], 2), 'art_span_x_mm': [round(g['left'], 2), round(g['right'], 2)],
            'depth_row_mm': g['my'], 'assembled_height_mm': round(CFG['presets'][0]['base_thickness_mm']+g['top'], 2),
            'effective_ppi': [r['effective_ppi'] for r in a['rasters']], 'clear_border_mm': s['border'],
            'tab_cx_mm': [round(g['mx']-g['tabx']+cx, 2) for cx in s['tab_cx']],
            'minimum_art_to_cut_mm': round(s['clearance'], 3), 'minimum_feature_mm': neck_width(s['poly'])}
    standing = standing_cuts(shapes)
    bd = assets['backdrop']; sky = bd['rasters'][0]; comp = out['pieces']['backdrop']
    comp['sky_mm'] = [round(sky['w'], 2), round(sky['h'], 2)]
    comp['sky_span_x_mm'] = [round(geo['backdrop']['left'], 2), round(geo['backdrop']['right'], 2)]
    sky_left = geo['backdrop']['mx']-sky['w']/2
    cuts_in_front = lambda row: [g for pid, (g, my) in standing.items() if my < row]
    # Printed-ink occlusion (what the eye sees through clear acrylic) per piece.
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
    # The same disc against the PRINTED ink of every plate in front of it.
    front = ink_in_front(geo['backdrop']['my'])
    res = .25; disc_cells = 0; disc_seen = 0
    for zz in np.arange(0, 100, res):
        for xx in np.arange(0, CFG['base_mm'][0], res):
            if (xx-disc_x)**2+(zz-disc_z)**2 <= (radius*scm)**2:
                disc_cells += 1
                if not front[int(round((100-zz)/res)), int(round(xx/res))]: disc_seen += 1
    comp['moon_disc']['visible_pct_against_printed_ink_of_front_plates'] = round(100*disc_seen/disc_cells, 1) if disc_cells else None
    # Tree piece: the wood skeleton, its scene box and what the plates in front hide.
    tr = assets['tree']; ts = shapes['tree']; tg = geo['tree']; ra = tr['rasters'][0]
    tinfo = dict(tr['split_info'])
    sc = ra['h']/ra['res_alpha'].shape[0]
    pct, _ = visible(ra, tg['my'], tg['left'], ts['shoulder'])
    ys, xs = np.nonzero(ra['res_alpha'] > 128)
    tinfo.update({'rotate_deg_clockwise': CFG['tree_split']['rotate_deg'], 'configured_art_height_mm': CFG['tree_split']['art_height_mm'],
        'unrotated_alpha_box_px': ra['source_bbox_px'][2:], 'source_density_ppi': round(ra['source_bbox_px'][3]/(CFG['tree_split']['art_height_mm']/25.4)),
        'embedded_ppi': ra['effective_ppi'], 'resample_px': ra['resample_px'], 'native_cap': ra['native_cap'],
        'canvas_mm': [round(tr['w'], 2), round(tr['h'], 2)], 'wood_ink_box_mm': [round(xs.min()*sc, 2), round(ys.min()*sc, 2), round((xs.max()+1)*sc, 2), round((ys.max()+1)*sc, 2)],
        'wood_ink_box_in_scene_mm': {'x': [round(tg['left']+xs.min()*sc, 2), round(tg['left']+(xs.max()+1)*sc, 2)], 'z_above_base_top': [round(ts['shoulder']-(ys.max()+1)*sc, 2), round(ts['shoulder']-ys.min()*sc, 2)]},
        'plate_cut_bounds_in_scene_mm': {'x': [round(tg['left']+ts['poly'].bounds[0], 2), round(tg['left']+ts['poly'].bounds[2], 2)], 'z_above_base_top': [round(ts['shoulder']-ts['poly'].bounds[3], 2), round(ts['shoulder']-ts['poly'].bounds[1], 2)]},
        'art_area_mm2': round(tr['art'].area, 1), 'body_area_mm2': round(ts['poly'].area, 1), 'clear_rim_and_riser_mm2': round(ts['poly'].area-ts['body'].area+0, 1),
        'minimum_art_to_cut_mm': round(ts['clearance'], 3), 'minimum_feature_mm': neck_width(ts['poly']),
        'tab_x_scene_mm': round(tg['mx']-tg['tabx']+ts['tab_cx'][0], 2), 'depth_row_mm': tg['my'],
        'visible_pct_in_front_view_not_hidden_by_front_plates': pct,
        'visible_pct_of_printed_ink_not_hidden_by_printed_ink_of_front_plates': visible_ink('tree'),
        'bud_guard_riser': ts['bud_guard'], 'processing': ra['processing']})
    out['tree_piece'] = tinfo
    bl = []
    for spec in CFG['pieces']:
        if not spec['id'].startswith('blossom_'): continue
        a = assets[spec['id']]; s = shapes[spec['id']]; g = geo[spec['id']]; ra = a['rasters'][0]; sc = ra['h']/ra['res_alpha'].shape[0]
        pct, _ = visible(ra, g['my'], g['left'], s['shoulder'])
        ys, xs = np.nonzero(ra['res_alpha'] > 128)
        bl.append({'id': spec['id'], 'cluster': spec['cluster'], 'seed_mm': spec['seed_mm'], 'disc_radius_mm': spec['radius_mm'],
            'art_mm': [round(a['w'], 2), round(a['h'], 2)], 'canvas_mm': [round(a['w'], 2), round(a['h'], 2)],
            'cluster_box_in_scene_mm': {'x': [round(g['left']+xs.min()*sc, 2), round(g['left']+(xs.max()+1)*sc, 2)], 'z_above_base_top': [round(s['shoulder']-(ys.max()+1)*sc, 2), round(s['shoulder']-ys.min()*sc, 2)]},
            'plate_cut_bounds_in_scene_mm': {'x': [round(g['left']+s['poly'].bounds[0], 2), round(g['left']+s['poly'].bounds[2], 2)], 'z_above_base_top': [round(s['shoulder']-s['poly'].bounds[3], 2), round(s['shoulder']-s['poly'].bounds[1], 2)]},
            'tab_x_scene_mm': round(g['mx'], 2), 'depth_row_mm': g['my'], 'stem_mm': {'width': STEM_WIDTH_MM, 'length': a['split_info']['stem_length_mm'], 'top_inside_cluster_mm': 2.0, 'printed': False},
            'ink_mm2': round(a['split_info']['opaque_px_inside_contour']*sc*sc, 1), 'body_area_mm2': round(s['poly'].area, 1),
            'clear_fill_pct_of_cluster_body': round(100*(1-a['split_info']['opaque_px_inside_contour']*sc*sc/(s['poly'].area-a['split_info']['stem_length_mm']*STEM_WIDTH_MM)), 1),
            'minimum_art_to_cut_mm': round(s['clearance'], 3), 'minimum_feature_mm': neck_width(s['poly']),
            'visible_pct_in_front_view_not_hidden_by_front_plates': pct,
            'visible_pct_of_printed_ink_not_hidden_by_printed_ink_of_front_plates': visible_ink(spec['id']),
            'laser_path_segments': None, 'processing': ra['processing']})
    st = standing_cuts(shapes)
    bl_ids = [b['id'] for b in bl]
    gaps = []
    for i in range(len(bl_ids)):
        for j in range(i+1, len(bl_ids)):
            d = st[bl_ids[i]][0].distance(st[bl_ids[j]][0])
            gaps.append({'pair': [bl_ids[i], bl_ids[j]], 'front_view_gap_mm': round(d, 2)})
    out['blossom_pieces'] = bl
    out['blossom_front_view_gaps_mm'] = sorted(gaps, key=lambda r: r['front_view_gap_mm'])[:12]
    out['blossom_front_view_gap_note'] = 'standing silhouettes (clusters plus stems) of every blossom plate pair in the front view, whatever their depth row; negative values are impossible because rows differ, zero means two plates overlap in projection (the nearer hides part of the farther)'
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
    out['split'] = {'colour_rule': CFG['tree_split']['colour_rule'], 'wood_rule': CFG['tree_split']['wood_rule'], 'cluster_rule': CFG['tree_split']['cluster_rule'],
        'min_feature_rule': CFG['tree_split']['min_feature_rule'], 'dropped_petals': CFG['tree_split']['dropped_petals']}
    return out


def validate(assets, shapes, preset, items, gap, slot_gap, split):
    mind, worst, over, pairs = assembly_clearance(shapes)
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
    assert len(items) == PIECE_COUNT and sum(len(p['holes']) for p in items) == SLOT_COUNT
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
    # V7 pieces: every printed pixel inside its plate with at least 0.5 mm of
    # clear acrylic around it, the stem exactly 12.25 mm wide, minimum feature.
    for p in CFG['pieces']:
        if not p.get('split'): continue
        a = assets[p['id']]; s = shapes[p['id']]; ra = a['rasters'][0]
        pm = np.zeros(arr.shape[:2], np.uint8)
        item = next(q for q in items if q['name'] == p['id'])
        ext = np.round(np.asarray(item['poly'].exterior.coords)*PPI).astype(np.int32)
        cv2.fillPoly(pm, [ext], 1)
        x0, y0 = round(item['rasters'][0]['x']*PPI), round(item['rasters'][0]['y']*PPI)
        ink = np.zeros(arr.shape[:2], bool)
        rw, rh = round(ra['w']*PPI), round(ra['h']*PPI)
        alpha_img = np.asarray(Image.fromarray(ra['res_alpha']).resize((rw, rh), Image.BILINEAR)) > 128
        ink[y0:min(y0+rh, arr.shape[0]), x0:min(x0+rw, arr.shape[1])] = alpha_img[:max(0, min(rh, arr.shape[0]-y0)), :max(0, min(rw, arr.shape[1]-x0))]
        assert (ink & (pm == 0)).sum() == 0, (p['id'], 'ink outside the cut')
        dt = cv2.distanceTransform(pm, cv2.DIST_L2, 3)/PPI
        assert dt[ink].min() >= .5, (p['id'], 'ink closer than 0.5 mm to the cut', float(dt[ink].min()))
        nf = neck_width(s['poly'])
        assert nf is None or nf >= MIN_FEATURE_MM, (p['id'], 'minimum feature', nf)
        stats, _ = audit_path(cut_path(s['poly']))
        assert stats['segments'] <= max(100, 1.5*stats['perimeter_mm']), (p['id'], stats)
        if p['split'] == 'blossom':
            cx = s['tab_cx'][0]; half = STEM_WIDTH_MM/2
            sec = s['poly'].intersection(LineString([(cx-half-3, s['shoulder']-1.5), (cx+half+3, s['shoulder']-1.5)]))
            assert abs(sec.length-STEM_WIDTH_MM) < .01, (p['id'], 'stem width', sec.length)
            sec = s['poly'].intersection(LineString([(cx-half-3, s['shoulder']-a['split_info']['stem_length_mm']+2.5), (cx+half+3, s['shoulder']-a['split_info']['stem_length_mm']+2.5)]))
            assert sec.length >= STEM_WIDTH_MM-.01, (p['id'], 'stem top narrower than the stem', sec.length)
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
    heights = {pid: round(preset['base_thickness_mm']+assets[pid]['h']+shapes[pid]['border'], 2)
               for pid in assets if pid != 'base' and not assets[pid].get('shoulder_override')}
    for pid in assets:
        if assets[pid].get('shoulder_override'): heights[pid] = round(preset['base_thickness_mm']+shapes[pid]['poly'].bounds[3], 2)
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
        'same_row_note': f"blossom plates share rows {sorted({p['mounts_mm'][0][1] for p in CFG['pieces'] if p['id'].startswith('blossom_')})} with each other; every same-row pair of standing cuts keeps at least 2 mm",
        'art_overhang_beyond_base_mm': over,
        'front_view_coverage_pct': cov,
        'front_view_policy': CFG['front_view_policy'],
        'load_path_floor_mm': LOAD_PATH_FLOOR_MM, 'stem_width_mm': STEM_WIDTH_MM, 'minimum_feature_mm': MIN_FEATURE_MM,
        'bud_guard_risers': {p['id']: shapes[p['id']]['bud_guard']
            for p in CFG['pieces'] if shapes[p['id']]['bud_guard']},
        'blue_reference_four_sides': True, 'unprinted_tabs_and_slots': True,
        'slot_ink_clearance_checked_mm': 1.5, 'margins_nonblue_ink': True,
        'base_plate': f'supplied raster 07_base_art printed as-is, vertically centred '
                      'on a 2.5 mm clear rim; {SLOT_COUNT} slot windows ink-cleared 1.5 mm in-memory '
                      'by the builder (no separate prepared copy, no placeholder-slot surgery)',
        'piece_breakdown': {
            'backdrop': 'one plate: 05_background sky with both 06_lattice_doors islands butted against its sides (bottoms aligned), the whole 04_moon_clouds layer (both islands) registered 5 mm below the sky top; no tree printed on it (V7); 3 tabs',
            'tree': 'V7: the trunk and branches of 03_blossom_tree.png as their own cut piece (wood pixels only, blossoms removed by colour), 88 mm art rotated 35 deg clockwise, 1 tab under the trunk base behind the serpent',
            'blossom_01..07': f"V7: seven pink petal clusters as separate cut plates (1.0 mm rim, no webbing between clusters), each on a 12.25 mm clear stem and one tab, standing behind the tree piece at rows {sorted({p['mounts_mm'][0][1] for p in CFG['pieces'] if p['id'].startswith('blossom_')})}",
            'snake': '02_snake silhouette plate, 1 tab (V2/V4 position)',
            'character': '01_character silhouette plate, 1 tab; the whole 84 mm figure (no crop), boot rims on the base line, bud-guard clear riser inside the tab window between the legs (V2/V4 scale and x)'},
        'layer_order_back_to_front': ['backdrop (sky, doors, moon/clouds)'] + [f"blossom plates on row {r}" for r in sorted({p['mounts_mm'][0][1] for p in CFG['pieces'] if p['id'].startswith('blossom_')}, reverse=True)] + ['tree', 'snake', 'character'],
        'row_order_front_to_back': [p['id'] for p in sorted(CFG['pieces'], key=lambda q: q['mounts_mm'][0][1])]+['backdrop'],
        'composition': composition_report(assets, shapes, split),
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
            **({'split_info': assets[p['id']]['split_info']} if assets[p['id']].get('split_info') else {})}
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
    split = TreeSplit(CFG['tree_split'])
    base_y = None
    assets = {}
    for p in CFG['pieces']:
        if p.get('split') == 'tree':
            assets[p['id']] = load_tree(split, p)
            base_y = assets[p['id']]['art'].bounds[3]
    clusters = split.clusters()
    by_id = {c['id']: (m, i) for c, (m, i) in zip(CFG['tree_split']['clusters'], clusters)}
    for p in CFG['pieces']:
        if p.get('split') == 'blossom':
            m, i = by_id[p['id']]
            assets[p['id']] = load_blossom(split, p, m, i, base_y)
        elif not p.get('split'):
            assets[p['id']] = load_piece(p)
    reports = []
    # Scene x of every blossom tab: the stem axis computed from the cluster,
    # expressed from the base's left edge like every other mount.
    tree_mount = next(p for p in CFG['pieces'] if p['id'] == 'tree')['mounts_mm'][0][0]
    scene_left = tree_mount-assets['tree']['tab_x_mm']
    for p in CFG['pieces']:
        if p.get('split') == 'blossom':
            p['mounts_mm'] = [[round(scene_left+assets[p['id']]['split_info']['stem_x_mm'], 1), p['mounts_mm'][0][1]]]
    for preset in presets:
        folder = OUT/preset['name']; (folder/'preview').mkdir(parents=True, exist_ok=True)
        assets['base'] = load_base(preset)
        shapes = {p['id']: standee(assets[p['id']], preset['base_thickness_mm'], p['mounts_mm'], p.get('plinth_rise_mm', 8), p.get('simplify_mm', .015), p.get('clear_border_mm', CFG['clear_border_mm'])) for p in CFG['pieces']}
        items, gap, slot_gap = make_board(assets, shapes, preset, folder)
        assembly(assets, shapes, preset, folder)
        report = validate(assets, shapes, preset, items, gap, slot_gap, split); reports.append(report)
        print(json.dumps({'preset': preset['name'], 'pieces': PIECE_COUNT, 'cut_paths': CUT_PATH_COUNT,
            'same_row_mm': report['same_row_standing_clearance_mm'], 'slot_gap_mm': slot_gap,
            'coverage': report['front_view_coverage_pct'],
            'risers': report['bud_guard_risers'],
            'art': {k: round(v['w'], 1) for k, v in assets.items() if k != 'base'},
            'plate_bounds': {k: [round(x, 1) for x in v['poly'].bounds] for k, v in shapes.items()},
            'base': [round(assets['base']['w'], 1), round(assets['base']['h'], 1)]}, ensure_ascii=False), flush=True)
        prune_archive(folder, keep_preview=preset is presets[0])
    print(json.dumps({'product': CFG['product'], 'archive': [str(p.relative_to(ROOT)) for p in sorted(OUT.rglob('*')) if p.is_file()]}), flush=True)


if __name__ == '__main__':
    main()
