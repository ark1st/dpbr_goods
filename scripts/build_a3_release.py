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
from shapely.geometry import Polygon, Point, box
from shapely import affinity
from svgpathtools import parse_path, Line, CubicBezier
from laser_paths import audit_path, cut_path, flatten_cubic, slot_path
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

def len_slot_fit(thickness):
    """Drawn slot (length, width) after kerf and fit compensation (issue #1)."""
    fit=CONFIG['len_slot_fit'];t=fit['thickness'][thickness]
    width=t['part_thickness_mm']+t['thickness_clearance_mm']-t['kerf_mm']
    length=fit['tab_width_mm']+t['side_clearance_mm']-2*t['kerf_mm']
    return round(length,6),round(width,6)

def compensate_len_slots(pieces,thickness):
    """Replace nominal 18.8 x T Len mounting slots by kerf-compensated slots.

    Only interior slots matching the nominal Len slot are changed. Outer
    contours, artwork, tabs and other holes (e.g. Cadena 3.2 x 20.2) are kept.
    """
    fit=CONFIG['len_slot_fit'];nominal=(fit['source_slot_mm'][0],float(thickness.removesuffix('T')))
    length,width=len_slot_fit(thickness);radius=fit['corner_radius_mm'];changed=0
    for piece in pieces:
        outer=max(piece['paths'],key=lambda e:e['poly'].area)
        for e in piece['paths']:
            if e is outer or e['protected']:continue
            rect=np.array(e['poly'].minimum_rotated_rectangle.exterior.coords)
            a,b=rect[1]-rect[0],rect[2]-rect[1]
            long,short=(a,b) if np.hypot(*a)>=np.hypot(*b) else (b,a)
            if abs(np.hypot(*long)-nominal[0])>.01 or abs(np.hypot(*short)-nominal[1])>.01:continue
            angle=math.degrees(math.atan2(long[1],long[0]))
            # Source slots sit on the 15-degree layout grid; snap fitting noise.
            snapped=round(angle/15)*15
            if abs(angle-snapped)<.1:angle=float(snapped)
            aligned=affinity.rotate(e['poly'],-angle,origin=(0,0)).bounds
            mid=affinity.rotate(Point((aligned[0]+aligned[2])/2,(aligned[1]+aligned[3])/2),angle,origin=(0,0))
            center=(mid.x,mid.y)
            path=slot_path(center,angle,length,width,radius)
            stats,poly=audit_path(path)
            assert outer['poly'].contains(poly)
            e.update(path=path,poly=poly,stats=stats,slot_fit={'nominal_mm':list(nominal),
                'drawn_mm':[length,width],'center_mm':list(center),'angle_degrees':angle})
            changed+=1
    return changed

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
         {'command':'layer.setProps','params':{'ids':[layers['WHITE_INK_MASK']],'visible':False,'printable':False}},
         {'command':'layer.setProps','params':{'ids':[layers['LASER_CUT']],'visible':True,'printable':False}},
         {'command':'document.save','params':{'path':str(folder/'02_MASTER.vectorcraft'),'format':'vectorcraft','compress':False}}]
    jf=TMP/'export.json';jf.write_text(json.dumps(job));runvc(['run','--in',nativepath,'--commands',jf])
    with fitz.open(folder/'02_MASTER.ai') as ai:
        groups=ai.get_ocgs();on=[i for i,g in groups.items() if g['name'] in ['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT']]
        ai.set_layer(-1,basestate='OFF',on=on,off=[i for i in groups if i not in on])
        # The exporter serializes off-clip source objects repeatedly into its
        # Illustrator private payload (hundreds of MB). Keep the PDF-compatible
        # vector/OCG content; the full native editing state is supplied separately.
        ai.xref_set_key(ai[0].xref,'PieceInfo','null')
        ai.xref_set_key(ai.pdf_catalog(),'Names/EmbeddedFiles','null')
        ai.save(TMP/'hidden.ai',garbage=4,deflate=True)
    shutil.copy2(TMP/'hidden.ai',folder/'02_MASTER.ai')
    master.set_layer(-1,basestate='OFF',on=[oc[n] for n in ['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT']],off=[oc['WHITE_INK_MASK']])
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
    rel=folder.relative_to(ROOT/'output').as_posix() if folder.is_relative_to(ROOT/'output') else str(folder)
    return {'folder':rel,'pieces':len(report),'contours':count}

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


