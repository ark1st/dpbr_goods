"""Repack existing artwork at 1:1 onto A3; never shrink mechanical interfaces.

Every piece carries its print, white and cut data through the SAME rigid map.
Protected contours are copied as curves, not refitted. Only dense owned Len
contours are fitted through laser_paths. Original inputs remain recoverable.
"""
from pathlib import Path
from io import BytesIO
import sys, json, math, hashlib, subprocess, zipfile, shutil, random
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np
import pymupdf as fitz
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject
from shapely.geometry import Polygon, box
from shapely import affinity
from svgpathtools import parse_path, Line, CubicBezier
from laser_paths import audit_path, cut_path, flatten_cubic
from verify_laser_paths import contours
from vector_utils import runvc, svg_doc, layer
from pdf_layers import mark_pdf_layers
from source_cache import source_path, restore_inputs
from nest_contours import rotated,contour_nest

MM=72/25.4
CONFIG=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))
SIZE=tuple(CONFIG['canvas_mm'])
MARGIN=CONFIG['page_margin_mm']
GAP=CONFIG['piece_gap_mm']
OUT=ROOT/'output/a3_release'
TMP=ROOT/'tmp/a3_release'
TMP.mkdir(parents=True,exist_ok=True)

def extract_layers(path,names):
    """Remove excluded OCG operators/forms, preserving the source page matrix."""
    r=PdfReader(path);w=PdfWriter();p=w.add_page(r.pages[0])
    props=p['/Resources'].get('/Properties',{})
    stack=[];ops=[]
    for a,op in p.get_contents().operations:
        if op==b'BDC' and a[0]=='/OC':
            stack.append(str(props[a[1]].get_object()['/Name']) in names)
        elif op==b'EMC' and stack:stack.pop()
        elif all(stack):ops.append((a,op))
    c=ContentStream(None,w);c.operations=ops;p.replace_contents(c)
    p['/Resources'].pop(NameObject('/Properties'),None)
    forms=p['/Resources'].get('/XObject',{})
    used={str(a[0]) for a,op in ops if op==b'Do'}
    for key in list(forms):
        if str(key) not in used:del forms[key]
    w.compress_identical_objects(remove_unreferenced=True)
    b=BytesIO();w.write(b)
    return fitz.open(stream=b.getvalue(),filetype='pdf')

def polygon_of(path):
    pts=[]
    for s in parse_path(path):
        if isinstance(s,Line):pts.append((s.start.real,s.start.imag))
        elif isinstance(s,CubicBezier):
            pts.extend(flatten_cubic(np.array([[z.real,z.imag] for z in [s.start,s.control1,s.control2,s.end]]))[:-1])
        else:raise ValueError('Only line/cubic source paths are expected')
    return Polygon(pts)

def draw_path(page,path,color=(1,0,0),width=.001):
    shape=page.new_shape()
    def point(z):return fitz.Point(z.real*MM,z.imag*MM)
    for s in parse_path(path):
        if isinstance(s,Line):shape.draw_line(point(s.start),point(s.end))
        else:shape.draw_bezier(*[point(z) for z in [s.start,s.control1,s.control2,s.end]])
    shape.finish(color=color,width=width*MM,closePath=True);shape.commit()

def pieces_from(cut,art,white,slug,protected_drawings=(),smooth=False):
    entries=[]
    for i,d in enumerate(cut[0].get_drawings()):
        for j,path in enumerate(contours(d)):
            original=polygon_of(path);protected=i in protected_drawings
            if smooth:
                if not original.is_valid:raise ValueError(f'{slug} invalid original path {i}:{j}')
                # Always fit owned raster-derived contours, including those that
                # happen to remain below the density rejection threshold.
                path=cut_path(original)
            stats,poly=audit_path(path,allow_original_numerics=protected)
            deviation=original.boundary.hausdorff_distance(poly.boundary)
            assert deviation<(.035 if smooth else .0001),(slug,i,deviation)
            entries.append(dict(path=path,poly=poly,protected=protected,
                                source_draw=i,source_subpath=j,deviation=deviation,stats=stats))
    outers=[i for i,a in enumerate(entries) if not any(b['poly'].contains(a['poly']) for j,b in enumerate(entries) if i!=j)]
    result=[]
    for n,i in enumerate(outers):
        outer=entries[i];members=[e for j,e in enumerate(entries) if j==i or outer['poly'].contains(e['poly'])]
        # Interior holes first, exactly one outer per physical part.
        members.sort(key=lambda e:e['poly'].area)
        result.append(dict(id=f'{slug}_{n+1:02}',bounds=outer['poly'].bounds,poly=outer['poly'],
            paths=members,art=art,white=white,source_rect=cut[0].rect,source=slug))
    assert sum(len(p['paths']) for p in result)==len(entries)
    return result

