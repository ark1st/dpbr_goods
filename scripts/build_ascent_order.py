"""Repeat the ordered Ascent artwork and its reviewed 5T mounting interfaces at 1:1."""
import itertools
import json
import shutil

import pymupdf as fitz
from shapely import affinity

from build_a3_release import ROOT, MM, draw_path, extract_layers, polygon_of, transformed_cut_path
from pdf_layers import mark_pdf_layers
from print_delivery import build_pair
from source_cache import cached_input

WORK = ROOT / 'tmp/ascent_11_sets'
DELIVERY = ROOT / 'output/print_delivery/ascent_11_sets'
WIDTH, HEIGHT = 800, 500
# Use the approved order as the registration template for its replacement cuts.
# Its layer-separated press artwork and placement record remain reproducible
# even after the 30-piece reference plate is re-packed.
APPROVED_REVISION = '4387390b3247a51dd35d741397e597f344055219'
APPROVED_INPUTS = {
    '01_PRINT_300ppi.png': 'a2a36c2cf96f5d78ac0b5de6c7f9d64f178dfa59147900973d7068840e0aac4b',
    'layout.json': '822ff3febc168a08ae879bff1fa926511c1ade5b3df9949efa507b6a32f0fd5c',
    '03_COMBINED_MASTER.ai': 'cfa267f37ab726749422df5a3bad52b2dd016f68777e11fcd8954c1df3a9fcba',
}
MIN_GAP = 7.15


def approved_file(name):
    return cached_input({'file': (DELIVERY / name).relative_to(ROOT).as_posix(),
                         'commit': APPROVED_REVISION, 'sha256': APPROVED_INPUTS[name]})


def registered_rows(canonical):
    approved = json.loads(approved_file('layout.json').read_text())['parts']
    rows, outlines = [], []
    for previous in approved:
        part = canonical[previous['source_id']]
        previous_box = previous['source_bounds_mm']
        placed = previous['placed_bounds_mm']
        xshift, yshift = placed[0] - previous_box[0], placed[1] - previous_box[1]
        outer = max(map(polygon_of, part['paths']), key=lambda p: p.area)
        outline = affinity.translate(outer, xoff=xshift, yoff=yshift)
        outlines.append(outline)
        rows.append(dict(previous, source_bounds_mm=part['source_bounds_mm'],
                         placed_bounds_mm=list(outline.bounds), path_count=len(part['paths'])))
    gap = min(a.distance(b) for a,b in itertools.combinations(outlines, 2))
    border = min(min(x,y,WIDTH-r,HEIGHT-b) for x,y,r,b in (p.bounds for p in outlines))
    assert gap >= MIN_GAP-.001 and border >= 8, (gap, border)
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
    rows, gap, border = registered_rows(canonical)
    cut = new_doc()
    for row in rows:
        x, y = row['placed_bounds_mm'][:2]
        place = {'piece': {'bounds': row['source_bounds_mm']}, 'x':x, 'y':y, 'rotation':0}
        for path in canonical[row['source_id']]['paths']:
            draw_path(cut[0], transformed_cut_path(path, place))
    master_path = approved_file('03_COMBINED_MASTER.ai')
    art = extract_layers(master_path, ['PRINT_ARTWORK'])
    white = extract_layers(master_path, ['WHITE_INK_MASK'])
    blue = extract_layers(master_path, ['CORNER_REFERENCE'])
    print_groups = [('PRINT_ARTWORK',art),('CORNER_REFERENCE',blue)]
    with layered(print_groups) as printed:
        printed.save(WORK/'01_PRINT.pdf',garbage=4,deflate=True,no_new_id=True)
    shutil.copyfile(approved_file('01_PRINT_300ppi.png'), WORK/'01_PRINT_300ppi.png')
    with layered(print_groups+[('LASER_CUT',cut),('WHITE_INK_MASK',white)]) as master:
        master.save(WORK/'02_MASTER.pdf',garbage=4,deflate=True,no_new_id=True)
    cut.save(WORK/'03_CUT_ONLY.pdf',garbage=4,deflate=True,no_new_id=True)
    report = {'canvas_mm':[WIDTH,HEIGHT], 'stock':'5T','pieces':len(rows),
              'registered_print_revision':APPROVED_REVISION,
              'closed_contours':sum(r['path_count'] for r in rows),'panels':39,'bases':11,
              'minimum_gap_mm':gap,'minimum_margin_mm':border,'parts':rows,'physical_fit_test':False}
    (DELIVERY/'layout.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    build_pair('ascent_11_sets')
    write_preview(rows, canonical)
    print(f"{len(rows)} pieces; minimum gap {gap:.4f} mm; edge {border:.4f} mm", flush=True)


if __name__ == '__main__':
    build()