def ascent_parts():
    src=ascent_source()
    return pieces_from(extract_layers(src,['받침','칼선']),extract_layers(src,['인쇄']),
                       extract_layers(src,['화이트']),'ascent')

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
    if (not only or only in '04_ascent_cadena' or '11_ascent_remaining' in only) and not CONFIG.get('ascent_5t_migration',{}).get('three_t_excluded',False):
        pieces=ascent_parts();assert len(pieces)==31,len(pieces)
        selected=CONFIG['cadena_source_part_ids']
        cadena=[p for p in pieces if p['id'] in selected]
        assert {p['id'] for p in cadena}==set(selected) and len(cadena)==5
        batches.append(('04_ascent_cadena',cadena))
        remaining=CONFIG.get('ascent_remaining',{}).get('part_ids',[])
        if remaining:batches.append(('11_ascent_remaining/3T',[p for p in pieces if p['id'] in remaining]))
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
        meta['compensated_base_slot_mm']=list(len_slot_fit(t));meta['slot_fit_status']=CONFIG['len_slot_fit']['status']
        assert compensate_len_slots(pieces,t)==8,('Len slot count changed',t)
        batches.append((f'05_len/{t}',pieces+[replacement]+linked[4:]))
    for t in ['3T','5T']:
        if only and only not in f'06_len_pad/{t}':continue
        folder=source_path(f'output/len_diorama_pad_v1/{t}/02_MASTER.ai').parent
        art=extract_layers(folder/'02_MASTER.ai',['3_ARTWORK'])
        pieces=pieces_from(fitz.open(folder/'03_CUT_ONLY.pdf'),art,None,f'len_pad_{t}')
        assert len(pieces)==7 and sum(len(p['paths']) for p in pieces)==15
        assert compensate_len_slots(pieces,t)==8,('Len PAD slot count changed',t)
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
    row=apply_canonical_contours.data[piece.get('canonical_id',piece['id'])]
    assert max(abs(a-b) for a,b in zip(piece['bounds'],row['source_bounds_mm']))<.0001,('Canonical source dimensions changed',piece['id'])
    assert len(piece['paths'])==len(row['paths'])
    for entry,path in zip(piece['paths'],row['paths']):
        poly=polygon_of(path)
        delta=entry['poly'].boundary.hausdorff_distance(poly.boundary)
        assert delta<(.0001 if entry['protected'] else .035),(piece['id'],'Changed reviewed curve',delta)
        entry.update(path=path,poly=poly,deviation=delta)
    piece['poly']=max((e['poly'] for e in piece['paths']),key=lambda q:q.area)
    return piece


def smooth_logo_source(original,design):
    """New exterior, exact original hole; isolate source artwork before widening its clip."""
    assert original['id']==design['source_id']=='extra_3T_32'
    assert len(original['paths'])==len(design['paths'])==2
    original_hole=min(original['paths'],key=lambda entry:entry['poly'].area)
    hole_stats,hole=audit_path(design['paths'][0])
    assert hole.boundary.hausdorff_distance(original_hole['poly'].boundary)<.00001,'Changed original logo hole'
    stats,outer=audit_path(design['paths'][1])
    assert outer.is_valid and outer.contains(hole)
    assert outer.boundary.distance(hole.boundary)>=3.0,'Insufficient material around logo hole'
    assert max(abs(a-b) for a,b in zip(outer.bounds,design['new_bounds_mm']))<.002
    # Never let the expanded silhouette expose adjacent art on the original
    # combined sheet: isolate using the original outline while coordinates stay
    # in the original page's coordinate system.
    art=clip_art(original['art'],original)
    white=clip_art(original['white'],original)
    def entry(path,poly,quality):
        return {'path':path,'poly':poly,'protected':False,'source_draw':None,
                'source_subpath':None,'deviation':0,'stats':quality}
    return {**original,'id':'danba_logo_smooth','canonical_id':'danba_logo_smooth',
            'bounds':outer.bounds,'poly':outer,
            'paths':[entry(design['paths'][0],hole,hole_stats),entry(design['paths'][1],outer,stats)],
            'art':art,'white':white,
            'design_metadata':{'source_id':original['id'],
                'exterior':'intentionally redesigned smooth contour',
                'art_clip':'original source exterior',
                'hole_diameter_mm':4}}