def pack_once(pieces,order,metric):
    pages=[]
    for p in sorted(pieces,key=order,reverse=True):
        x0,y0,x1,y1=p['bounds'];w=x1-x0;h=y1-y0
        assert min(w,h)<=SIZE[1]-2*MARGIN and max(w,h)<=SIZE[0]-2*MARGIN,(p['id'],w,h)
        choices=[]
        for pi,page in enumerate(pages):
            for fi,(x,y,fw,fh) in enumerate(page['free']):
                for rot,pw,ph in [(0,w,h),(90,h,w)]:
                    if pw+GAP<=fw+1e-6 and ph+GAP<=fh+1e-6:
                        a,b=fw-pw-GAP,fh-ph-GAP
                        score=(min(a,b),max(a,b)) if metric=='short' else (fw*fh-(pw+GAP)*(ph+GAP),min(a,b))
                        choices.append((pi,*score,y,x,fi,rot,pw,ph))
        if not choices:
            pages.append({'free':[(MARGIN,MARGIN,SIZE[0]-2*MARGIN+GAP,SIZE[1]-2*MARGIN+GAP)],'placements':[]})
            pi=len(pages)-1
            for rot,pw,ph in [(0,w,h),(90,h,w)]:
                if pw<=SIZE[0]-2*MARGIN and ph<=SIZE[1]-2*MARGIN:
                    choices.append((pi,SIZE[1]-2*MARGIN-ph,SIZE[0]-2*MARGIN-pw,MARGIN,MARGIN,0,rot,pw,ph))
        pi,_,__,y,x,fi,rot,pw,ph=min(choices)
        page=pages[pi];used=(x,y,pw+GAP,ph+GAP);free=[]
        for fx,fy,fw,fh in page['free']:
            ux,uy,uw,uh=used
            if ux>=fx+fw-1e-8 or ux+uw<=fx+1e-8 or uy>=fy+fh-1e-8 or uy+uh<=fy+1e-8:
                free.append((fx,fy,fw,fh));continue
            if ux>fx:free.append((fx,fy,ux-fx,fh))
            if ux+uw<fx+fw:free.append((ux+uw,fy,fx+fw-ux-uw,fh))
            if uy>fy:free.append((fx,fy,fw,uy-fy))
            if uy+uh<fy+fh:free.append((fx,uy+uh,fw,fy+fh-uy-uh))
        page['free']=[r for i,r in enumerate(free) if not any(i!=j and q[0]<=r[0]+1e-7 and q[1]<=r[1]+1e-7 and q[0]+q[2]>=r[0]+r[2]-1e-7 and q[1]+q[3]>=r[1]+r[3]-1e-7 and (q!=r or j<i) for j,q in enumerate(free))]
        page['placements'].append(dict(piece=p,x=x,y=y,w=pw,h=ph,rotation=rot))
    return pages

def pack(pieces):
    def wh(p):b=p['bounds'];return b[2]-b[0],b[3]-b[1]
    orders=[lambda p:math.prod(wh(p)),lambda p:max(wh(p)),lambda p:min(wh(p)),lambda p:wh(p)[1],lambda p:wh(p)[0]]
    candidates=[pack_once(pieces,key,metric) for key in orders for metric in ['short','area']]
    # A slightly longer 5T tab can defeat the ten greedy orders despite a valid
    # one-page arrangement. Explore deterministic size-weighted orders before
    # accepting an extra sheet; geometry and gap never change.
    if min(len(p) for p in candidates)>1:
        rng=random.Random(20261121)
        for attempt in range(200):
            ranks={p['id']:math.prod(wh(p))*rng.uniform(.6,1.4) for p in pieces}
            trial=pack_once(pieces,lambda p:ranks[p['id']],['short','area'][attempt%2])
            candidates.append(trial)
            if len(trial)==1:break
    return min(candidates,key=lambda pages:(len(pages),sum(max(q['y']+q['h'] for q in p['placements']) for p in pages)))

def shifted_poly(p,placement):
    x0,y0,x1,y1=placement['piece']['bounds']
    p=affinity.translate(p,-x0,-y0)
    angle=math.radians(placement['rotation']);c,s=math.cos(angle),math.sin(angle)
    origin=placement.get('rotated_origin')
    if origin is None:
        # Legacy rectangular packing uses the rotated source rectangle origin.
        corners=[(c*x+s*y,-s*x+c*y) for x,y in [(0,0),(x1-x0,0),(0,y1-y0),(x1-x0,y1-y0)]]
        origin=(min(x for x,y in corners),min(y for x,y in corners))
    p=affinity.affine_transform(p,[c,s,-s,c,0,0])
    return affinity.translate(p,placement['x']-origin[0],placement['y']-origin[1])


