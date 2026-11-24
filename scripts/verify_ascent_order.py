"""Check the selected 800 × 500 mm Ascent order against the 5T source plate."""
from collections import Counter, defaultdict
import json

import numpy as np
import pymupdf as fitz
from PIL import Image
from shapely import affinity
from shapely.geometry import box

from build_a3_release import ROOT, MM, extract_layers, polygon_of
from fixed_page3_checks import verify_exported_paths
from verify_laser_paths import contours

PLATE = ROOT/'output/large_format/ascent_5T_800x500'
PANELS = {'카데나':[11,12,13,14], '키네시스':[15,16,17,18], '라라':[19,10,6,7],
          '카인':[8,25,26], '렌':[9,22,27,28], '제로':[20,23,29], '엔젤릭버스터':[21,24,30]}
COUNTS = {'카데나':1, '키네시스':2, '라라':1, '카인':1, '렌':2, '제로':3, '엔젤릭버스터':1}


def thumbnail_at(image, bounds):
    """Sample at common physical coordinates regardless of the PNG pixel grid."""
    pixels_per_mm = 300 / 25.4
    crop_box = tuple(v*pixels_per_mm for v in bounds)
    # Premultiplied RGB ignores arbitrary RGB values in transparent pixels.
    # Area resampling tolerates the source image's subpixel shift on the new sheet.
    return np.asarray(image.resize((160,96), Image.Resampling.BOX, box=crop_box).convert('RGBa'), dtype=float)


def verify_source_windows(path, pieces, originals):
    """Inspect the actual PDF clipping window and unscaled transform for each image."""
    with fitz.open(path) as doc:
        page = doc[0]
        forms = page.get_xobjects()
        panels = [p for p in pieces if p['role']=='panel']
        for row in panels:
            start = fitz.Rect(*(v*MM for v in originals[row['source_id']]['placed_bounds_mm']))
            end = fitz.Rect(*(v*MM for v in row['placed_bounds_mm']))
            guard = (-.15*MM,-.15*MM,.15*MM,.15*MM)
            clipped = (start+guard)*page.transformation_matrix
            placed = (end+guard)*page.transformation_matrix
            matches = [xref for xref,_,_,bounds in forms if max(abs(v-w) for v,w in zip(bounds,placed))<.006]
            assert len(matches)==1,(row['id'],'Missing or repeated placed art')
            xref=matches[0]
            def coordinates(key):
                kind,vals=doc.xref_get_key(xref,key)
                assert kind=='array'
                return list(map(float,vals[1:-1].split()))
            assert max(abs(v-w) for v,w in zip(coordinates('BBox'),clipped,strict=True))<.006,(row['id'],'Source clip')
            matrix=coordinates('Matrix')
            assert max(abs(v-w) for v,w in zip(matrix,[1,0,0,1,end.x0-start.x0,start.y0-end.y0],strict=True))<.006,(row['id'],'Shifted or scaled art')


def verify_order(folder):
    from print_delivery import AI, PNG
    layout = json.loads((folder/'layout.json').read_text())
    source_rows = json.loads((PLATE/'validation.json').read_text())['parts']
    old = {r['id']:r for r in source_rows}
    canonical = json.loads((ROOT/'configs/ascent_5t_contours.json').read_text())['parts']
    pieces = layout['parts']
    assert len(pieces)==len({p['id'] for p in pieces})==50
    assert layout['canvas_mm']==[800,500] and layout['stock']=='5T'
    assert (layout['pieces'],layout['panels'],layout['bases'],layout['closed_contours'])==(50,39,11,138)
    sets = defaultdict(list)
    exteriors, expected = [], []
    deltas = []
    with Image.open(PLATE/PNG) as source, Image.open(folder/PNG) as final:
        source_thumbs = {cid:thumbnail_at(source,row['placed_bounds_mm']) for cid,row in old.items()}
        for row in pieces:
            cid = row['source_id']
            assert row['scale']==1 and row['rotation_degrees']==0, row['id']
            assert row['role']==('base' if int(cid.split('_')[1])<=5 else 'panel')
            sets[(row['character'],row['set_id'])].append((row.get('layer_index',0),cid))
            left, top, right, bottom = row['placed_bounds_mm']
            original = canonical[cid]
            a,b,c,d = original['source_bounds_mm']
            assert max(abs(x-y) for x,y in zip((c-a,d-b),(right-left,bottom-top)))<.002
            shapes = [affinity.translate(polygon_of(curve),left-a,top-b) for curve in original['paths']]
            outer = max(shapes,key=lambda s:s.area)
            assert box(7.998,7.998,792.002,492.002).covers(outer)
            expected.append({'expected_paths':[p.exterior.coords for p in shapes]})
            exteriors.append(outer)
            printed = thumbnail_at(final,row['placed_bounds_mm'])
            error = float(np.abs(source_thumbs[cid]-printed).mean())
            if row['role']=='base':
                assert not printed.any(), (row['id'],'Unexpected printed ink on transparent base')
            else:
                other = min(float(np.abs(reference-printed).mean()) for key,reference in source_thumbs.items() if key!=cid)
                assert error<4 and error*2<other,(row['id'],cid,'Expected original panel appearance',error,other)
            deltas.append(error)

    source_pdf=ROOT/'tmp/ascent_11_sets/01_PRINT.pdf'
    if source_pdf.is_file():
        verify_source_windows(source_pdf,pieces,old)
    assert Counter(character for character,_ in sets)==COUNTS
    for (character,set_id),ids in sets.items():
        numbers = [int(cid.split('_')[1]) for _,cid in sorted(ids)]
        assert sum(n<=5 for n in numbers)==1,(character,set_id,'Expected one 5T base')
        assert [n for n in numbers if n>5]==PANELS[character],(character,set_id,ids)
    gap = min(p.distance(q) for i,p in enumerate(exteriors) for q in exteriors[:i])
    assert gap>=9.249 and abs(gap-layout['minimum_gap_mm'])<.001,(gap,'Ascent order gap')
    margin = min(min(x,y,800-r,500-b) for x,y,r,b in (p.bounds for p in exteriors))
    assert abs(margin-layout['minimum_margin_mm'])<.001,(margin,'Ascent edge margin')
    with extract_layers(folder/AI,['LASER_CUT']) as doc:
        actual = [p for drawing in doc[0].get_drawings() for p in contours(drawing)]
        assert len(actual)==138
        verify_exported_paths({'parts':expected},actual)
    print('Ascent 11 sets: 39 art panels, 11 bases, 138 registered cut loops; '
          f'gap {gap:.3f} mm; max panel registration sample MAE {max(deltas):.3f}',flush=True)
