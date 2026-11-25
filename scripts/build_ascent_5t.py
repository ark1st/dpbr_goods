"""Generate the 800 x 500 mm Ascent source plate from the pinned unmodified art."""
import json
import re
import tempfile

from svgpathtools import parse_path, Line
import build_a3_release as sheet
from laser_paths import audit_path
from print_delivery import build_pair
from vector_utils import svg_doc, layer

ROOT = sheet.ROOT
GEOMETRY = ROOT/'configs/ascent_5t_contours.json'
OUTPUT = ROOT/'output/large_format/ascent_5T_800x500'
FIT = sheet.CONFIG['ascent_5t_migration']


def panel_path(original):
    """Extend only the four bottom anchors of the two rectangular tabs."""
    path = parse_path(original)
    bottom = max(s.end.imag for s in path)
    tip_segments = [s for s in path if isinstance(s, Line) and abs(s.start.imag-bottom)<.001
                    and abs(s.end.imag-bottom)<.001]
    assert len(tip_segments)==2 and all(abs(s.length()-FIT['tab_width_mm'])<.001 for s in tip_segments)
    shoulders = [s.start.imag for s in path if isinstance(s, Line)
                 and abs(s.end.imag-bottom)<.001 and s.start.imag < bottom-.001]
    assert len(shoulders)==2 and max(shoulders)-min(shoulders)<.001
    assert all(abs(bottom-y-3)<.001 for y in shoulders)
    tip = sum(shoulders)/2 + FIT['tab_depth_mm']
    # Replace only explicit line endpoints; keep all other original path text.
    count = 0
    def extend(match):
        nonlocal count
        if abs(float(match[2])-bottom)>.001:
            return match[0]
        count += 1
        return f'L{match[1]} {tip:.9f}'
    result = re.sub(r'L\s*([-\d.]+)\s+([-\d.]+)', extend, original)
    assert count==4
    return result


def base_paths(original):
    outer = sheet.polygon_of(original[-1])
    xmin, ymin, xmax, ymax = outer.bounds
    center_y = (ymin+ymax)/2
    half = FIT['base_size_mm'][1]/2
    length, width = sheet.len_slot_fit('5T', FIT['tab_width_mm'])
    assert [length,width]==FIT['slot_size_mm']
    slots = [sheet.polygon_of(p).centroid for p in original[:-1]]
    assert len(slots)==8
    pitch = FIT['base_slot_pitch_mm']
    # The two tabs belong to one rigid panel. The old pair stagger would
    # exceed the finished 0.05 mm thickness clearance and wedge that panel.
    ordered = sorted(slots, key=lambda c:c.y)
    target = {}
    for row in range(4):
        pair = ordered[2*row:2*row+2]
        assert abs(abs(pair[1].x-pair[0].x)-40)<.001 and abs(pair[1].y-pair[0].y)<.2
        mid_y = (pair[0].y+pair[1].y)/2 + (row-1.5)*(pitch-6)
        target.update({s:mid_y for s in pair})
    paths = []
    for p in slots:
        # A square-edged tab needs the corners of the original square slot;
        # the laser itself rounds the interior corners by about half a kerf.
        x0,x1=p.x-length/2,p.x+length/2
        y0,y1=target[p]-width/2,target[p]+width/2
        paths.append(f'M{x0:.9f} {y0:.9f} L{x1:.9f} {y0:.9f} L{x1:.9f} {y1:.9f} '
                     f'L{x0:.9f} {y1:.9f} Z')
    paths.append(f'M{xmax:.9f} {center_y-half:.9f} L{xmax:.9f} {center_y+half:.9f} '
                 f'L{xmin:.9f} {center_y+half:.9f} L{xmin:.9f} {center_y-half:.9f} Z')
    return paths


def canonical_parts():
    originals=json.loads((ROOT/'configs/individual_contours.json').read_text())['parts']
    result={}
    for n in range(1,31):
        ident=f'ascent_{n:02}'
        paths=originals[ident]['paths']
        paths=base_paths(paths) if n<=5 else [panel_path(paths[0])]
        result[ident]={'source_bounds_mm':list(sheet.polygon_of(paths[-1]).bounds),'paths':paths}
    return result


def build():
    rows=canonical_parts()
    data={'parts':rows,'source':'configs/individual_contours.json; 38 mm supports, kerf-compensated slots and 5.10 mm tabs',
          'physical_test':False}
    GEOMETRY.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    source={p['id']:p for p in sheet.ascent_parts()}
    placements=[]
    panel_height=max(r['source_bounds_mm'][3]-r['source_bounds_mm'][1]
                     for i,r in rows.items() if int(i[-2:])>5)
    for index,n in enumerate([*range(6,31),*range(1,6)]):
        p=source[f'ascent_{n:02}']
        if n<=5:
            p['art']=p['white']=None
        else:
            # In the source file the extra depth is transparent acrylic. Clip
            # artwork at the original shape before extending the cutting path.
            p['art']=sheet.clip_art(p['art'],p)
            p['white']=sheet.clip_art(p['white'],p)
        paths=[]
        for path in rows[p['id']]['paths']:
            stats,poly=audit_path(path)
            paths.append(dict(path=path,poly=poly,protected=False,deviation=0,stats=stats))
        p.update(paths=paths,poly=paths[-1]['poly'],bounds=paths[-1]['poly'].bounds)
        row,col=divmod(index,7) if n>5 else (4,n-1)
        poly,origin=sheet.rotated(p,0)
        placements.append(dict(piece=p,x=8.01+107.1*col,y=8.01+(panel_height+3.103)*row,
                               rotation=0,rotated_origin=origin,w=poly.bounds[2],h=poly.bounds[3]))
    sheet.SIZE=(800,500)
    # Write into staging so the 11-set builder can keep using the previous
    # complete source plate until every new master is ready.
    scratch=ROOT/'tmp/ascent_5t_build'
    scratch.mkdir(exist_ok=True)
    sheet.TMP=scratch
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        from pathlib import Path
        stage=Path(temp)
        sheet.write_page(stage,placements,native_ppi=300)
        # Keep full source control precision in SVG.
        curves=[sheet.transformed_cut_path(e['path'],p) for p in placements for e in p['piece']['paths']]
        xml=''.join(f'<path d="{s}" fill="none" stroke="#ff0000" stroke-width="0.001"/>' for s in curves)
        (stage/'03_CUT_ONLY.svg').write_text(svg_doc(*sheet.SIZE,layer('LASER_CUT',xml)))
        spec=json.loads((stage/'validation.json').read_text())
        spec.update(layout_method='seven-column rows, original orientation',native_artwork_pixel_exact_to_source=False,
                    print_source_retained_in_pdf=True)
        (stage/'validation.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
        for file in stage.iterdir():
            if file.name!='README.md':
                file.replace(OUTPUT/file.name)
    build_pair('alternative_800x500')


if __name__=='__main__':
    build()
