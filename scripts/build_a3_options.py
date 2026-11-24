"""Fit two mascot sets and mixed keyrings around the full-size Len diorama on A3."""
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import cv2
import numpy as np
from PIL import Image, ImageDraw
import pymupdf as fitz
from shapely import affinity
from shapely.geometry import Polygon

from build_a3_release import (ROOT, MM, extract_layers, polygon_of, transformed_cut_path,
                              shifted_poly, pdf_destination, draw_path)
from nest_contours import rotated
from pdf_layers import mark_pdf_layers

A3 = (420,297)
MARGIN = 8
GAP = 3
GROUP = 'a3_release/19_personal_fill/3T/sheet_01'
OLD = ROOT/'output'/GROUP
DEST = ROOT/'tmp/a3_options'
INDEX = ROOT/'output/a3_options'
PREVIOUS = json.loads((OLD/'validation.json').read_text())
LOGO = 'danba_logo_smooth'
LEN = 'len_pad_3T_05_safe'
LINKED = ('tuiing_01','golden_01','burnt_01','unfried_01')
FILLERS = ('danba_garam_keyring', *LINKED, 'mascot_blue_keyring',
           'danba_danpaengi_keyring', LOGO)

@lru_cache(None)
def asset(name):
    if name in ('danba_garam_keyring','danba_danpaengi_keyring'):
        return danba_assets()[name]
    if name.startswith('mascot_'):
        return mascot_assets()[name]
    folder=ROOT/'output/individual_assets'/name
    paths=[e.attrib['d'] for e in ET.parse(folder/'03_CUT_ONLY.svg').iter() if e.tag.endswith('}path')]
    poly=max((polygon_of(p) for p in paths),key=lambda s:s.area)
    source_bounds=json.loads((folder/'asset.json').read_text())['source_bounds_mm']
    return dict(id=name,paths=paths,poly=poly,bounds=poly.bounds,art=fitz.open(folder/'01_PRINT.pdf'),source_bounds_mm=source_bounds)

@lru_cache(None)
def mascot_assets():
    from mascot_parts import mascot_pieces
    return mascot_pieces()

@lru_cache(None)
def danba_assets():
    from danba_character_keyrings import garam_danpaengi_pieces
    return garam_danpaengi_pieces()

class Sheet:
    def __init__(self):
        self.saved=[]
        self.shapes=[max((Polygon(p) for p in row['expected_paths']),key=lambda q:q.area)
                     for row in PREVIOUS['parts']]
        self.grid=0.6
        self.occupied=Image.new('L',(math.floor((A3[0]-2*MARGIN)/self.grid)+1,math.floor((A3[1]-2*MARGIN)/self.grid)+1))
        for q in self.shapes:self.mark(q)

    def mark(self,q):
        b=q.buffer(GAP+.25)
        ImageDraw.Draw(self.occupied).polygon([((x-MARGIN)/self.grid,(y-MARGIN)/self.grid) for x,y in b.exterior.coords],fill=1)

    def add(self, name, angles, filler=False):
        p=asset(name);occ=np.asarray(self.occupied,dtype=np.float32);opts=[]
        for angle in angles:
            poly,origin=rotated(p,angle);w,h=poly.bounds[2:];g=self.grid
            mask=Image.new('L',(math.ceil(w/g)+1,math.ceil(h/g)+1))
            ImageDraw.Draw(mask).polygon([(x/g,y/g) for x,y in poly.exterior.coords],fill=1)
            if mask.width>occ.shape[1] or mask.height>occ.shape[0]:continue
            match=cv2.matchTemplate(occ,np.asarray(mask,dtype=np.float32),cv2.TM_CCORR)
            ys,xs=np.where(match<.15)
            if not len(xs):continue
            scores=(ys*g+h)+.003*(xs*g+w)
            for i in np.argsort(scores)[:8]:
                opts.append((scores[i],angle,float(xs[i]*g+MARGIN),float(ys[i]*g+MARGIN),poly,origin))
        for _,angle,x,y,poly,origin in sorted(opts,key=lambda c:c[:4]):
            q=affinity.translate(poly,x,y)
            if min((q.distance(v) for v in self.shapes),default=100)<GAP:continue
            self.shapes.append(q);self.mark(q)
            self.saved.append(dict(id=name,filler=filler,x=x,y=y,rotation=angle,w=poly.bounds[2],h=poly.bounds[3],rotated_origin=origin))
            return True
        return False

    def fill(self):
        angles=range(0,360,15)
        for name in FILLERS:
            assert self.add(name,angles,filler=True),f'Missing first copy of {name}'
        # Reserve one of every requested family first, then dedicate the usable
        # space to regular G-hood mascot keyrings. Smaller originals can still
        # occupy narrow pockets where the hood outline cannot fit.
        for name in ('mascot_blue_keyring', 'danba_danpaengi_keyring', LOGO):
            for step in (15, 5):
                while self.add(name,range(0,360,step),filler=True):
                    pass