def pdf_destination(placement,pad=.15):
    b=placement['piece']['bounds'];w,h=b[2]-b[0],b[3]-b[1]
    a=math.radians(placement['rotation']);c,s=math.cos(a),math.sin(a)
    corners=[(c*x+s*y,-s*x+c*y) for x,y in [(-pad,-pad),(w+pad,-pad),(-pad,h+pad),(w+pad,h+pad)]]
    origin=placement.get('rotated_origin')
    if origin is None:
        corners0=[(c*x+s*y,-s*x+c*y) for x,y in [(0,0),(w,0),(0,h),(w,h)]]
        origin=(min(x for x,y in corners0),min(y for x,y in corners0))
    dx,dy=placement['x']-origin[0],placement['y']-origin[1]
    return fitz.Rect((dx+min(x for x,y in corners))*MM,(dy+min(y for x,y in corners))*MM,
                     (dx+max(x for x,y in corners))*MM,(dy+max(y for x,y in corners))*MM)

def transformed_cut_path(path,placement):
    """Rigidly map original Bezier controls; avoid rounded PDF Form matrices."""
    b=placement['piece']['bounds'];a=math.radians(placement['rotation']);c,s=math.cos(a),math.sin(a)
    origin=placement.get('rotated_origin')
    if origin is None:
        corners=[(c*x+s*y,-s*x+c*y) for x,y in [(0,0),(b[2]-b[0],0),(0,b[3]-b[1]),(b[2]-b[0],b[3]-b[1])]]
        origin=(min(x for x,y in corners),min(y for x,y in corners))
    def pt(z):
        x,y=z.real-b[0],z.imag-b[1]
        return f'{c*x+s*y-origin[0]+placement["x"]:.9f} {-s*x+c*y-origin[1]+placement["y"]:.9f}'
    result=[]
    for i,seg in enumerate(parse_path(path)):
        if i==0:result.append('M'+pt(seg.start))
        if isinstance(seg,Line):result.append('L'+pt(seg.end))
        elif isinstance(seg,CubicBezier):result.append('C'+' '.join(pt(z) for z in [seg.control1,seg.control2,seg.end]))
        else:raise ValueError('Expected original line or cubic contour')
    return ' '.join(result)+' Z'


def clip_art(doc,piece):
    """Isolate the piece with a true vector clip, avoiding adjacent artwork."""
    if doc is None:return None
    result=fitz.open();page=result.new_page(width=doc[0].rect.width,height=doc[0].rect.height)
    if not doc[0].get_contents():return result
    page.show_pdf_page(page.rect,doc,0)
    # PDF coordinates have an upward Y axis. An exterior clip has no stroke.
    outer=max(piece['paths'],key=lambda e:e['poly'].area)['path'];cmd=[]
    for k,s in enumerate(parse_path(outer)):
        def pt(z):return f'{z.real*MM:.7f} {page.rect.height-z.imag*MM:.7f}'
        if k==0:cmd.append(pt(s.start)+' m')
        if isinstance(s,Line):cmd.append(pt(s.end)+' l')
        else:cmd.append(' '.join(pt(z) for z in [s.control1,s.control2,s.end])+' c')
    stream=page.get_contents()[-1]
    result.update_stream(stream,('q\n'+'\n'.join(cmd)+' h W n\n').encode()+result.xref_stream(stream)+b'\nQ')
    return result

