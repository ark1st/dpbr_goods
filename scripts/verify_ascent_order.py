"""Check the selected 800 × 500 mm Ascent order against the 5T source plate."""
from collections import Counter, defaultdict
import json

import numpy as np
from PIL import Image
from shapely import affinity
from shapely.geometry import LineString, box

from build_a3_release import ROOT, extract_layers, polygon_of
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


def verify_mounts(actual, pieces, approved):
    polygons = [polygon_of(curve) for curve in actual]
    for row in pieces:
        x, y, right, bottom = row['placed_bounds_mm']
        region = box(x-.002, y-.002, right+.002, bottom+.002)
        cuts = [p for p in polygons if region.covers(p)]
        assert len(cuts)==row['path_count'], row['id']
        if row['role']=='base':
            holes = sorted(cuts, key=lambda p: p.area)[:-1]
            assert len(holes)==8
            in_rows = sorted(holes, key=lambda p: p.centroid.y)
            for first,second in zip(in_rows[::2],in_rows[1::2],strict=True):
                assert abs(first.centroid.y-second.centroid.y)<.002, (row['id'],'Slot axes disagree')
                assert abs(abs(first.centroid.x-second.centroid.x)-40)<.002, (row['id'],'Slot pitch')
                ycenter = (first.centroid.y+second.centroid.y)/2
                for hole in (first,second):
                    # The outline kerf trims each 20 mm tab to 19.8 mm. Both
                    # cut slots must admit the square 5T panel without twisting.
                    cx = hole.centroid.x
                    tab = box(cx-9.9,ycenter-2.5,cx+9.9,ycenter+2.5)
                    kerf_opening = hole.buffer(.10)
                    assert kerf_opening.covers(tab) and tab.distance(kerf_opening.boundary)>.024, row['id']
            for hole in holes:
                l,t,r,b = hole.bounds
                assert abs((r-l)-19.8)<.002 and abs((b-t)-4.85)<.002, row['id']
        else:
            panel, = cuts
            shoulder = approved[row['id']]['placed_bounds_mm'][3] - 3
            assert abs(panel.bounds[3]-shoulder-5.10)<.002, row['id']
            for depth in (.05,5.05):
                section = panel.intersection(LineString([(x-1,shoulder+depth),(right+1,shoulder+depth)]))
                spans = list(section.geoms) if section.geom_type=='MultiLineString' else [section]
                assert len(spans)==2 and all(abs(span.length-20)<.002 for span in spans), row['id']


def verify_order(folder):
    from build_ascent_order import approved_file, APPROVED_INPUTS, APPROVED_REVISION
    from print_delivery import AI, PNG, sha
    layout = json.loads((folder/'layout.json').read_text())
    source_rows = json.loads((PLATE/'validation.json').read_text())['parts']
    old = {r['id']:r for r in source_rows}
    canonical = json.loads((ROOT/'configs/ascent_5t_contours.json').read_text())['parts']
    pieces = layout['parts']
    approved = {p['id']:p for p in json.loads(approved_file('layout.json').read_text())['parts']}
    assert layout['registered_print_revision']==APPROVED_REVISION
    assert sha(folder/PNG)==APPROVED_INPUTS[PNG], 'Approved production print changed'
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
            previous = approved[row['id']]
            assert previous['source_id']==cid and all(abs(v-w)<.002 for v,w in zip(
                previous['placed_bounds_mm'][:3], row['placed_bounds_mm'][:3])), (row['id'],'Print registration shifted')
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

    assert Counter(character for character,_ in sets)==COUNTS
    for (character,set_id),ids in sets.items():
        numbers = [int(cid.split('_')[1]) for _,cid in sorted(ids)]
        assert sum(n<=5 for n in numbers)==1,(character,set_id,'Expected one 5T base')
        assert [n for n in numbers if n>5]==PANELS[character],(character,set_id,ids)
    gap = min(p.distance(q) for i,p in enumerate(exteriors) for q in exteriors[:i])
    assert gap>=7.149 and abs(gap-layout['minimum_gap_mm'])<.001,(gap,'Ascent order gap')
    margin = min(min(x,y,800-r,500-b) for x,y,r,b in (p.bounds for p in exteriors))
    assert abs(margin-layout['minimum_margin_mm'])<.001,(margin,'Ascent edge margin')
    with extract_layers(folder/AI,['LASER_CUT']) as doc:
        actual = [p for drawing in doc[0].get_drawings() for p in contours(drawing)]
        assert len(actual)==138
        verify_exported_paths({'parts':expected},actual)
        verify_mounts(actual,pieces,approved)
    print('Ascent 11 sets: 39 art panels, 11 bases, 138 registered cut loops; '
          f'gap {gap:.3f} mm; max panel registration sample MAE {max(deltas):.3f}',flush=True)
