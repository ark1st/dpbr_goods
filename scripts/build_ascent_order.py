"""Repeat the ordered Ascent artwork and its reviewed 5T mounting interfaces at 1:1."""
import itertools
import json

import pymupdf as fitz
from shapely import affinity

from build_a3_release import ROOT, MM, draw_path, extract_layers, polygon_of, transformed_cut_path
from pdf_layers import mark_pdf_layers
from print_delivery import build_pair

SOURCE = ROOT / 'output/large_format/ascent_5T_800x500'
WORK = ROOT / 'tmp/ascent_11_sets'
DELIVERY = ROOT / 'output/print_delivery/ascent_11_sets'
WIDTH, HEIGHT = 800, 500
GAP = 9.25
# Print panels in the recorded assembly order for each character.
ORDER = [
    ('cadena', '카데나', 1, (11, 12, 13, 14)),
    ('kinesis', '키네시스', 2, (15, 16, 17, 18)),
    ('lara', '라라', 1, (19, 10, 6, 7)),
    ('kain', '카인', 1, (8, 25, 26)),
    ('ren', '렌', 2, (9, 22, 27, 28)),
    ('zero', '제로', 3, (20, 23, 29)),
    ('angelic_buster', '엔젤릭버스터', 1, (21, 24, 30)),
]


def ordered_parts():
    panels, bases = [], []
    for slug, character, copies, layers in ORDER:
        for copy in range(1, copies + 1):
            ident = f'{slug}_{copy:02}'
            common = {'set_id': ident, 'character': character}
            for layer_index, source in enumerate(layers, 1):
                panels.append(dict(common, id=f'{ident}_panel_{layer_index}', role='panel',
                                   layer_index=layer_index, source_id=f'ascent_{source:02}'))
            bases.append(dict(common, id=f'{ident}_base', role='base', source_id='ascent_01'))
    assert (len(panels), len(bases)) == (39, 11)
    return panels, bases


def arrange(canonical):
    panels, bases = ordered_parts()
    def bounds(row):
        return canonical[row['source_id']]['source_bounds_mm']
    column_width = max(bounds(row)[2] - bounds(row)[0] for row in panels + bases)
    left = (WIDTH - (7 * column_width + 6 * GAP)) / 2
    rows = []
    outlines = []
    for column in range(7):
        parts = panels[column*6:(column+1)*6] + (bases[column:column+1] if column<6 else bases[6:])
        height = sum(bounds(part)[3]-bounds(part)[1] for part in parts) + GAP*(len(parts)-1)
        x = left + column*(column_width+GAP)
        y = (HEIGHT-height)/2
        for row in parts:
            b = bounds(row)
            paths = canonical[row['source_id']]['paths']
            outer = max(map(polygon_of, paths), key=lambda p:p.area)
            shape = affinity.translate(outer, xoff=x-b[0], yoff=y-b[1])
            outlines.append(shape)
            rows.append(dict(row, source_bounds_mm=b, placed_bounds_mm=list(shape.bounds),
                             rotated_origin_mm=[0,0], rotation_degrees=0, scale=1, path_count=len(paths)))
            y += b[3]-b[1]+GAP
    gap = min(a.distance(b) for a,b in itertools.combinations(outlines, 2))
    border = min(min(x,y,WIDTH-r,HEIGHT-b) for x,y,r,b in (p.bounds for p in outlines))
    assert gap >= GAP-.0001 and border >= 8
    return rows, gap, border


def new_doc():
    doc = fitz.open()
    doc.new_page(width=WIDTH*MM, height=HEIGHT*MM)
    return doc


def layered(groups):
    result = new_doc()
    page = result[0]
    streams = {}
    visible, hidden = [], []
    for name, doc in groups:
        show = name != 'WHITE_INK_MASK'
        ocg = result.add_ocg(name, on=show)
        (visible if show else hidden).append(ocg)
        page.show_pdf_page(page.rect, doc, 0)
        streams[ocg] = [result.xref_stream(page.get_contents()[-1])]
    mark_pdf_layers(page, streams)
    result.set_layer(-1, basestate='OFF',on=visible,off=hidden)
    return result