def write_json(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def export(key,sheet):
    out=DEST/key;out.mkdir(parents=True,exist_ok=True)
    index=INDEX/key;index.mkdir(parents=True,exist_ok=True)
    docs={n:fitz.open() for n in ['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT']}
    for doc in docs.values():doc.new_page(width=A3[0]*MM,height=A3[1]*MM)
    art,blue,cut=[d[0] for d in docs.values()]
    original=extract_layers(OLD/'02_MASTER.pdf',['PRINT_ARTWORK'])
    art.show_pdf_page(art.rect,original,0)
    oldcut=fitz.open(OLD/'03_CUT_ONLY.pdf')
    cut.show_pdf_page(cut.rect,oldcut,0)
    rows=PREVIOUS['parts'][:]
    original_blue=extract_layers(OLD/'02_MASTER.pdf',['CORNER_REFERENCE'])
    blue.show_pdf_page(blue.rect,original_blue,0)
    filler_counts=Counter()
    for pos in sheet.saved:
        name=pos['id'];p=asset(name);place={**pos,'piece':p}
        b=p['bounds'];pad=.15
        clip=fitz.Rect(*[(v+delta)*MM for v,delta in zip(b,(-pad,-pad,pad,pad))])
        if p.get('art') is not None and p['art'][0].get_contents():
            art.show_pdf_page(pdf_destination(place,pad),p['art'],0,clip=clip,rotate=pos['rotation'])
        paths=[transformed_cut_path(path,place) for path in p['paths']]
        for path in paths:draw_path(cut,path)
        ident=name
        if pos['filler']:
            filler_counts[name]+=1
            ident=f'fill_{name}_{filler_counts[name]:02}'
        rows.append(dict(id=ident,canonical_id=name,source_bounds_mm=p['source_bounds_mm'],
                    rotated_origin_mm=pos['rotated_origin'],scale=1,rotation_degrees=pos['rotation'],
                    placed_bounds_mm=list(shifted_poly(p['poly'],place).bounds),
                    path_count=len(paths),expected_paths=[list(polygon_of(s).exterior.coords) for s in paths]))
    def combined(names):
        d=fitz.open();pg=d.new_page(width=art.rect.width,height=art.rect.height);streams={}
        for n in names:
            oc=d.add_ocg(n,on=True)
            pg.show_pdf_page(pg.rect,docs[n],0)
            streams[oc]=[d.xref_stream(pg.get_contents()[-1])]
        mark_pdf_layers(pg,streams)
        return d
    printdoc=combined(['PRINT_ARTWORK','CORNER_REFERENCE'])
    printdoc.save(out/'01_PRINT.pdf',deflate=True,garbage=4,no_new_id=True)
    printdoc[0].get_pixmap(dpi=300,alpha=True).save(out/'01_PRINT_300ppi.png')
    master=combined(docs);master.save(out/'02_MASTER.pdf',garbage=4,deflate=True,no_new_id=True)
    docs['LASER_CUT'].save(out/'03_CUT_ONLY.pdf',garbage=4,deflate=True,no_new_id=True)
    review=fitz.open();pg=review.new_page(width=art.rect.width,height=art.rect.height);pg.show_pdf_page(pg.rect,printdoc,0)
    for row in rows:
        for loop in row['expected_paths']:
            pg.draw_polyline([(x*MM,y*MM) for x,y in loop],closePath=True,color=(1,0,0),width=.12*MM)
    pg.get_pixmap(dpi=100).save(index/'preview.png')
    gap=min(q.distance(r) for i,q in enumerate(sheet.shapes) for r in sheet.shapes[:i])
    assert gap>=GAP-.002
    spec=dict(canvas_mm=list(A3),pieces=len(rows),closed_contours=sum(r['path_count'] for r in rows),parts=rows,minimum_gap_mm=gap)
    write_json(out/'validation.json',spec)
    summary=dict(stock='3T',canvas_mm=list(A3),pieces=len(rows),closed_contours=spec['closed_contours'],danba_keyrings=filler_counts[LOGO],filler_counts=dict(filler_counts),
                 minimum_gap_mm=gap,physical_fit_test=False,ids=[r['id'] for r in rows])
    summary['parts']=[{k:r[k] for k in ['id','source_bounds_mm','rotated_origin_mm','placed_bounds_mm','rotation_degrees','scale','path_count']} | {'canonical_id':r.get('canonical_id',r['id'])} for r in rows]
    summary['additional_source_paths']={name:p['paths'] for name,p in (mascot_assets() | danba_assets()).items()}
    write_json(index/'layout.json',summary)
    print(key,len(rows),'fill',dict(filler_counts),'gap',round(gap,4),flush=True)

def make():
    alt=Sheet()
    assert alt.add(LEN,range(0,360,15))
    for name in sorted(mascot_assets(),key=lambda n:asset(n)['poly'].area,reverse=True):
        assert alt.add(name,range(0,360,10)),f'No 1:1 placement for {name}'
    alt.fill()
    export('alternative/page_04',alt)

if __name__=='__main__':make()
