"""Prepare the Len PAD diorama base raster for production.

Source: assets/len_pad/01_베이스.png - the supplied base plate design,
drawn with five PLACEHOLDER slot openings (the pack README states cut
lines, acrylic tabs/slots and physical dimensions are not yet fixed).
The placeholders cannot become real slots: at the 275 mm print width
their pixel size works out to about 32.5 x 4.1 mm / 23.9 x 4.1 mm,
which no repo-convention tab (18 mm wide, 3/5 mm thick) fits.

This script therefore:
1. closes the five transparent placeholder holes plus their drawn
   outline rings by mirror-transplanting the adjacent clean pattern
   strip (measured art, no interpolation - TELEA-style fills banded at
   delivery scale on this soft gradient pattern) so the printed base
   reads as one continuous decorated plate;
2. clears ink (alpha zero) inside a buffer of each of the eight REAL
   slot cut shapes defined by configs/len_diorama_pad - the buffer of
   the exact slot shape covers the builder's 1.5 mm clearance zone
   including its corner arcs, plus rasterization slack on top.

Every other pixel is byte-identical to the source. provenance.json in
assets/len_pad/prepared/ records the patch rectangles, hashes and the
change accounting. The builder embeds the prepared PNG as-is.
"""
from pathlib import Path
import sys, json, hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pylibs'))
import numpy as np
import cv2
from PIL import Image
from shapely.geometry import box

SRC = ROOT / 'assets/len_pad/01_베이스.png'
DST_DIR = ROOT / 'assets/len_pad/prepared'
CFG = json.loads((ROOT / 'configs/len_diorama_pad.json').read_text(encoding='utf-8'))
ART_W_MM, ART_H_MM = CFG['base_art_mm']
INSET_MM = CFG['base_art_inset_mm']
SLOT_L = CFG['slot_length_mm']
SLOT_R = CFG['slot_corner_radius_mm']
CLEAR_MM = 1.5          # production spec, asserted by the builder
CLIP_MM = 2.0           # buffer of the exact slot shape; 1.5 mm spec plus
                        # slack that must exceed the LANCZOS upsample transition
                        # band (~5 render px) at the window's hard alpha edge.
                        # A 0.17 mm gap let edge bleed reach the assert zone.

im = Image.open(SRC).convert('RGBA')
arr = np.asarray(im).copy()
orig = arr.copy()
H, W = arr.shape[:2]

ys, xs = np.nonzero(arr[..., 3] > 8)
x0, y0 = int(xs.min()), int(ys.min())
x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
bw, bh = x1 - x0, y1 - y0
assert abs(bw / ART_W_MM - bh / ART_H_MM) < 2e-3, (bw, bh)
PXMM = bw / ART_W_MM
print(f"plate ink bbox px=({x0},{y0},{x1},{y1}) px/mm={PXMM:.4f}")

mask = (arr[..., 3] > 8).astype(np.uint8)
cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
holes = []
for i, c in enumerate(cnts):
    if hier[0][i][3] != -1:
        area = cv2.contourArea(c)
        bx, by, bw2, bh2 = cv2.boundingRect(c)
        if area >= 500:
            holes.append((int(area), bx, by, bw2, bh2))
holes.sort(key=lambda t: (t[2], t[1]))
assert len(holes) == 5, f"expected 5 placeholder holes, found {len(holes)}: {holes}"

# Ring + lighter glow reach 8-12 px past each hole edge (measured).
MARGIN = 12
# Source strip side per hole: every strip lands in the soft gradient /
# petal-scatter zones (x fraction 0.24-0.75), away from the branch art
# (x<0.23, x>0.76) and the central emblem (x~0.50, lower band).
MIRROR_SIDE = {(298, 237): 'right', (963, 237): 'right', (1628, 237): 'left',
               (658, 403): 'right', (1334, 403): 'left'}