def write_page(folder,placements):
    folder.mkdir(parents=True,exist_ok=True)
    master=fitz.open();mp=master.new_page(width=SIZE[0]*MM,height=SIZE[1]*MM)
    names=['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT','WHITE_INK_MASK']
    oc={n:master.add_ocg(n,on=True) for n in names};streams={v:[] for v in oc.values()}
    docs={n:fitz.open() for n in ['PRINT_ARTWORK','LASER_CUT','WHITE_INK_MASK']}
    for d in docs.values():d.new_page(width=mp.rect.width,height=mp.rect.height)
    report=[];protected_regions=[]
    for place in placements:
        p=place['piece'];b=p['bounds'];pad=.15
        clip=fitz.Rect((b[0]-pad)*MM,(b[1]-pad)*MM,(b[2]+pad)*MM,(b[3]+pad)*MM)
        dest=pdf_destination(place,pad)
        selected={'PRINT_ARTWORK':clip_art(p['art'],p),'WHITE_INK_MASK':clip_art(p['white'],p)}
        for name,doc in selected.items():
            if doc is None or not doc[0].get_contents():continue
            mp.show_pdf_page(dest,doc,0,clip=clip,rotate=place['rotation'])
            streams[oc[name]].append(master.xref_stream(mp.get_contents()[-1]))
            docs[name][0].show_pdf_page(dest,doc,0,clip=clip,rotate=place['rotation'])
        for entry in p['paths']:
            global_path=transformed_cut_path(entry['path'],place)
            draw_path(mp,global_path)
            streams[oc['LASER_CUT']].append(master.xref_stream(mp.get_contents()[-1]))
            draw_path(docs['LASER_CUT'][0],global_path)
        expected=[shifted_poly(e['poly'],place) for e in p['paths']]
        if any(e['protected'] for e in p['paths']):
            protected_regions.append(list(shifted_poly(p['poly'],place).bounds))
        report.append({'id':p['id'],'source':p['source'],'source_bounds_mm':list(b),
            'rotated_origin_mm':place.get('rotated_origin'),
            'placed_bounds_mm':[place['x'],place['y'],place['x']+place['w'],place['y']+place['h']],
            'rotation_degrees':place['rotation'],'scale':1,'path_count':len(p['paths']),
            'protected_original':any(e['protected'] for e in p['paths']),
            'max_source_curve_deviation_mm':max(e['deviation'] for e in p['paths']),
            'expected_paths':[list(q.exterior.coords) for q in expected],
            'design_metadata':p.get('design_metadata')})
    for page in [mp,docs['PRINT_ARTWORK'][0]]:
        page.draw_rect(fitz.Rect(4*MM,4*MM,(SIZE[0]-4)*MM,(SIZE[1]-4)*MM),color=(0,0,1),width=.3*MM)
    streams[oc['CORNER_REFERENCE']].append(master.xref_stream(mp.get_contents()[-1]))
    mark_pdf_layers(mp,streams)
    allpath=TMP/'all_layers.pdf';master.save(allpath,garbage=4,deflate=True)
    # Production PDFs and transparent PNGs: all share A3 and the same origin.
    for name,stem in [('PRINT_ARTWORK','01_PRINT'),('LASER_CUT','03_CUT_ONLY'),('WHITE_INK_MASK','04_WHITE_INK_MASK')]:
        docs[name].save(folder/f'{stem}.pdf',garbage=4,deflate=True)
        if name!='LASER_CUT':docs[name][0].get_pixmap(dpi=300,alpha=True).save(folder/f'{stem}_300ppi.png')
    cuts=docs['LASER_CUT'][0].get_drawings()
    svgpaths=[s for d in cuts for s in contours(d)]
    (folder/'03_CUT_ONLY.svg').write_text(svg_doc(*SIZE,layer('LASER_CUT',''.join(f'<path d="{s}" fill="none" stroke="#ff0000" stroke-width="0.001"/>' for s in svgpaths))),encoding='utf-8')
    # Verify exported cuts against every source path under its exact rigid map.
    actual=[polygon_of(s).buffer(0) for s in svgpaths]
    expected=[Polygon(coords) for r in report for coords in r['expected_paths']]
    assert len(actual)==len(expected),(len(actual),len(expected))
    deviations=[a.boundary.hausdorff_distance(e.boundary) for a,e in zip(actual,expected)]
    assert max(deviations,default=0)<.002,('export transformed geometry',max(deviations))
    outers=[shifted_poly(p['piece']['poly'],p) for p in placements]
    gap=min((p.distance(q) for i,p in enumerate(outers) for q in outers[:i]),default=None)
    assert gap is None or gap>=GAP-.002,gap
    assert all(box(MARGIN-.002,MARGIN-.002,SIZE[0]-MARGIN+.002,SIZE[1]-MARGIN+.002).contains(p) for p in outers)
    # Avoid importing every off-clip source image once for every placed part.
    # Print PDFs above retain the original vector/bitmap data. Native edit files
    # carry individually movable 600-ppi artwork images and exact vector cuts.
    native=fitz.open();npag=native.new_page(width=mp.rect.width,height=mp.rect.height)
    noc={n:native.add_ocg(n,on=True) for n in names};ns={v:[] for v in noc.values()}
    for place in placements:
        region=fitz.Rect((place['x']-.2)*MM,(place['y']-.2)*MM,(place['x']+place['w']+.2)*MM,(place['y']+place['h']+.2)*MM)
        for name in ['PRINT_ARTWORK','WHITE_INK_MASK']:
            # Nested bounding boxes overlap. Render this piece alone so adjacent
            # artwork is never duplicated in native editable image objects.
            piece=place['piece'];b=piece['bounds'];pad=.15
            source=clip_art(piece['art'] if name=='PRINT_ARTWORK' else piece['white'],piece)
            if source is None or not source[0].get_contents():continue
            isolated=fitz.open();ip=isolated.new_page(width=mp.rect.width,height=mp.rect.height)
            clip=fitz.Rect((b[0]-pad)*MM,(b[1]-pad)*MM,(b[2]+pad)*MM,(b[3]+pad)*MM)
            ip.show_pdf_page(pdf_destination(place,pad),source,0,clip=clip,rotate=place['rotation'])
            pix=ip.get_pixmap(dpi=600,clip=region,alpha=True)
            if not any(pix.samples[3::4]):continue
            rect=fitz.Rect(pix.x*72/600,pix.y*72/600,(pix.x+pix.width)*72/600,(pix.y+pix.height)*72/600)
            npag.insert_image(rect,stream=pix.tobytes('png'))
            ns[noc[name]].append(native.xref_stream(npag.get_contents()[-1]))
    npag.show_pdf_page(npag.rect,docs['LASER_CUT'],0)
    ns[noc['LASER_CUT']].append(native.xref_stream(npag.get_contents()[-1]))
    npag.draw_rect(fitz.Rect(4*MM,4*MM,(SIZE[0]-4)*MM,(SIZE[1]-4)*MM),color=(0,0,1),width=.3*MM)
    ns[noc['CORNER_REFERENCE']].append(native.xref_stream(npag.get_contents()[-1]))
    mark_pdf_layers(npag,ns)
    nativepath=TMP/'native_layers.pdf';native.save(nativepath,garbage=4,deflate=True)
    info=json.loads(runvc(['run','--in',nativepath,'--cmd','document.inspect']).splitlines()[-1])['result']
    layers={g['name']:g['id'] for g in info['layers']};assert set(layers)==set(names)
    job=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
         {'command':'document.export','params':{'path':str(folder/'02_MASTER.ai'),'format':'pdf','createLayers':True,'preserveEditing':False}},
         {'command':'layer.setProps','params':{'ids':[layers[n] for n in ['LASER_CUT','WHITE_INK_MASK']],'visible':False,'printable':False}},
         {'command':'document.save','params':{'path':str(folder/'02_MASTER.vectorcraft'),'format':'vectorcraft','compress':False}}]
    jf=TMP/'export.json';jf.write_text(json.dumps(job));runvc(['run','--in',nativepath,'--commands',jf])
    with fitz.open(folder/'02_MASTER.ai') as ai:
        groups=ai.get_ocgs();on=[i for i,g in groups.items() if g['name'] in ['PRINT_ARTWORK','CORNER_REFERENCE']]
        ai.set_layer(-1,basestate='OFF',on=on,off=[i for i in groups if i not in on])
        # The exporter serializes off-clip source objects repeatedly into its
        # Illustrator private payload (hundreds of MB). Keep the PDF-compatible
        # vector/OCG content; the full native editing state is supplied separately.
        ai.xref_set_key(ai[0].xref,'PieceInfo','null')
        ai.xref_set_key(ai.pdf_catalog(),'Names/EmbeddedFiles','null')
        ai.save(TMP/'hidden.ai',garbage=4,deflate=True)
    shutil.copy2(TMP/'hidden.ai',folder/'02_MASTER.ai')
    master.set_layer(-1,basestate='OFF',on=[oc[n] for n in ['PRINT_ARTWORK','CORNER_REFERENCE']],off=[oc[n] for n in ['LASER_CUT','WHITE_INK_MASK']])
    master.save(folder/'02_MASTER.pdf',garbage=4,deflate=True)
    # Review only: visible 0.13-mm red cut outlines; production stroke stays .001.
    review=fitz.open();rp=review.new_page(width=mp.rect.width,height=mp.rect.height)
    rp.show_pdf_page(rp.rect,docs['PRINT_ARTWORK'],0)
    for s in svgpaths:draw_path(rp,s,width=.13)
    review.save(folder/'PREVIEW_NOT_FOR_CUT.pdf',garbage=4,deflate=True)
    rp.get_pixmap(dpi=100,alpha=False).save(folder/'preview.png')
    # A close-up of actual curves is required, not just the overall art render.
    zoom=fitz.open();zp=zoom.new_page(width=mp.rect.width,height=mp.rect.height)
    for s in svgpaths:draw_path(zp,s,width=.10)
    zrect=fitz.Rect(*[v*MM for v in report[0]['placed_bounds_mm']])
    zoomscale=min(8,1300/max(zrect.width,zrect.height))
    zp.get_pixmap(matrix=fitz.Matrix(zoomscale,zoomscale),clip=zrect+(-3,-3,3,3),alpha=False).save(folder/'cut_detail.png')
    count=sum(r['path_count'] for r in report)
    occupied=[min(p.bounds[0] for p in outers),min(p.bounds[1] for p in outers),
              max(p.bounds[2] for p in outers),max(p.bounds[3] for p in outers)]
    result={'canvas_mm':list(SIZE),'pieces':len(report),'closed_contours':count,'minimum_gap_mm':gap,
        'occupied_bounds_mm':occupied,'occupied_rectangle_area_mm2':(occupied[2]-occupied[0])*(occupied[3]-occupied[1]),
        'layout_method':'15-degree contour nesting' if any(p.get('rotated_origin') is not None for p in placements) else 'rectangular packing',
        'minimum_page_margin_mm':MARGIN,'artwork_scale':1,'protected_regions_mm':protected_regions,
        'max_rigid_export_deviation_mm':max(deviations,default=0),'physical_cut_test':False,
        'white_ink_policy':'Provided white plates retained; absent source white is empty. RIP white required for other art.',
        'native_artwork_ppi':600,'ai_format':'PDF-compatible layered vector-cut artwork; native editing state is separate .vectorcraft',
        'parts':report}
    (folder/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'README.md').write_text(f'# A3 · {len(report)}조각\n\n![배치](preview.png)\n\n420×297mm / 실제 크기 100% / 자동 맞춤 해제.\n\n- `01_PRINT.pdf` 또는 `01_PRINT_300ppi.png`: 인쇄·파란 기준선.\n- `02_MASTER.ai`, `.pdf`, `.vectorcraft`: 레이어별 편집 원본.\n- `03_CUT_ONLY.pdf` 또는 `.svg`: 재단 전용, 빨강 0.001mm.\n- `04_WHITE_INK_MASK`: 원본 제공 백색만 보존. 없는 그림은 RIP에서 백색 설정.\n- `PREVIEW_NOT_FOR_CUT.pdf`, `preview.png`, `cut_detail.png`: 검토용, 재단 금지.\n\n외곽 {len(report)}개 / 전체 폐곡선 {count}개. 그림·홈·구멍 배율 1:1.\n파란 기준 사각형은 자르지 않습니다. 인쇄·재단 모두 같은 대지 원점을 사용합니다.\n실물 정합·끼움·절단은 아직 시험하지 않았습니다.\n',encoding='utf-8')
    print(folder.relative_to(ROOT),len(report),count,'gap',gap,flush=True)
    return {'folder':folder.relative_to(ROOT/'output').as_posix(),'pieces':len(report),'contours':count}

