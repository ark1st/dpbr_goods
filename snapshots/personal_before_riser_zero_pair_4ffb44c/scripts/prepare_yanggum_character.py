"""Derive the cutting alpha for the supplied yanggum JPG, pixels untouched.

The source is an opaque JPG on a pure-white studio background. The figure is
kept exactly as supplied; only a background flood-fill alpha is added, so the
cut silhouette comes from the real ink extent and the printed pixels stay the
original bytes.
"""
from pathlib import Path
import hashlib, json
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/yanggum/아크릴SD스탠드.jpg'
OUT_DIR = ROOT / 'assets/yanggum/prepared'
# Outer background is 254-255; badge whites are 202-236, so a 245 floor floods
# only the true background and keeps every enclosed light region opaque.
BG_FLOOR = 245


def background_alpha(im):
    a = np.asarray(im.convert('RGB')).astype(int)
    mn = a.min(axis=2)
    near_white = mn >= BG_FLOOR
    labels, _ = ndimage.label(near_white)
    border = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    corner = set(border.tolist()) - {0}
    reach = np.isin(labels, list(corner))
    return (~reach).astype(np.uint8) * 255


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    im = Image.open(SOURCE).convert('RGB')
    alpha = background_alpha(im)
    lab, n = ndimage.label(alpha > 8)
    sizes = ndimage.sum(alpha > 8, lab, range(1, n + 1))
    big = [i + 1 for i, s in enumerate(sizes) if s > 200]
    assert len(big) == 1, ('Expected one connected figure', [(i, int(sizes[i - 1])) for i in big])
    specks = sum(1 for s in sizes if 0 < s <= 200)
    solid = alpha > 8
    bbox = Image.fromarray(solid).getbbox()
    assert bbox == (288, 300, 1105, 1156), bbox
    out = Image.merge('RGBA', (*im.split(), Image.fromarray(alpha))).crop(bbox)
    destination = OUT_DIR / 'character_rgba.png'
    out.save(destination)
    raw = SOURCE.read_bytes()
    provenance = {
        'source_file': SOURCE.relative_to(ROOT).as_posix(),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'method': 'corner flood-fill on min(RGB)>=%d; figure kept opaque, background transparent' % BG_FLOOR,
        'rgb_pixels_modified': 0,
        'alpha_islands_over_200px': 1,
        'alpha_specks_discarded': specks,
        'crop_px': list(bbox),
        'print_note': 'RGB bytes are the supplied JPG cropped; no redraw, no retouch, no generative step.',
    }
    (OUT_DIR / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(provenance, ensure_ascii=False))


if __name__ == '__main__':
    main()