def write_preview(rows, canonical):
    """Draw assembly labels in the gutters of the separate on-screen proof."""
    with fitz.open(WORK/'01_PRINT.pdf') as printed, new_doc() as review:
        page = review[0]
        page.show_pdf_page(page.rect, printed, 0)
        for row in rows:
            x, y, right, bottom = row['placed_bounds_mm']
            place = {'piece': {'bounds':row['source_bounds_mm']}, 'x':x, 'y':y, 'rotation':0}
            for path in canonical[row['source_id']]['paths']:
                draw_path(page, transformed_cut_path(path,place), width=.2)
            copy = int(row['set_id'].rsplit('_',1)[-1])
            layer = f"판 {row['layer_index']}" if row['role']=='panel' else '받침'
            label = f"{row['character']} {copy} · {layer}"
            rect = fitz.Rect(x*MM,(bottom+.4)*MM,right*MM,(bottom+8.1)*MM)
            page.insert_textbox(rect, label, fontname='korea-s', fontsize=11,
                                color=(.10,.17,.22), align=fitz.TEXT_ALIGN_CENTER)
        page.get_pixmap(dpi=96).save(DELIVERY/'preview.png')


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    DELIVERY.mkdir(parents=True, exist_ok=True)
    canonical = json.loads((ROOT/'configs/ascent_5t_contours.json').read_text())['parts']
    old_parts = {p['id']: p for p in json.loads((SOURCE/'validation.json').read_text())['parts']}
    rows, gap, border = arrange(canonical)
    art, white, cut = new_doc(), new_doc(), new_doc()
    with fitz.open(SOURCE/'01_PRINT.pdf') as src_art, fitz.open(SOURCE/'04_WHITE_INK_MASK.pdf') as src_white:
        for row in rows:
            name = row['source_id']
            x,y = row['placed_bounds_mm'][:2]
            place = {'piece': {'bounds': row['source_bounds_mm']}, 'x':x, 'y':y, 'rotation':0}
            for path in canonical[name]['paths']:
                draw_path(cut[0], transformed_cut_path(path, place))
            if row['role'] == 'base':
                continue
            source = old_parts[name]
            assert source['rotation_degrees']==0 and source['scale']==1
            # All old outer contours are separated by >3 mm. A 0.15 mm guard
            # retains the full source print at edges while excluding adjacent art.
            s = fitz.Rect(*(v*MM for v in source['placed_bounds_mm']))
            s += (-.15*MM,-.15*MM,.15*MM,.15*MM)
            dx = (x-source['placed_bounds_mm'][0])*MM
            dy = (y-source['placed_bounds_mm'][1])*MM
            dest = s + (dx,dy,dx,dy)
            art[0].show_pdf_page(dest, src_art, 0, clip=s)
            if src_white[0].get_contents():
                white[0].show_pdf_page(dest, src_white, 0, clip=s)
    blue = extract_layers(SOURCE/'02_MASTER.pdf',['CORNER_REFERENCE'])
    print_groups = [('PRINT_ARTWORK',art),('CORNER_REFERENCE',blue)]
    with layered(print_groups) as printed:
        printed.save(WORK/'01_PRINT.pdf',garbage=4,deflate=True,no_new_id=True)
        printed[0].get_pixmap(dpi=300,alpha=True).save(WORK/'01_PRINT_300ppi.png')
    with layered(print_groups+[('LASER_CUT',cut),('WHITE_INK_MASK',white)]) as master:
        master.save(WORK/'02_MASTER.pdf',garbage=4,deflate=True,no_new_id=True)
    cut.save(WORK/'03_CUT_ONLY.pdf',garbage=4,deflate=True,no_new_id=True)
    report = {'canvas_mm':[WIDTH,HEIGHT], 'stock':'5T','pieces':len(rows),
              'closed_contours':sum(r['path_count'] for r in rows),'panels':39,'bases':11,
              'minimum_gap_mm':gap,'minimum_margin_mm':border,'parts':rows,'physical_fit_test':False}
    (DELIVERY/'layout.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    build_pair('ascent_11_sets')
    write_preview(rows, canonical)
    print(f"{len(rows)} pieces; minimum gap {gap:.4f} mm; edge {border:.4f} mm", flush=True)


if __name__ == '__main__':
    build()