def supplied_sources():
    native=next((ROOT/'assets/external/linked_supplied').rglob('*.vectorcraft'))
    info=json.loads(runvc(['run','--in',native,'--cmd','document.inspect']).splitlines()[-1])['result']
    layers={x['name']:x for x in info['layers']};cutfile=TMP/'supplied_cut.pdf'
    job=[{'command':'layer.setProps','params':{'ids':[layers['이미지']['id']],'visible':False,'printable':False}},
         {'command':'document.export','params':{'path':str(cutfile),'format':'pdf'}}]
    p=TMP/'supplied.json';p.write_text(json.dumps(job));runvc(['run','--in',native,'--commands',p])
    cut=fitz.open(cutfile);art=fitz.open();white=fitz.open()
    ap=art.new_page(width=cut[0].rect.width,height=cut[0].rect.height);wp=white.new_page(width=ap.rect.width,height=ap.rect.height)
    for item in layers['이미지']['children']:
        src=next(native.parent.rglob(item['name']));b=item['bounds'];r=fitz.Rect(b['x'],b['y'],b['x']+b['width'],b['y']+b['height'])
        ap.insert_image(r,filename=str(src))
        im=Image.open(src).convert('RGBA');mask=Image.new('RGBA',im.size,(0,0,0,0));mask.putalpha(im.getchannel('A'))
        b=BytesIO();mask.save(b,format='PNG');wp.insert_image(r,stream=b.getvalue())
    return pieces_from(cut,art,white,'supplied_saetui')

