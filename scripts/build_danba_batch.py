"""Nest full-scale Danba keyrings and export the registered A3 print and cutter files."""
import itertools
import json
import math

import pymupdf as fitz
from danba_character_keyrings import garam_danpaengi_pieces

from build_a3_release import ROOT, MM, draw_path, extract_layers, polygon_of, transformed_cut_path
from nest_contours import rotated
from pdf_layers import mark_pdf_layers
from print_delivery import build_pair

KEY = 'danba_keyrings'
WORK = ROOT/'tmp'/KEY
OUT = ROOT/'output/print_delivery'/KEY
SOURCE = ROOT/'output/individual_assets/danba_logo_smooth'
GUIDE = ROOT/'output/a3_release/19_personal_fill/3T/sheet_01/02_MASTER.pdf'
WIDTH, HEIGHT = 420., 297.
MARGIN, GAP = 8., 4.


LOGO='danba_mass_contour'


def sources():
    pieces=garam_danpaengi_pieces().copy()
    config=json.loads((ROOT/'configs/danba_mass_contour.json').read_text())
    hole,outer=map(polygon_of,config['paths'])
    assert outer.contains(hole) and outer.boundary.distance(hole.boundary)>=2.998
    pieces[LOGO]=dict(id=LOGO,paths=config['paths'],poly=outer,bounds=outer.bounds,
                      art=fitz.open(SOURCE/'01_PRINT.pdf'), white=fitz.open(SOURCE/'04_WHITE_INK_MASK.pdf'))
    return pieces


def arrange(pieces, plan):
    """Replay the selected nesting result in source coordinates without refitting."""
    placements=[]
    for row in plan['placements']:
        piece=pieces[row['source_id']]
        _,origin=rotated(piece,row['rotation'])
        placements.append(dict(piece=piece,x=row['x'],y=row['y'],rotation=row['rotation'],
                               rotated_origin=origin))
    return placements


def new_page():
    doc=fitz.open()
    doc.new_page(width=WIDTH*MM,height=HEIGHT*MM)
    return doc


def compose(docs):
    result=new_page();page=result[0];groups={}
    for name,doc in docs.items():
        oc=result.add_ocg(name,on=name!='WHITE_INK_MASK')
        page.show_pdf_page(page.rect,doc,0)
        groups[oc]=[result.xref_stream(page.get_contents()[-1])]
    mark_pdf_layers(page,groups)
    return result


def place_art(page,source,place):
    """Rotate the entire source canvas about the same point as the vector paths."""
    angle=place['rotation']
    bounds=place['piece']['bounds']
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    dx=place['x']-place['rotated_origin'][0];dy=place['y']-place['rotated_origin'][1]
    corners=[((c*(x-bounds[0])+s*(y-bounds[1])+dx)*MM,
              (-s*(x-bounds[0])+c*(y-bounds[1])+dy)*MM)
             for x in (0,source[0].rect.width/MM) for y in (0,source[0].rect.height/MM)]
    xx,yy=zip(*corners)
    page.show_pdf_page(fitz.Rect(min(xx),min(yy),max(xx),max(yy)),source,0,rotate=angle)


def build():
    pieces=sources()
    plan=json.loads((ROOT/'configs/danba_batch_placements.json').read_text())
    places=arrange(pieces,plan)
    WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    docs={'PRINT_ARTWORK':new_page(),'CORNER_REFERENCE':extract_layers(GUIDE,['CORNER_REFERENCE']),
          'LASER_CUT':new_page(),'WHITE_INK_MASK':new_page()}
    rows=[];shapes=[]
    for index,p in enumerate(places,1):
        piece=p['piece']
        place_art(docs['PRINT_ARTWORK'][0],piece['art'],p)
        if piece.get('white') is not None:
            place_art(docs['WHITE_INK_MASK'][0],piece['white'],p)
        cut_paths=[transformed_cut_path(path,p) for path in piece['paths']]
        for path in cut_paths:draw_path(docs['LASER_CUT'][0],path)
        shape=polygon_of(cut_paths[-1]);shapes.append(shape)
        rows.append(dict(id=f'{piece["id"]}_{index:03}',canonical_id=piece['id'],
                         source_bounds_mm=list(piece['bounds']),placed_bounds_mm=list(shape.bounds),
                         rotated_origin_mm=list(p['rotated_origin']),rotation_degrees=p['rotation'],
                         scale=1,path_count=2))
    gap=min(p.distance(q) for p,q in itertools.combinations(shapes,2))
    border=min(min(x,y,WIDTH-r,HEIGHT-b) for x,y,r,b in (shape.bounds for shape in shapes))
    assert gap>=GAP and border>=MARGIN-.0001
    printed=compose({n:docs[n] for n in ('PRINT_ARTWORK','CORNER_REFERENCE')})
    printed.save(WORK/'01_PRINT.pdf',garbage=4,deflate=True,no_new_id=True)
    printed[0].get_pixmap(dpi=300,alpha=True).save(WORK/'01_PRINT_300ppi.png')
    docs['LASER_CUT'].save(WORK/'03_CUT_ONLY.pdf',garbage=4,deflate=True,no_new_id=True)
    compose(docs).save(WORK/'02_MASTER.pdf',garbage=4,deflate=True,no_new_id=True)
    preview=new_page();pg=preview[0];pg.show_pdf_page(pg.rect,printed,0)
    for p in places:
        for path in p['piece']['paths']:draw_path(pg,transformed_cut_path(path,p),width=.23)
    pg.get_pixmap(dpi=110).save(OUT/'preview.png')
    counts={key:sum(r['canonical_id']==key for r in rows) for key in pieces}
    assert counts==plan['order_counts']
    spec=dict(canvas_mm=[WIDTH,HEIGHT],stock='3T',pieces=len(rows),closed_contours=2*len(rows),
              minimum_gap_mm=gap,minimum_margin_mm=border,counts=counts,
              physical_cut_test=False,parts=rows,
              fit_method=plan['method'],
              white_ink_policy='Supplied white on logo; generate the character underbase from art alpha in RIP.',
              optimum_proven=False)
    (OUT/'layout.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    build_pair(KEY)
    print('Danba keyrings:',counts,'gap:',gap,'edge:',border,flush=True)


if __name__=='__main__':
    build()