def redesign_outer_contour(original,design):
    """Install a reviewed exterior while pinning all source art and interfaces.

    Candidate paths use the source page coordinates. Internal paths remain in
    the source order with the exterior last. For an identified tab, a declared
    rectangular region must retain the original material geometry exactly.
    """
    from shapely.geometry import box
    ident=original['id']
    assert design.get('pin_original_art') is True,(ident,'Source artwork must stay isolated')
    assert not any(entry.get('protected') for entry in original['paths']),(ident,'Protected original may not be redesigned')
    assert max(abs(a-b) for a,b in zip(original['bounds'],design['source_bounds_mm']))<.0001,(ident,'Original bounds changed')
    paths=design['paths'];original_paths=original['paths']
    assert len(paths)==len(original_paths),(ident,'Changed path count')
    old_outer=max(original_paths,key=lambda entry:entry['poly'].area)
    old_holes=[entry for entry in original_paths if entry is not old_outer]
    assert len(old_holes)==len(paths)-1
    entries=[]
    for path in paths:
        stats,poly=audit_path(path)
        assert poly.is_valid,(ident,'Invalid redesigned contour')
        entries.append({'path':path,'poly':poly,'protected':False,'source_draw':None,
                        'source_subpath':None,'deviation':0,'stats':stats})
    outer=entries[-1]['poly']
    assert max(abs(a-b) for a,b in zip(outer.bounds,design['new_bounds_mm']))<.002,(ident,'Redesigned bounds changed')
    # The default is essentially exact coverage. An explicitly reviewed curve
    # fit may allow up to 0.04 mm of boundary deviation, but this is not an
    # artwork clearance guarantee: print coverage must be verified separately.
    coverage_tolerance=design.get('source_coverage_tolerance_mm',.002)
    assert isinstance(coverage_tolerance,(int,float)) and not isinstance(coverage_tolerance,bool) and 0<coverage_tolerance<=.04,(ident,'Invalid source coverage tolerance')
    assert outer.buffer(coverage_tolerance).covers(old_outer['poly']),(ident,'New outline exceeds source coverage tolerance')
    for new,old in zip(entries[:-1],old_holes,strict=True):
        assert new['poly'].boundary.hausdorff_distance(old['poly'].boundary)<.0001,(ident,'Changed internal hole or slot')
        assert outer.contains(new['poly']),(ident,'Hole or slot outside exterior')
    proof=design.get('tab_geometry_proof',{})
    tolerance=proof.get('tolerance_mm',.002)
    regions=proof.get('regions_mm',[])
    assert 0<tolerance<=.002,(ident,'Invalid tab comparison tolerance')
    meta=original.get('design_metadata') or {}
    if meta.get('tab_width_mm') is not None or meta.get('tab_center_mm') is not None:
        assert regions,(ident,'Missing tab preservation region')
    if meta.get('tab_center_mm') is not None and meta.get('tab_width_mm') is not None and meta.get('tab_depth_mm') is not None:
        from shapely.ops import unary_union
        cx,shoulder=meta['tab_center_mm'];half=meta['tab_width_mm']/2
        tab_box=box(cx-half,shoulder,cx+half,shoulder+meta['tab_depth_mm'])
        assert unary_union([box(*r) for r in regions]).buffer(.002).covers(tab_box),(ident,'Tab proof does not cover the complete tab')
    for region in regions:
        assert len(region)==4 and region[0]<region[2] and region[1]<region[3],(ident,'Invalid tab preservation region')
        zone=box(*region)
        # Intersection at the shoulder can additionally contain zero-area
        # line fragments; compare polygonal material, not crop-edge artifacts.
        from shapely.ops import unary_union
        def polygonal(geometry):
            if geometry.geom_type=='Polygon':return [geometry]
            if hasattr(geometry,'geoms'):return [part for item in geometry.geoms for part in polygonal(item)]
            return []
        before=unary_union(polygonal(old_outer['poly'].intersection(zone)))
        after=unary_union(polygonal(outer.intersection(zone)))
        assert not before.is_empty and not after.is_empty,(ident,'Empty tab preservation region')
        assert before.boundary.hausdorff_distance(after.boundary)<=tolerance,(ident,'Changed tab geometry')
    # Clip first to the original source silhouette. Widening the new contour
    # must not reveal a neighbouring item in the pinned production source PDF.
    art=clip_art(original['art'],original)
    white=clip_art(original['white'],original)
    return {**original,'bounds':outer.bounds,'poly':outer,'paths':entries,'art':art,'white':white}