def ascent_source():
    folder='assets/external/ascent_original/';m=json.loads(source_path(folder+'manifest.json').read_text())
    raw=b''.join(source_path(folder+p).read_bytes() for p in m['parts'])
    assert hashlib.sha256(raw).hexdigest()==m['sha256']
    path=TMP/'kimyun_ascent.ai';path.write_bytes(raw)
    return path

def source_inputs(only=None):
    restore_inputs()
    batches=[]
    linked=[]
    if not only or any(only in n for n in ['02_extra_sheet/3T','02_extra_sheet/5T','05_len/3T','05_len/5T']):
        linked=supplied_sources();assert len(linked)==4
        for name in ['tuiing','golden','burnt','unfried']:
            folder=source_path(f'output/linked_tuiing_v1/{name}/02_MASTER.ai').parent
            art=extract_layers(folder/'02_MASTER.ai',['PRINT_ARTWORK','3_ARTWORK','2_ARTWORK'])
            if not art[0].get_images() and not art[0].get_drawings():raise ValueError(f'No artwork extracted: {name}')
            linked+=pieces_from(fitz.open(folder/'03_CUT_ONLY.pdf'),art,fitz.open(folder/'04_WHITE_INK_MASK.pdf'),name)
        assert len(linked)==8
    for t in ['3T','5T']:
        if only and only not in f'02_extra_sheet/{t}':continue
        src=source_path(f'output/extra_sheet/{t}/01_COMBINED_SHEET.pdf').parent/'02_UNUSED'
        master=src.parent/'01_COMBINED_SHEET.pdf'
        art=extract_layers(master,['PRINT_ARTWORK']);white=extract_layers(master,['WHITE_INK_MASK'])
        cut=fitz.open(src.parent/'03_CUT_ONLY.pdf')
        pieces=pieces_from(cut,art,white,f'extra_{t}',range(34));assert len(pieces)==38
        batches.append((f'02_extra_sheet/{t}',pieces+linked[:4]))
    if not only or only in '04_ascent_cadena':
        src=ascent_source();art=extract_layers(src,['인쇄']);white=extract_layers(src,['화이트']);cut=extract_layers(src,['받침','칼선'])
        pieces=pieces_from(cut,art,white,'ascent');assert len(pieces)==31,len(pieces)
        selected=CONFIG['cadena_source_part_ids']
        pieces=[p for p in pieces if p['id'] in selected]
        assert {p['id'] for p in pieces}==set(selected) and len(pieces)==5
        batches.append(('04_ascent_cadena',pieces))
    for t in ['3T','5T']:
        if only and only not in f'05_len/{t}':continue
        folder=source_path(f'output/len_diorama_v1/{t}/02_MASTER.ai').parent
        master=folder/'02_MASTER.ai';art=extract_layers(master,['3_ARTWORK']);cut=fitz.open(folder/'03_CUT_ONLY.pdf')
        pieces=pieces_from(cut,art,None,f'len_{t}',smooth=True);assert len(pieces)==7
        dotfolder=source_path(f'output/len_diorama_dot_v1/{t}/02_MASTER.ai').parent
        dot=pieces_from(fitz.open(dotfolder/'03_CUT_ONLY.pdf'),extract_layers(dotfolder/'02_MASTER.ai',['3_ARTWORK']),None,f'len_dot_{t}',smooth=True)
        # Both source layouts put their character in the same upper-left cell.
        character=lambda p:p['bounds'][0]<15 and 120<p['bounds'][1]<130
        dotchar=[p for p in dot if character(p)]
        assert len(dotchar)==1 and len([p for p in pieces if character(p) and p['source']==f'len_{t}'])==1
        # Common parts must really be interchangeable before deduplicating them.
        for p in dot:
            if character(p):continue
            q=min(pieces[:7],key=lambda q:p['poly'].hausdorff_distance(q['poly']))
            assert len(p['paths'])==len(q['paths'])
            for e in p['paths']:
                assert min(e['poly'].boundary.hausdorff_distance(f['poly'].boundary) for f in q['paths'])<.035
        from len_dot_part import create_dot_documents
        newcut,newart,meta=create_dot_documents(ROOT,t,draw_path,MM,CONFIG['len_dot_revision'])
        replacement=pieces_from(newcut,newart,None,f'len_dot_{t}')[0]
        replacement['id']=dotchar[0]['id'];replacement['design_metadata']=meta
        batches.append((f'05_len/{t}',pieces+[replacement]+linked[4:]))
    for t in ['3T','5T']:
        if only and only not in f'06_len_pad/{t}':continue
        folder=source_path(f'output/len_diorama_pad_v1/{t}/02_MASTER.ai').parent
        art=extract_layers(folder/'02_MASTER.ai',['3_ARTWORK'])
        pieces=pieces_from(fitz.open(folder/'03_CUT_ONLY.pdf'),art,None,f'len_pad_{t}')
        assert len(pieces)==7 and sum(len(p['paths']) for p in pieces)==15
        batches.append((f'06_len_pad/{t}',pieces))
    if not only or 'yanggum' in only:
        from yanggum_parts import stand_documents,keyring_documents
        spec=CONFIG['yanggum_products']
        cut,art,meta=stand_documents(ROOT,'3T',draw_path,MM,spec['stand'])
        stand=pieces_from(cut,art,None,'yanggum_stand',smooth=True);assert len(stand)==2
        stand[0]['design_metadata']=meta['character'];stand[1]['design_metadata']=meta['base']
        cut,art,kmeta=keyring_documents(ROOT,'3T',draw_path,MM,spec['keyring'])
        keyring=pieces_from(cut,art,None,'yanggum_keyring',smooth=True);assert len(keyring)==1
        keyring[0]['design_metadata']=kmeta
        batches.append(('09_yanggum/3T',stand+keyring))
    return batches

