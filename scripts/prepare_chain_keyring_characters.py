"""Prepare the chain/stand keyring line's character sprites for printing.

Print-source policy: the OpenAPI look render (<name>__<world>_render300.png) is
the only print source. Every render300 file measured as a corner-transparent
cutout with 1-2 alpha islands, and where the ranking avatar180 pair is
pixel-identical both depict the same sprite. Several avatar180 files are NOT
cutouts (룃혜 95% opaque background canvas; 믐댕/타루카루타/안개질무렵 61-78%
opaque canvases with 95-476 effect particles), so avatar180 stays on disk as
lookup provenance and never reaches a cut piece.

Per sprite: keep the main silhouette plus detail islands within the printable
clear border at the largest print size (stand 60 mm) - the len_dot keep rule -
alpha-zero anything farther, crop to the kept-ink bbox, and NEAREST-resample to
the exact 300-ppi print height of both products so the dot grid stays crisp.
RGB bytes are untouched apart from the alpha-zeroed dropped components.
"""
from pathlib import Path
import hashlib, json, sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tmp/pylibs'))
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/chain_keyring'
PPI = 300.0
ART_H_MM = {'chain40': 40.0, 'stand60': 60.0}
CLEAR_BORDER_MM = 2.5
KEEP_MM = CLEAR_BORDER_MM - 0.1
MIN_MAIN_AREA_PX = 500

ZERO_SUFFIXLESS_MODE = {
    '마가다락방': '알파 (랭킹 스냅샷 · 현재 활성 모드는 베타)',
    '청민예': '알파 (현재 활성 모드)',
    '뿟쥐': '베타 (현재 활성 모드)',
}

POLICY = (
    '인쇄 원본은 OpenAPI look 렌더(render300) 파일뿐이다. 전원 코너 투명·섬 1~2개의 '
    '컷아웃으로 실측됐으며 랭킹 아바타180과 픽셀 동일한 캐릭터도 있다. avatar180 파일 '
    '중 룃혜(불투명 95%), 믐댕·타루카루타·안개질무렵(불투명 61~78%, 효과 파티클 '
    '95~476개)은 배경·효과 캔버스라 인쇄에 쓰지 않고 조회 근거로만 보존한다.'
)


def render_sources(applicant):
    """Print-source files in stable order: current mode first, then _alpha/_beta."""
    files = [f for ch in applicant['characters'] for f in ch['files'] if '_render300' in f]
    return sorted(files, key=lambda f: (f.count('_render300_'), f))


def mode_label(nickname, name):
    if name.endswith('_render300_alpha.png'):
        return '알파 (공식 과거 이미지)'
    if name.endswith('_render300_beta.png'):
        return '베타 (공식 이미지)'
    if nickname in ZERO_SUFFIXLESS_MODE:
        return ZERO_SUFFIXLESS_MODE[nickname]
    return '현재 모드'


def prepare_sprite(applicant, nickname, name):
    src = ASSETS / applicant / name
    im = Image.open(src).convert('RGBA')
    arr = np.asarray(im).copy()
    alpha = arr[:, :, 3] > 8
    n, labels, stats, _ = cv2.connectedComponentsWithStats(alpha.astype('uint8'), 8)
    assert n >= 2, name
    order = sorted(range(1, n), key=lambda i: -stats[i, 4])
    main = order[0]
    assert stats[main, 4] >= MIN_MAIN_AREA_PX, (name, stats[main, 4])
    ys, xs = np.nonzero(labels == main)
    h_main = int(ys.max() - ys.min() + 1)
    keep_px = KEEP_MM * h_main / ART_H_MM['stand60']
    dist = cv2.distanceTransform((labels != main).astype('uint8'), cv2.DIST_L2, 3)
    kept, dropped = [main], []
    for i in order[1:]:
        d = float(dist[labels == i].min())
        (kept if d <= keep_px else dropped).append((i, d))
    changed = 0
    for i, _ in dropped:
        changed += int((labels == i).sum())
        arr[labels == i, 3] = 0
    live = arr[:, :, 3] > 8
    ys, xs = np.nonzero(live)
    assert len(ys) > 0, name
    crop = Image.fromarray(arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    assert crop.height >= 20 and crop.width >= 10, (name, crop.size)
    outs = {}
    for tag, h_mm in ART_H_MM.items():
        th = int(round(h_mm * PPI / 25.4))
        tw = max(1, int(round(crop.width * th / crop.height)))
        out = ASSETS / applicant / 'prepared' / (name[:-4] + f'_{tag}.png')
        crop.resize((tw, th), Image.NEAREST).save(out)
        outs[tag] = [tw, th]
    return {
        'source': name,
        'mode': mode_label(nickname, name),
        'sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
        'source_px': [im.width, im.height],
        'islands': n - 1,
        'kept_islands': len(kept),
        'dropped': [{'area_px': int(stats[i, 4]),
                     'min_distance_mm': round(d * ART_H_MM['stand60'] / h_main, 3)}
                    for i, d in dropped],
        'changed_px': changed,
        'crop_px': [crop.width, crop.height],
        'outputs_px': outs,
        'resample': 'NEAREST',
    }


def main():
    manifest = json.loads((ASSETS / 'applicants.json').read_text(encoding='utf-8'))
    total = 0
    for app in manifest['applicants']:
        name = app['applicant']
        (ASSETS / name / 'prepared').mkdir(parents=True, exist_ok=True)
        sprites = []
        for ch in app['characters']:
            files = sorted((f for f in ch['files'] if '_render300' in f),
                           key=lambda f: (f.count('_render300_'), f))
            for f in files:
                sprites.append(prepare_sprite(name, ch['nickname'], f))
        total += len(sprites)
        (ASSETS / name / 'prepared' / 'provenance.json').write_text(
            json.dumps({
                'print_source_policy': POLICY,
                'keep_rule': (f'clear border {CLEAR_BORDER_MM}mm 기준, stand 60mm 스케일에서 '
                              f'{KEEP_MM}mm 이내 디테일만 유지하고 나머지는 알파 0 처리'),
                'resample': 'NEAREST (도트 그리드 보존, 업스케일 아닌 인쇄 크기 정확화)',
                'sprites': sprites,
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        trimmed = sum(s['changed_px'] for s in sprites)
        flags = [f"{s['source']}:{s['islands']}isl/{s['changed_px']}px" for s in sprites if s['changed_px'] or s['islands'] > 1]
        print(f"{name}: {len(sprites)} sprites, trimmed {trimmed}px" + (f" | {flags}" if flags else ''))
    print('TOTAL', total, 'sprites')


if __name__ == '__main__':
    main()