def pad_production_piece(source,ident,variants):
    """A reviewed production variant shares the source art, not its identity."""
    original_id=variants.get(ident,ident)
    assert source['id']==original_id,(ident,'Wrong PAD variant source')
    if ident==original_id:return source
    assert ident==original_id+'_safe' and original_id.startswith('len_pad_3T_'),(ident,'Invalid PAD variant identity')
    metadata={**(source.get('design_metadata') or {}),'redesign_source_id':original_id}
    return {**source,'id':ident,'canonical_id':ident,
            'paths':[dict(entry) for entry in source['paths']],
            'design_metadata':metadata}


def inputs(only=None):
    fixed_group='11_ascent_remaining/3T'
    if CONFIG.get('fixed_source_page3') and only and only in fixed_group:
        from fixed_page3_assets import additions
        return [(fixed_group,additions())]
    standalone=only and any(name in only for name in ('19_personal_fill','20_guide_stand_comparison'))
    batches={} if standalone else dict(source_inputs(only if only and any(n in only for n in ['06_len_pad','yanggum','11_ascent_remaining']) else None))
    logo_allocation=CONFIG.get('logo_fill_allocation',{})
    logo_source=None
    if any(not only or only in group for group in logo_allocation):
        logos=batches.get('02_extra_sheet/3T')
        if logos is None:logos=dict(source_inputs('02_extra_sheet/3T'))['02_extra_sheet/3T']
        original=next(p for p in logos if p['id']=='extra_3T_32')
        design=json.loads((ROOT/'configs/logo_smooth.json').read_text(encoding='utf-8'))
        logo_source=smooth_logo_source(original,design)
    for t in ['3T','5T']:
        group=f'02_extra_sheet/{t}'
        if group in batches:
            batches[group]=[p for p in batches[group] if p['id'] not in CONFIG['excluded_brand_parts'][t]]
    cadena={p['id']:p for p in batches.pop('04_ascent_cadena',[])}
    for group,ids in CONFIG['cross_sheet_cadena_allocation'].items():
        if group in batches:batches[group]+=[cadena[k] for k in ids]
    optional={p['id']:p for p in batches.get('09_yanggum/3T',[])}
    for group,ids in CONFIG.get('optional_fill_allocation',{}).items():
        if group in batches:batches[group]+=[optional[k] for k in ids]
    for group,ids in logo_allocation.items():
        if not only or only in group:
            assert logo_source is not None
            for ident in ids:
                clone={**logo_source,'id':ident,'canonical_id':'danba_logo_smooth',
                       'paths':[dict(entry) for entry in logo_source['paths']]}
                batches.setdefault(group,[]).append(clone)
    pad_allocation=CONFIG.get('pad_fill_allocation',{})
    if any(not only or only in group for group in pad_allocation):
        pad_source=batches.get('06_len_pad/3T')
        if pad_source is None:
            pad_source=dict(source_inputs('06_len_pad/3T'))['06_len_pad/3T']
        pad_parts={p['id']:p for p in pad_source}
        variants=CONFIG.get('pad_variant_sources',{})
        for group,ids in pad_allocation.items():
            if not only or only in group:
                batches.setdefault(group,[]).extend(
                    pad_production_piece(pad_parts[variants.get(ident,ident)],ident,variants) for ident in ids)
    allocation=CONFIG.get('personal_fill_allocation',{})
    if any(not only or only in group for group in allocation):
        from chain_keyring_parts import build_all
        personal={p['id']:p for record in build_all() if record['applicant'] is not None for p in record['pieces']}
        for group,ids in allocation.items():
            if not only or only in group:
                batches.setdefault(group,[]).extend(personal[ident] for ident in ids)
    additional_allocation=CONFIG.get('additional_stand_allocation',{})
    if any(not only or only in group for group in additional_allocation):
        from additional_stands import build_stands
        additional={p['id']:p for p in build_stands()}
        for group,ids in additional_allocation.items():
            if not only or only in group:
                batches.setdefault(group,[]).extend(additional[ident] for ident in ids)
    guide_allocation=CONFIG.get('guide_stand_allocation',{})
    if any(not only or only in group for group in guide_allocation):
        from guide_stand_variant import build_variant
        guide={p['id']:p for p in build_variant()}
        for group,ids in guide_allocation.items():
            if not only or only in group:
                batches.setdefault(group,[]).extend(guide[ident] for ident in ids)
    redesign_file=ROOT/'configs/contour_redesigns.json'
    redesigns=json.loads(redesign_file.read_text(encoding='utf-8')) if redesign_file.exists() else {}
    if 'parts' in redesigns:redesigns=redesigns['parts']
    visited=set();redesigned={}
    for parts in batches.values():
        for i,piece in enumerate(parts):
            ident=piece['id']
            if ident in redesigns:
                if ident not in redesigned:redesigned[ident]=redesign_outer_contour(piece,redesigns[ident])
                piece=parts[i]=redesigned[ident]
            if id(piece) not in visited:
                apply_canonical_contours(piece);visited.add(id(piece))
    if CONFIG.get('fixed_source_page3') and (not only or only in fixed_group):
        from fixed_page3_assets import additions
        batches[fixed_group]=additions()
    return [(group,parts) for group,parts in batches.items() if not only or only in group]