def apply_canonical_contours(piece):
    """Stable reviewed Beziers shared by individual assets and A3 derivatives.

    This removes platform-dependent refitting from the released geometry. The
    print source remains pinned separately; no image or mechanical scaling occurs.
    """
    file=ROOT/'configs/individual_contours.json'
    if not file.exists():return piece
    # Cache data only; callers can mutate their independent piece dictionaries.
    if not hasattr(apply_canonical_contours,'data'):
        apply_canonical_contours.data=json.loads(file.read_text(encoding='utf-8'))['parts']
    row=apply_canonical_contours.data[piece['id']]
    assert max(abs(a-b) for a,b in zip(piece['bounds'],row['source_bounds_mm']))<.0001,('Canonical source dimensions changed',piece['id'])
    assert len(piece['paths'])==len(row['paths'])
    for entry,path in zip(piece['paths'],row['paths']):
        poly=polygon_of(path)
        delta=entry['poly'].boundary.hausdorff_distance(poly.boundary)
        assert delta<(.0001 if entry['protected'] else .035),(piece['id'],'Changed reviewed curve',delta)
        entry.update(path=path,poly=poly,deviation=delta)
    piece['poly']=max((e['poly'] for e in piece['paths']),key=lambda q:q.area)
    return piece


def inputs(only=None):
    batches=dict(source_inputs(only if only and ('06_len_pad' in only or 'yanggum' in only) else None))
    for t in ['3T','5T']:
        group=f'02_extra_sheet/{t}'
        if group in batches:
            batches[group]=[p for p in batches[group] if p['id'] not in CONFIG['excluded_brand_parts'][t]]
    cadena={p['id']:p for p in batches.pop('04_ascent_cadena',[])}
    for group,ids in CONFIG['cross_sheet_cadena_allocation'].items():
        if group in batches:batches[group]+=[cadena[k] for k in ids]
    visited=set()
    for parts in batches.values():
        for piece in parts:
            if id(piece) not in visited:
                apply_canonical_contours(piece);visited.add(id(piece))
    return [(group,parts) for group,parts in batches.items() if not only or only in group]


