"""Prepare the dot character asset for the Len Diorama DOT version.

Source: assets/len/official_avatar_180.png - the person's own MapleStory
ranking avatar render, a crisp dot sprite with decorative sparkles.

Every pixel is preserved byte-for-byte; the only change is that sparkle
components whose distance to the main figure exceeds the printable clear
border (clear_border_mm - 0.1 at the config's print scale) have their
alpha zeroed. Ink farther than the clear border from the kept silhouette
cannot print inside the cut piece, and build_len_diorama's load_asset
asserts exactly that rule, so those specks must not survive into the
print asset. Geometry/scale of the kept art are untouched.
"""
from pathlib import Path
import sys, json, hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pylibs'))
import numpy as np
import cv2
from PIL import Image

SRC = ROOT / 'assets/len/official_avatar_180.png'
DST_DIR = ROOT / 'assets/len/05_도트_캐릭터'
CFG = json.loads((ROOT / 'configs/len_diorama_dot.json').read_text(encoding='utf-8'))
FIG_ART_HEIGHT_MM = next(p['art_height_mm'] for p in CFG['pieces'] if p['id'] == 'character')
CLEAR_BORDER_MM = CFG['clear_border_mm']
KEEP_LIMIT_MM = CLEAR_BORDER_MM - 0.1

im = Image.open(SRC).convert('RGBA')
arr = np.asarray(im).copy()
alpha = (arr[..., 3] > 8).astype(np.uint8)
n, labels, stats, _ = cv2.connectedComponentsWithStats(alpha, connectivity=8)
order = sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA])
main = order[0]
mh = stats[main, cv2.CC_STAT_HEIGHT]
scale = FIG_ART_HEIGHT_MM / mh
limit_px = KEEP_LIMIT_MM / scale
main_pts = np.stack(np.nonzero(labels == main)[::-1], 1).astype(np.float32)

kept, removed = [main], []
for i in order[1:]:
    ys, xs = np.nonzero(labels == i)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    d = float(np.sqrt(((pts[:, None, :] - main_pts[None, :, :]) ** 2).sum(-1)).min())
    (kept if d < limit_px else removed).append(i)

arr[np.isin(labels, removed), 3] = 0
out = Image.fromarray(arr, 'RGBA')
DST_DIR.mkdir(parents=True, exist_ok=True)
dst = DST_DIR / '캐릭터_도트.png'
out.save(dst)

def info(i):
    return {'label': int(i),
            'bbox_px': [int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                        int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])],
            'area_px': int(stats[i, cv2.CC_STAT_AREA])}

record = {
    'source': str(SRC.relative_to(ROOT)),
    'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
    'figure_height_mm': FIG_ART_HEIGHT_MM,
    'mm_per_px': round(float(scale), 4),
    'keep_rule': f'main component + components within {KEEP_LIMIT_MM} mm of it at print scale',
    'kept_components': [info(i) for i in kept],
    'removed_components': [info(i) for i in removed],
    'removed_count': len(removed),
    'pixel_changes': 'removed-component alpha zeroed only; every other pixel byte-identical to source',
    'out': str(dst.relative_to(ROOT)),
    'out_sha256': hashlib.sha256(dst.read_bytes()).hexdigest(),
}
(DST_DIR / 'provenance.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'kept': [int(i) for i in kept], 'removed': [int(i) for i in removed],
                  'removed_count': len(removed), 'limit_px': round(float(limit_px), 2),
                  'mm_per_px': round(float(scale), 4), 'out': str(dst.relative_to(ROOT))},
                 ensure_ascii=False))