hole_records = []
for area, hx, hy, hw, hh in holes:
    side = MIRROR_SIDE[(hx, hy)]
    rx0, ry0 = max(0, hx - MARGIN), max(0, hy - MARGIN)
    rx1, ry1 = min(W, hx + hw + MARGIN), min(H, hy + hh + MARGIN)
    pw2 = rx1 - rx0
    if side == 'right':
        sx0, sx1 = rx1, rx1 + pw2
    else:
        sx0, sx1 = rx0 - pw2, rx0
    assert 0 <= sx0 and sx1 <= W, (hx, hy, 'source strip out of canvas')
    strip = arr[ry0:ry1, sx0:sx1].copy()
    assert (strip[..., 3] > 8).all(), (hx, hy, 'source strip is not solid ink')
    arr[ry0:ry1, rx0:rx1] = strip[:, ::-1]
    hole_records.append({'bbox_px': [hx, hy, hw, hh], 'area_px': area,
                         'patch_rect_px': [rx0, ry0, rx1, ry1],
                         'mirror_side': side,
                         'source_rect_px': [sx0, ry0, sx1, ry1]})

mask2 = (arr[..., 3] > 8).astype(np.uint8)
cnts2, hier2 = cv2.findContours(mask2, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
left = [cv2.boundingRect(c) for i, c in enumerate(cnts2)
        if hier2[0][i][3] != -1 and cv2.contourArea(c) >= 60]
assert not left, f"holes remain after inpaint: {left}"
ys2, xs2 = np.nonzero(arr[..., 3] > 8)
assert (int(xs2.min()), int(ys2.min()), int(xs2.max()) + 1, int(ys2.max()) + 1) == (x0, y0, x1, y1)

slot_records = []
max_slot_w = max(p['slot_width_mm'] for p in CFG['presets'])
def rounded_mm(cx, cy, hw, hh, r):
    return box(cx - hw + r, cy - hh + r, cx + hw - r, cy + hh + r).buffer(r, quad_segs=16)

for p in CFG['pieces']:
    for mx, my in p['mounts_mm']:
        ax_mm = mx - INSET_MM                       # cut x -> art x
        ay_mm = ART_H_MM - (my - INSET_MM)          # cut y (from front) -> art y from top
        zone = rounded_mm(ax_mm, ay_mm, SLOT_L / 2, max_slot_w / 2, SLOT_R).buffer(CLIP_MM)
        pts = np.asarray(zone.exterior.coords)
        pts[:, 0] = x0 + pts[:, 0] * PXMM
        pts[:, 1] = y0 + pts[:, 1] * PXMM
        m = np.zeros((H, W), np.uint8)
        cv2.fillPoly(m, [np.round(pts).astype(np.int32)], 1)
        arr[m > 0, 3] = 0
        slot_records.append({'piece': p['id'], 'mount_cut_mm': [mx, my],
                             'center_art_px': [round(x0 + ax_mm * PXMM, 1), round(y0 + ay_mm * PXMM, 1)],
                             'window_art_mm': [round(v, 2) for v in zone.bounds]})
assert len(slot_records) == 8, slot_records
changed_px = int((arr != orig).any(axis=-1).sum())

out = Image.fromarray(arr, 'RGBA')
DST_DIR.mkdir(parents=True, exist_ok=True)
dst = DST_DIR / '01_베이스.png'
out.save(dst, optimize=True)

record = {
    'source': str(SRC.relative_to(ROOT)),
    'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
    'out': str(dst.relative_to(ROOT)),
    'out_sha256': hashlib.sha256(dst.read_bytes()).hexdigest(),
    'why': 'pack README: cut lines / tabs / slots not yet fixed; the five drawn '
           'placeholder openings are ~32.5 x 4.1 mm (row 1) and ~23.9 x 4.1 mm '
           '(row 2) at the 275 mm print width - no 18 mm tab fits them, so the '
           'real slots are placed by configs/len_diorama_pad.json instead.',
    'placeholder_holes_closed': hole_records,
    'closure': 'mirror transplant of the adjacent clean pattern strip '
               '(measured art, no interpolation; the seam at the mirror axis '
               'is an exact continuation)',
    'real_slot_windows_cleared': slot_records,
    'slot_clearance_spec_mm': CLEAR_MM,
    'slot_clearance_clip_mm': CLIP_MM,
    'changed_pixel_count': changed_px,
    'pixel_changes': 'mirror-transplanted hole/ring fills + alpha-zeroed slot windows only; '
                     'every other pixel byte-identical to source',
}
(DST_DIR / 'provenance.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'holes_closed': len(hole_records), 'slot_windows': len(slot_records),
                  'changed_px': changed_px,
                  'out': str(dst.relative_to(ROOT)),
                  'out_sha256': record['out_sha256'][:16]}, ensure_ascii=False))