def reviewed_layout(name,pieces):
    """Replay reviewed rigid placements without searching a new layout on rebuild."""
    data=json.loads((ROOT/'configs/a3_placements.json').read_text(encoding='utf-8'))
    rows=data['groups'][name]
    by_id={p['id']:p for p in pieces}
    assert set(by_id)=={r['id'] for r in rows} and len(by_id)==len(rows),('Changed part inventory',name)
    placements=[]
    for row in rows:
        piece=by_id[row['id']]
        assert max(abs(a-b) for a,b in zip(piece['bounds'],row['source_bounds_mm']))<.0001,('Source dimensions changed; review placement',piece['id'])
        poly,origin=rotated(piece,row['rotation_degrees'])
        placements.append(dict(piece=piece,x=row['x'],y=row['y'],rotation=row['rotation_degrees'],
            rotated_origin=origin,w=poly.bounds[2],h=poly.bounds[3]))
    shapes=[shifted_poly(p['piece']['poly'],p) for p in placements]
    for i,shape in enumerate(shapes):
        assert box(MARGIN-.002,MARGIN-.002,SIZE[0]-MARGIN+.002,SIZE[1]-MARGIN+.002).contains(shape)
        assert all(shape.distance(q)>=GAP-.002 for q in shapes[:i])
    return [{'placements':placements}]


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--only');parser.add_argument('--plan',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    manifest_path=OUT/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'canvas_mm':list(SIZE),'groups':{},'physical_cut_test':False}
    manifest['revision']=CONFIG['revision']
    manifest['test_pieces_included']=False
    manifest['superseded_releases']=CONFIG['superseded_releases']
    manifest['physical_pages_per_selected_thickness']=2
    manifest['retired_groups']=CONFIG['retired_groups']
    for retired in manifest['retired_groups']:manifest['groups'].pop(retired,None)
    for name,pieces in inputs(args.only):
        if args.only and args.only not in name:continue
        assert not CONFIG['include_test_pieces']
        assert not any('fit' in p['id'].lower() or 'test' in p['id'].lower() for p in pieces)
        if (ROOT/'configs/a3_placements.json').exists():
            pages=reviewed_layout(name,pieces)
        elif name.startswith(('05_len/','06_len_pad/')):
            policy=CONFIG['len_layout']
            assert policy['angle_step_degrees']==15 and policy['exact_minimum_gap_mm']==GAP
            pages=contour_nest(pieces,SIZE,MARGIN,GAP,trials=policy['trials'],resolution=policy['search_grid_mm'])
        else:pages=pack(pieces)
        assert len(pages)==1,(name,'A3 sheet count regression')
        print('PLAN',name,len(pieces),len(pages),[len(p['placements']) for p in pages],flush=True)
        if args.plan:continue
        records=[write_page(OUT/name/f'sheet_{i+1:02}',p['placements']) for i,p in enumerate(pages)]
        manifest['groups'][name]=records
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