def reviewed_layout(name,pieces,rows=None):
    """Replay reviewed rigid placements without searching a new layout on rebuild."""
    if rows is None:
        data=json.loads((ROOT/'configs/a3_placements.json').read_text(encoding='utf-8'))
        rows=data['groups'][name]
    if rows and isinstance(rows[0],list):
        pages=[]
        for page_rows in rows:
            page_ids={r['id'] for r in page_rows}
            pages+=reviewed_layout(name,[p for p in pieces if p['id'] in page_ids],page_rows)
        assert {p['piece']['id'] for page in pages for p in page['placements']}=={p['id'] for p in pieces}
        return pages
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
    if CONFIG.get('fixed_source_page3'):
        if args.only and args.only in '11_ascent_remaining/3T':
            if args.plan:
                plan=json.loads((ROOT/'configs/fixed_page3_additions.json').read_text())
                print('PLAN 11_ascent_remaining/3T fixed 26 additions',len(plan['placements']))
                return
            from build_fixed_page3 import main as fixed_main
            return fixed_main()
        if not args.plan and (not args.only or args.only not in '19_personal_fill/3T'):
            parser.error('Pages 1 and 2 are frozen. This workflow permits writes only to page 3 or 4.')
    OUT.mkdir(parents=True,exist_ok=True)
    manifest_path=OUT/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'canvas_mm':list(SIZE),'groups':{},'physical_cut_test':False}
    manifest['revision']=CONFIG['revision']
    manifest['test_pieces_included']=False
    manifest['superseded_releases']=CONFIG['superseded_releases']
    manifest['physical_pages_per_selected_thickness']=CONFIG.get('selected_primary_pages',2)
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
        assert len(pages)==CONFIG.get('pages_per_group',{}).get(name,1),(name,'A3 sheet count regression')
        print('PLAN',name,len(pieces),len(pages),[len(p['placements']) for p in pages],flush=True)
        if args.plan:continue
        records=[write_page(OUT/name/f'sheet_{i+1:02}',p['placements']) for i,p in enumerate(pages)]
        manifest['groups'][name]=records
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
