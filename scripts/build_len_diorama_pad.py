"""Len PAD layered slot-in acrylic diorama, V1.

The separated-asset pack in assets/len_pad is embedded as-is: the
painted base plate (five placeholder slot holes closed and eight real
slot windows cleared by scripts/prepare_len_pad_base.py), one backdrop
scene, four decoration islands separated from the bundled parts sheet
at load, and the character with her painted aura backdrop. Cut
geometry derives from each raster's alpha contours plus the 2.5 mm
clear border; slots and tabs follow the repo conventions
(18.8 mm slots, 18 mm tabs, 0.4 mm bottom clearance).
One base + six plates = seven pieces; 3T and 5T presets.
"""
from pathlib import Path
import sys,os,json,argparse,zipfile,base64,io,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon,box,LineString
from shapely import affinity,concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from vector_utils import runvc,path,poly_path,layer
from laser_paths import cut_path
from guide_fonts import GUIDE_FONT,GUIDE_BOLD,register_guide_fonts
from build_diorama import write_svg,render,cut_layer,rounded,svg_text,tab_shape,artwork_layer

OUT=ROOT/'output/len_diorama_pad_v1'
TMP=ROOT/'tmp/len_diorama_pad'
CFG=json.loads((ROOT/'configs/len_diorama_pad.json').read_text(encoding='utf-8'))
BOARD=tuple(CFG['board_mm'])
PPI=300/25.4
RED='#ff0000'
BLUE='#0000ff'
ZIP_NAME='Danpungbaram_Len_Diorama_PAD_V1_MAIN_7pcs_3T_5T.zip'
SRC=ROOT/'assets/len_pad'
PREP=SRC/'prepared'


def export_native(svg,folder,name='02_MASTER'):
    commands=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
        {'command':'document.save','params':{'path':str(folder/f'{name}.vectorcraft'),'format':'vectorcraft','compress':False}},
        {'command':'document.export','params':{'path':str(folder/f'{name}.ai'),'format':'ai','createLayers':True,'preserveEditing':True}}]
    cf=TMP/f'{folder.name}-{name}.json'
    cf.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',svg,'--commands',cf])


def export_png(svg,dest):
    cf=TMP/f'{dest.parent.name}-{dest.stem}.json'
    cf.write_text(json.dumps([{'command':'document.export','params':{'path':str(dest),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}}]),encoding='utf-8')
    runvc(['run','--in',svg,'--commands',cf])


def load_asset(spec):
    source=SRC/spec['file']
    im=Image.open(source)
    if im.mode!='RGBA': im=im.convert('RGBA')
    if spec.get('island_at_px'):
        a=np.asarray(im)
        n,labels,stats,_=cv2.connectedComponentsWithStats((a[...,3]>8).astype('uint8'),8)
        ex,ey=spec['island_at_px']
        sel=[i for i in range(1,n) if abs(int(stats[i,0])-ex)<40 and abs(int(stats[i,1])-ey)<40]
        assert sel,(spec['id'],ex,ey)
        idx=max(sel,key=lambda i:int(stats[i,4]))
        assert int(stats[idx,4])>10000,(spec['id'],ex,ey,[int(stats[i,4]) for i in sel])
        idx=sel[0]
        bx,by,bw,bh=int(stats[idx,0]),int(stats[idx,1]),int(stats[idx,2]),int(stats[idx,3])
        # Bundled islands overlap each other's bounding boxes: keep only this
        # island's own label so no neighbour fragment rides along on the plate.
        crop=a[by:by+bh,bx:bx+bw].copy()
        crop[labels[by:by+bh,bx:bx+bw]!=idx,3]=0
        im=Image.fromarray(crop,'RGBA')
        spec=dict(spec,source_bbox_px=[bx,by,bw,bh],
                  processing='island separated from the bundled parts sheet by '
                             'connected-component label; neighbour-bbox fragments '
                             'alpha-zeroed, island pixels untouched')
    else:
        a=np.asarray(im)
        ys,xs=np.nonzero(a[...,3]>8)
        assert len(ys),source
        x0,y0=int(xs.min()),int(ys.min())
        im=im.crop((x0,y0,int(xs.max())+1,int(ys.max())+1))
        spec=dict(spec,source_bbox_px=[x0,y0,im.size[0],im.size[1]],processing=None)
    pw,ph=im.size
    h=spec['art_height_mm'];s=h/ph;w=pw*s
    mask=(np.asarray(im)[:,:,3]>8).astype('uint8')
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    polys=[Polygon(c[:,0,:].astype(float)*[s,s]).buffer(0) for c in contours if cv2.contourArea(c)>6]
    assert polys,source
    main=max(polys,key=lambda p:p.area)
    # No ink may sit farther than the clear border from the kept silhouette:
    # far specks would print outside the cut piece.
    for p in polys:
        if p is main: continue
        assert main.distance(p)<CFG['clear_border_mm']-.1,(source.name,p.bounds)
    kept=np.zeros(mask.shape,np.uint8)
    for c in contours:
        if cv2.contourArea(c)>6: cv2.drawContours(kept,[c],-1,1,-1)
    far=cv2.distanceTransform(1-kept,cv2.DIST_L2,3)*s
    assert not ((far>=CFG['clear_border_mm']-.05)&(mask>0)).any(),(source.name,'stray ink beyond border')
    # Embed at the exact 300 ppi print size, but never upscale beyond the
    # native pixels: a raster below 300 ppi ships as-is and the renderer
    # scales it at export (300 ppi metadata adds no real resolution).
    tw,th=max(1,min(round(w*PPI),pw)),max(1,min(round(h*PPI),ph))
    res=im.resize((tw,th),Image.LANCZOS)
    buf=io.BytesIO();res.save(buf,'PNG',optimize=True)
    b64=base64.b64encode(buf.getvalue()).decode()
    ink=(f'<image x="0" y="0" width="{w:.6f}" height="{h:.6f}" '
         f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    return {'id':spec['id'],'src_name':source.name,
        'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_px':[pw,ph],'source_bbox_px':spec['source_bbox_px'],
        'resample_px':[tw,th],
        'w':w,'h':h,'ink':ink,'art':unary_union(polys),
        'processing':spec.get('processing'),
        'opaque_px':int((np.asarray(res)[:,:,3]>8).sum()),
        'native_cap':bool(tw<pw-1 or (tw==pw and th==ph and round(w*PPI)>pw)),
        'effective_ppi':round(tw/(w/25.4))}


def load_base():
    source=PREP/'01_베이스.png'
    im=Image.open(source)
    if im.mode!='RGBA': im=im.convert('RGBA')
    a=np.asarray(im)
    ys,xs=np.nonzero(a[...,3]>8)
    assert len(ys),source
    x0,y0=48,111
    x1,y1=int(xs.max())+1,int(ys.max())+1
    crop=im.crop((x0,y0,x1,y1));pw,ph=crop.size
    aw=CFG['base_art_mm'][0];ah_doc=CFG['base_art_mm'][1]
    s=aw/pw;h=ph*s
    assert abs(h-ah_doc)<.02,(h,ah_doc)
    tw,th=max(1,min(round(aw*PPI),pw)),max(1,min(round(h*PPI),ph))
    res=crop.resize((tw,th),Image.LANCZOS)
    buf=io.BytesIO();res.save(buf,'PNG',optimize=True)
    b64=base64.b64encode(buf.getvalue()).decode()
    ink=(f'<image x="0" y="0" width="{aw:.6f}" height="{h:.6f}" '
         f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    prov=json.loads((PREP/'provenance.json').read_text(encoding='utf-8'))
    return {'src_name':'prepared/01_베이스.png','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'prepared_from_sha256':prov['source_sha256'],'source_px':[pw,ph],
        'source_bbox_px':[x0,y0,pw,ph],'resample_px':[tw,th],
        'w':aw,'h':h,'ink':ink,'opaque_px':int((np.asarray(res)[:,:,3]>8).sum()),
        'native_cap':bool(tw<pw-1 or (tw==pw and th==ph and round(aw*PPI)>pw)),
        'effective_ppi':round(tw/(aw/25.4))}


def standee(a,base_thickness,mounts,plinth_rise=8,simplify_tol=.015):
    border=CFG['clear_border_mm']; art=a['art']
    body=art.buffer(border,quad_segs=28)
    if body.geom_type!='Polygon': body=concave_hull(body,ratio=.5)
    body=Polygon(body.exterior)
    shoulder=art.bounds[3]+border
    depth=base_thickness-CFG['tab_bottom_clearance_mm']
    mean_x=sum(m[0] for m in mounts)/len(mounts)
    half=CFG['tab_width_mm']/2
    tabs=[];bridges=[];tab_cx=[]
    for mx,my in mounts:
        cx=(mx-mean_x)+a['w']/2
        tab_cx.append(cx)
        tabs.append(tab_shape(cx,shoulder,depth))
        bridges.append(box(cx-half-4,shoulder-plinth_rise,cx+half+4,shoulder))
    union=unary_union([body]+bridges)
    if union.geom_type=='Polygon': union=Polygon(union.exterior)
    body=union.intersection(box(-80,-80,BOARD[0]+80,shoulder))
    if body.geom_type=='Polygon': body=Polygon(body.exterior)
    union=unary_union([body]+tabs)
    if union.geom_type=='Polygon': union=Polygon(union.exterior)
    shape=union.simplify(simplify_tol,preserve_topology=True)
    assert shape.geom_type=='Polygon' and shape.is_valid and not shape.interiors
    assert shape.contains(art)
    clearance=shape.boundary.distance(art)
    assert border-simplify_tol-.005<=clearance<=border+.05,(a['id'],clearance)
    for cx in tab_cx:
        section=shape.intersection(LineString([(cx-30,shoulder+.15),(cx+30,shoulder+.15)]))
        assert abs(section.length-CFG['tab_width_mm'])<.001,(a['id'],cx,section.length)
    assert depth>1 and abs(shape.bounds[3]-shoulder-depth)<.001
    return {'poly':shape,'tab_cx':tab_cx,'shoulder':shoulder,'depth':depth,'mount_mean_x':mean_x,'clearance':clearance}


def base_slots(preset):
    L=CFG['slot_length_mm']; r=CFG['slot_corner_radius_mm']; sw=preset['slot_width_mm']
    slots=[]
    for p in CFG['pieces']:
        for mx,my in p['mounts_mm']:
            slots.append((p['id'],mx,my,rounded(mx-L/2,my-sw/2,L,sw,r)))
    return slots


def standing_cuts(shapes):
    """Cut silhouettes as the plates stand in the assembly (front view, y up)."""
    out={}
    for p in CFG['pieces']:
        s=shapes[p['id']];mts=p['mounts_mm']
        txs=[mx-cx for (mx,my),cx in zip(mts,s['tab_cx'])]
        assert max(txs)-min(txs)<1e-9,(p['id'],txs)
        g=affinity.translate(s['poly'],txs[0],0)
        g=affinity.scale(g,xfact=1,yfact=-1,origin=(0,0))
        out[p['id']]=(affinity.translate(g,0,s['shoulder']),mts[0][1])
    return out


def assembly_clearance(shapes):
    """Plates sharing one depth row share one physical plane: their standing
    cuts must never touch. Art may overhang the base outline by at most
    12 mm (plum_left branch tips, by design)."""
    st=standing_cuts(shapes)
    rows={}
    for pid,(g,my) in st.items(): rows.setdefault(my,[]).append((pid,g))
    mind=float('inf');worst=None
    for my,members in rows.items():
        for i in range(len(members)):
            for j in range(i+1,len(members)):
                d=members[i][1].distance(members[j][1])
                if d<mind: mind,worst=d,(members[i][0],members[j][0])
    for pid,(g,my) in st.items():
        b=g.bounds
        assert b[0]>=-12 and b[2]<=CFG['base_mm'][0]+12,(pid,b[0],b[2])
    assert mind>=2,(worst,mind)
    over={pid:round(max(0,-g.bounds[0])+max(0,g.bounds[2]-CFG['base_mm'][0]),2)
          for pid,(g,my) in st.items() if g.bounds[0]<0 or g.bounds[2]>CFG['base_mm'][0]}
    return mind,worst,over


def front_coverage(shapes):
    """Front-view occlusion sweep: how much of each standing cut the rows
    in front of it cover, total and over the top 30% band where every
    key feature of this set (moon, stars, faces, blossoms) lives."""
    st=standing_cuts(shapes)
    out={}
    for pid,(g,my) in st.items():
        blockers=[gg for q,(gg,myy) in st.items() if myy<my]
        u=unary_union(blockers) if blockers else None
        b=g.bounds
        band=g.intersection(box(b[0],b[3]-.3*(b[3]-b[1]),b[2],b[3]))
        total=(u.intersection(g).area/g.area) if u else 0.
        top=(u.intersection(band).area/band.area) if u else 0.
        assert total<.65,(pid,round(total,3))
        assert top<.32,(pid,round(top,3))
        out[pid]={'total_pct':round(total*100,1),'top30_pct':round(top*100,1)}
    return out


def positioned(assets,shapes,preset):
    base=rounded(0,0,*CFG['base_mm'],CFG['base_corner_radius_mm'])
    slots=base_slots(preset)
    for pid,mx,my,s in slots:
        assert base.contains(s) and base.boundary.distance(s)>8,(pid,mx,my)
    for i in range(len(slots)):
        for j in range(i+1,len(slots)):
            gap=slots[i][3].distance(slots[j][3])
            assert gap>=2.99,(slots[i][:3],slots[j][:3],gap)
    items=[]
    for p in CFG['pieces']:
        a=assets[p['id']]; s=shapes[p['id']]
        poly=s['poly']; bx,by=poly.bounds[0],poly.bounds[1]
        x,y=p['board_xy_mm']; tx,ty=x-bx,y-by
        items.append({'name':p['id'],'poly':affinity.translate(poly,tx,ty),
                      'tx':tx,'ty':ty,'ink':a['ink'],'holes':[],
                      'art':(tx,ty,a['w'],a['h']),'opaque_px':a['opaque_px'],
                      'resample_px':a['resample_px']})
    tx,ty=CFG['base_board_xy_mm']; inset=CFG['base_art_inset_mm']; b=assets['base']
    # The raster's image-top is the plate's BACK edge; cut y0 is the front
    # edge, so the image is placed vertically mirrored to line up with the
    # cut outline and the slot windows cleared by the prep script.
    flip=f'translate({inset} {inset+b["h"]}) scale(1 -1)'
    items.append({'name':'base','poly':affinity.translate(base,tx,ty),'tx':tx,'ty':ty,
                  'ink':f'<g transform="{flip}">{b["ink"]}</g>',
                  'holes':[affinity.translate(s[3],tx,ty) for s in slots],
                  'art':(tx+inset,ty+inset,b['w'],b['h']),'opaque_px':b['opaque_px'],
                  'resample_px':b['resample_px']})
    for p in items:
        assert box(8,8,BOARD[0]-8,BOARD[1]-8).contains(p['poly']),(p['name'],p['poly'].bounds)
    gap=min(p['poly'].distance(q['poly']) for i,p in enumerate(items) for q in items[:i])
    assert gap>=6,gap
    return items,gap


def make_board(assets,shapes,preset,folder):
    items,gap=positioned(assets,shapes,preset)
    w,h=BOARD
    ink=layer('3_ARTWORK',artwork_layer(items))
    reference=layer('2_CORNER_REFERENCE',f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="{BLUE}" stroke-width="0.3"/>')
    cutting=layer('1_LASER_CUT',cut_layer(items))
    master=write_svg(folder/'02_MASTER.svg',w,h,ink+reference+cutting)
    printing=write_svg(folder/'01_PRINT.svg',w,h,ink+reference)
    write_svg(folder/'03_CUT_ONLY.svg',w,h,cutting)
    export_native(master,folder)
    export_png(printing,folder/'01_PRINT_300ppi.png')
    runvc(['convert',printing,folder/'01_PRINT.pdf'])
    runvc(['convert',folder/'03_CUT_ONLY.svg',folder/'03_CUT_ONLY.pdf'])
    depths=sorted({round(m[1],1) for p in CFG['pieces'] for m in p['mounts_mm']})
    labels=(svg_text(13,314,f'LEN DIORAMA PAD V1 / {preset["name"]} / 7 PIECES',4.0)
        +svg_text(13,321,'BASE / 280 x 71.2 cut / art 275 x 66.2 + 2.5 clear rim',3.1)
        +svg_text(13,328,f'8 SLOTS 18.8 x {preset["slot_width_mm"]:.2f} / rows y {depths} (bg: 3 tabs)',3.1)
        +svg_text(13,335,'BG 200x90  PLUM L 76x72  PLUM R 82x66  DRAGON 79x50  CHARACTER 58x84  CLOUD 62x28',3.0)
        +svg_text(13,342,f'TAB DEPTH {shapes["bg"]["depth"]:.2f} mm / FIT TEST FIRST',3.1,'#b55f46'))
    preview=write_svg(folder/'preview/flat_layout.svg',w,h,
        f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'+ink+reference+cut_layer(items,.17)+labels)
    render(preview,folder/'preview/flat_layout.png',2.2)
    preview.unlink()
    return items,gap


def fit_test(preset,folder):
    pw=CFG['slot_length_mm']; t=preset['part_thickness_mm']
    bw,bh=112,67; testbase=rounded(5,5,bw,bh,3)
    slots=[];labels=[];rows=[]
    for i,delta in enumerate(CFG['fit_test_offsets_mm']):
        col=i%3;row=i//3;x=24+col*36;y=17+row*19;width=round(t+delta,3)
        slots.append(rounded(x-pw/2,y-width/2,pw,width,CFG['slot_corner_radius_mm']))
        labels.append(svg_text(x,y+8,f'{i+1}: {width:.2f}',3.3,anchor='middle'))
        rows.append({'id':i+1,'path_slot_width_mm':width,'path_slot_length_mm':pw,'center_mm':[x,y]})
    cx=138;shoulder=46;depth=preset['base_thickness_mm']-CFG['tab_bottom_clearance_mm']
    key=unary_union([rounded(123,13,30,33,3),box(125,40,151,46),tab_shape(cx,shoulder,depth)])
    labels.append(svg_text(138,26,'TEST',4,anchor='middle'))
    labels.append(svg_text(138,33,'18 mm',3.5,anchor='middle'))
    labels.append(svg_text(138,59,f'{preset["name"]}',4,anchor='middle'))
    cut=''.join(path(cut_path(s),'none',RED,.001) for s in slots+[testbase,key])
    label=layer('2_LABELS_PRINT_OR_COPY_BY_HAND',''.join(labels))
    master=write_svg(folder/'04_FIT_TEST_MASTER.svg',160,78,label+layer('1_LASER_CUT',cut))
    write_svg(folder/'04_FIT_TEST_CUT_ONLY.svg',160,78,layer('1_LASER_CUT',cut))
    export_native(master,folder,'04_FIT_TEST_MASTER')
    write_svg(folder/'04_FIT_TEST_BASE_ONLY.svg',160,78,layer('1_LASER_CUT',''.join(path(cut_path(s),'none',RED,.001) for s in slots+[testbase])))
    write_svg(folder/'04_FIT_TEST_KEY_ONLY.svg',160,78,layer('1_LASER_CUT',path(cut_path(key),'none',RED,.001)))
    review=write_svg(folder/'preview/fit_test.svg',160,78,'<rect width="160" height="78" fill="#fffdf8"/>'+label+cut.replace('stroke-width="0.001"','stroke-width="0.18"'))
    render(review,folder/'preview/fit_test.png',2.2)
    return rows


def assembly(assets,shapes,preset,folder):
    # Axonometric assembly preview from the real cut polygons; illustrative only.
    ox,oy=30,150; dx,dy=.44,-.34
    bw,bh=CFG['base_mm']
    bt=preset['base_thickness_mm']; pt=preset['part_thickness_mm']
    base=rounded(0,0,bw,bh,CFG['base_corner_radius_mm'])
    slots=base_slots(preset)
    inset=CFG['base_art_inset_mm']; b=assets['base']
    parts=['<rect width="350" height="190" fill="#f7f3eb"/>']
    parts.append('<ellipse cx="181" cy="166" rx="162" ry="8" fill="#e9e2d5"/>')
    bt_transform=f'matrix(1 0 {dx} {dy} {ox} {oy})'
    parts.append(f'<g transform="{bt_transform}">'+path(poly_path(base),'#d4dedb','#99ada9',.35)+'</g>')
    top_transform=f'matrix(1 0 {dx} {dy} {ox} {oy-bt})'
    stage=path(poly_path(base),'#fafffc','#a4b6b1',.35)
    stage+=f'<g transform="translate({inset} {inset+b["h"]}) scale(1 -1)">{b["ink"]}</g>'
    for _,_,_,s in slots: stage+=path(poly_path(s),'#bdcbc5','#8eaaa1',.25)
    parts.append(f'<g transform="{top_transform}">{stage}</g>')
    # Draw rear first: backdrop, plums, then dragon/character row, cloud last.
    for pid in ['bg','plum_left','plum_right','dragon','character','cloud']:
        spec=next(p for p in CFG['pieces'] if p['id']==pid)
        mx=sum(m[0] for m in spec['mounts_mm'])/len(spec['mounts_mm'])
        my=spec['mounts_mm'][0][1]
        a=assets[pid]; s=shapes[pid]
        X=ox+mx+dx*my-a['w']/2; Y=oy+dy*my-bt-s['shoulder']
        body=path(poly_path(s['poly']),'#fafffc','#a6b7b3',.35)
        parts.append(f'<g transform="translate({X+dx*pt:.4f} {Y+dy*pt:.4f})">{body}</g>')
        parts.append(f'<g transform="translate({X:.4f} {Y:.4f})">{body}{a["ink"]}</g>')
    parts.append(svg_text(13,15,'LEN DIORAMA PAD V1',5,'#4d5148'))
    parts.append(svg_text(13,23,f'base {bw:.0f} x {bh:.1f} mm / 7 pieces / transparent acrylic',3.4))
    parts.append(svg_text(13,182,f'V1 / {preset["name"]} concept / PAD pack rasters as supplied',3.1))
    svg=write_svg(folder/'preview/assembly.svg',350,190,''.join(parts))
    render(svg,folder/'preview/assembly.png',2.7)
    svg.unlink()


def validate(assets,shapes,preset,items,gap,folder,rows):
    mind,worst,over=assembly_clearance(shapes)
    cov=front_coverage(shapes)
    im=Image.open(folder/'01_PRINT_300ppi.png')
    assert im.mode=='RGBA' and im.size==tuple(round(v*PPI) for v in BOARD)
    assert abs(im.info['dpi'][0]-300)<.1
    arr=np.asarray(im)
    blue=(arr[:,:,2]>240)&(arr[:,:,0]<10)&(arr[:,:,1]<10)&(arr[:,:,3]>150)
    w,h=BOARD
    for x,y in [(w/2,4),(w/2,h-4),(4,h/2),(w-4,h/2)]:
        xx,yy=round(x*PPI),round(y*PPI)
        assert blue[yy-3:yy+4,xx-3:xx+4].any()
    # Four margins: no non-blue ink near the sheet edges (ref line is blue).
    m=round(3.7*PPI)
    strips=[arr[:m,:,:],arr[-m:,:,:],arr[:,:m,:],arr[:,-m:,:]]
    nonblue=lambda a:int(((a[:,:,3]>10)&~((a[:,:,2]>240)&(a[:,:,0]<10)&(a[:,:,1]<10))).sum())
    assert [nonblue(s) for s in strips]==[0,0,0,0]
    reader=PdfReader(folder/'02_MASTER.ai');page=reader.pages[0]
    assert abs(float(page.mediabox.width)*25.4/72-BOARD[0])<.01
    assert abs(float(page.mediabox.height)*25.4/72-BOARD[1])<.01
    names=[r.get_object()['/Name'] for r in reader.trailer['/Root']['/OCProperties']['/OCGs']]
    assert names==['3_ARTWORK','2_CORNER_REFERENCE','1_LASER_CUT']
    text=(folder/'03_CUT_ONLY.svg').read_text(encoding='utf-8')
    assert text.count('<path ')==15 and text.count(' Z"')==15 and BLUE not in text
    assert len(items)==7 and sum(len(p['holes']) for p in items)==8
    for p in items:
        for hole in p['holes']: assert p['poly'].contains(hole)
    for p in CFG['pieces']:
        a=assets[p['id']]
        assert abs(a['w']/a['h']-a['source_px'][0]/a['source_px'][1])<1e-9
        x0,y0,x1,y1=a['art'].bounds
        # Contour vertices are pixel indices: the mask edge sits one index
        # beyond the last vertex, so allow that quantization gap explicitly.
        quant=1/max(1,min(a['source_px'])-1)
        assert abs((x1-x0)/(y1-y0)-a['source_px'][0]/a['source_px'][1])<.003+quant,(p['id'],)
    b=assets['base']
    assert abs(b['w']/b['h']-b['source_px'][0]/b['source_px'][1])<.003
    # Slot centres carry no ink; tab tips are unprinted.
    for p in items:
        if p['name']=='base':
            mask=np.zeros(arr.shape[:2],np.uint8)
            for hole in p['holes']:
                outline=np.round(np.asarray(hole.buffer(1.5).exterior.coords)*PPI).astype(np.int32)
                cv2.fillPoly(mask,[outline],1)
            assert not arr[:,:,3][mask.astype(bool)].any(),'Ink must clear every slot by 1.5 mm'
        else:
            s=shapes[p['name']]
            for cx in s['tab_cx']:
                x,y=p['tx']+cx,p['ty']+s['shoulder']+s['depth']/2
                assert arr[round(y*PPI),round(x*PPI),3]==0
    # Each embedded raster actually printed where the piece sits.
    for p in items:
        tx,ty,aw,ah=p['art']
        x0,y0=round(tx*PPI),round(ty*PPI)
        region=arr[y0:y0+round(ah*PPI),x0:x0+round(aw*PPI),3]
        # Compare at the embedded raster's own resolution: the renderer
        # resamples the embed at export, so a raw 300 ppi census is not
        # apples-to-apples with the embed's opaque pixel count.
        rpx=p['resample_px']
        if (region.shape[1],region.shape[0])!=tuple(rpx):
            region=np.asarray(Image.fromarray(region).resize(tuple(rpx),Image.BILINEAR))
        cnt=int((region>8).sum())
        assert .55*p['opaque_px']<=cnt<=1.6*p['opaque_px'],(p['name'],cnt,p['opaque_px'])
    depths=sorted({m[1] for p in CFG['pieces'] for m in p['mounts_mm']})
    heights={pid:round(preset['base_thickness_mm']+assets[pid]['h']+CFG['clear_border_mm'],2)
             for pid in assets if pid!='base'}
    report={'revision':1,'product':CFG['product'],'concept_title':CFG['concept_title'],
        'character':CFG['character'],
        'preset':preset,'canvas_mm':list(BOARD),
        'base_mm':CFG['base_mm'],'base_art_mm':CFG['base_art_mm'],
        'base_art_inset_mm':CFG['base_art_inset_mm'],
        'base_corner_radius_mm':CFG['base_corner_radius_mm'],
        'pieces':7,'finished_size_mm':CFG['finished_size_mm'],
        'assembled_height_mm':heights,'depth_rows_mm':[round(d,2) for d in depths],
        'cut_closed_paths':15,'hole_paths_first':True,'slot_count':8,
        'tab_width_mm':CFG['tab_width_mm'],
        'tab_depth_mm':shapes['bg']['depth'],
        'slot_length_mm':CFG['slot_length_mm'],'slot_width_mm':preset['slot_width_mm'],
        'dimensions_are':'cut path centerlines; no kerf compensation',
        'fit_status':'UNTESTED - cut fit coupon from the same sheets first',
        'physical_fit_test':False,'minimum_piece_gap_mm':gap,'ai_layers':names,
        'same_row_standing_clearance_mm':round(mind,2),'same_row_worst_pair':list(worst),
        'art_overhang_beyond_base_mm':over,
        'front_view_coverage_pct':cov,
        'blue_reference_four_sides':True,'unprinted_tabs_and_slots':True,
        'slot_ink_clearance_checked_mm':1.5,'margins_nonblue_ink':True,
        'base_plate':'supplied raster 01_베이스 printed as-is plus a 2.5 mm clear rim; '
                    '5 placeholder slot holes mirror-transplanted shut and 8 real slot '
                    'windows cleared - assets/len_pad/prepared/provenance.json',
        'assets':{p['id']:{'file':assets[p['id']]['src_name'],
            'sha256':assets[p['id']]['sha256'],
            'source_bbox_px':assets[p['id']]['source_bbox_px'],
            'source_px':assets[p['id']]['source_px'],
            'resample_px':assets[p['id']]['resample_px'],
            'art_width_mm':round(assets[p['id']]['w'],3),'art_height_mm':round(assets[p['id']]['h'],3),
            'minimum_art_to_cut_mm':shapes[p['id']]['clearance'],
            'resample':'LANCZOS; exact 300 ppi print size, never upscaled past native pixels','redrawn':False,
            'native_cap':assets[p['id']]['native_cap'],
            'effective_ppi':assets[p['id']]['effective_ppi'],
            'processing':assets[p['id']]['processing']}
            for p in CFG['pieces']},
        'fit_test_slots':rows}
    report['assets']['base']={'file':b['src_name'],'sha256':b['sha256'],
        'prepared_from_sha256':b['prepared_from_sha256'],
        'source_px':b['source_px'],'source_bbox_px':b['source_bbox_px'],
        'resample_px':b['resample_px'],
        'art_width_mm':round(b['w'],3),'art_height_mm':round(b['h'],3),
        'resample':'LANCZOS; exact 300 ppi print size, never upscaled past native pixels','redrawn':False,
        'native_cap':b['native_cap'],
        'effective_ppi':b['effective_ppi'],
        'processing':'placeholder holes closed + slot windows cleared '
                     '(scripts/prepare_len_pad_base.py, provenance.json)'}
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'parameters.json').write_text(json.dumps({**CFG,'selected_preset':preset},ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def guide(reports):
    register_guide_fonts()
    c=canvas.Canvas(str(OUT/'00_ASSEMBLY_GUIDE.pdf'),pagesize=(210*mm,297*mm))
    c.setTitle('렌 아크릴 디오라마 PAD V1 - 3T / 5T 슬롯 조립')
    def text(x,y,s,size=10,bold=False,color='#33362e'):
        c.setFillColor(color);c.setFont(GUIDE_BOLD if bold else GUIDE_FONT,size);c.drawString(x*mm,y*mm,s)
    def page(title,sub,num):
        c.setFillColor('#faf8f2');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        text(17,278,'DANPUNGBARAM / LEN DIORAMA PAD V1',9,True,'#bd664e')
        text(17,262,title,20,True);text(17,250,sub,9,color='#777567')
        c.setStrokeColor('#d8d4c7');c.line(17*mm,243*mm,193*mm,243*mm)
        text(17,10,'2026.11.21 / 1:1 mm / 실물 끼움 시험 전 도안',8,color='#777567');text(190,10,str(num),8)
    first=reports[0]['preset']['name']
    page(CFG['concept_title'],'렌 아크릴 슬롯 디오라마 PAD V1 · 베이스 1 + 파츠 6 = 총 7조각',1)
    c.drawImage(str(OUT/first/'preview/assembly.png'),19*mm,92*mm,width=172*mm,height=172*190/350*mm,mask='auto')
    text(17,84,'받침대 280 × 71.2 mm (아트 275 × 66.2 + 사방 2.5 mm 투명 테두리).',11,True)
    text(17,76,'완성 높이 3T 약 95.5 mm · 5T 약 97.5 mm / 깊이 71.2 mm.',10,True)
    text(17,68,'레이어 순서(뒤→앞): 배경(별밤·산맥) → 매화 좌·우 → 용·캐릭터 → 구름(맨 앞).',9)
    text(17,60,'그림 6종+베이스는 assets/len_pad 원본 PNG를 재그림 없이 그대로 넣었습니다.',9)
    text(17,52,'베이스 시안의 슬롯 자리 5개는 실제 탭 규격(18 mm)과 맞지 않는 예시라 봉합했습니다.',8.5,color='#777567')
    text(17,45,'실제 홈 8개(행 23/34/45/56)를 새로 배치하고 홈 주변 잉크를 비웠습니다.',8.5,color='#777567')
    text(17,38,'캐릭터는 어두운 오라 배경까지 원본 그대로이며 컷선이 그 실루엣을 따라갑니다.',8.5,color='#777567')
    text(17,31,'용(x=95)과 캐릭터(x=173)는 달·별·서로를 가리지 않도록 배치했습니다.',8.5,color='#777567')
    text(17,20,'위 그림은 조립 예상도이며, 실물 끼움은 시험 조각으로 확인하세요.',8.5,color='#777567')
    c.showPage()
    page('3T와 5T, 달라지는 두 치수','T = 판 두께(mm). 홈 너비와 돌기 길이는 서로 다른 판을 기준으로 정합니다.',2)
    for y,title,lines in [
        (229,'1. 홈의 짧은 방향 = 서 있는 파츠 판 두께',[
            '3T 기본 홈: 18.8 × 3.00 mm / 5T 기본 홈: 18.8 × 5.00 mm. 받침대 홈은 8개입니다.',
            '위 숫자는 절단 경로 치수이며, 실제 완성 홈 너비를 보장하는 값은 아닙니다.',
            '기본 파일에는 커프 보정이 없습니다. 같은 판의 시험 홈으로 너비를 결정하세요.']),
        (185,'2. 아래로 들어가는 돌기 길이 = 받침대 두께 - 0.40 mm',[
            '3T 받침대: 2.60 mm / 5T 받침대: 4.60 mm.',
            '돌기가 바닥 아래로 튀어나오지 않게 0.40 mm 짧게 설계했습니다.',
            '배경판은 돌기 3개, 매화·용·캐릭터·구름은 돌기 1개입니다. 돌기 폭은 공통 18 mm.']),
        (141,'3. 서로 다른 두께도 조합 가능',[
            '예: 파츠 3T + 받침대 5T → 홈 너비는 3T 기준, 돌기 길이는 4.60 mm.',
            '이 경우 파츠와 받침대는 서로 다른 재료에 나누어 잘라야 합니다.',
            '06_BASE_ONLY / 06_PIECES_ONLY 파일은 같은 좌표를 유지한 분리 도안입니다.'])]:
        text(17,y,title,11,True)
        for i,s in enumerate(lines):text(17,y-12-i*8,s,9)
    text(17,94,'홈의 네 모서리는 반경 0.35 mm, 돌기 끝은 0.40 mm 사선입니다.',9)
    text(17,84,'긴 방향 18.8 mm는 18 mm 돌기와 홈 모서리가 간섭하지 않도록 여유를 둔 값입니다.',9)
    text(17,74,'깊이 행(앞→뒤): 구름 23 → 용·캐릭터 34 → 매화 45 → 배경 56 mm.',9)
    text(17,68,'행 사이 웹 3T 8 mm / 5T 6 mm.',9)
    text(17,64,'단면 개념도',10,True)
    c.setStrokeColor('#879d94');c.setFillColor('#e4eee8');c.rect(25*mm,38*mm,69*mm,16*mm,fill=1,stroke=1)
    c.setFillColor('#faf8f2');c.rect(53*mm,38*mm,13*mm,16*mm,fill=1,stroke=0)
    c.setFillColor('#f1b18e');c.rect(54*mm,42*mm,11*mm,28*mm,fill=1,stroke=1)
    text(106,58,'위쪽: 파츠 판',9);text(106,49,'가로 판: 받침대',9)
    text(106,40,'아래쪽 틈: 0.40 mm',9)
    text(25,28,'설명용 확대도 / 실제 비례 아님',8,color='#777567')
    c.showPage()
    page('시험 조각부터 잘라 맞춰봅니다','최종 도안과 같은 판·같은 장비·같은 가공 설정에서 시험하세요.',3)
    c.drawImage(str(OUT/first/'preview/fit_test.png'),18*mm,143*mm,width=174*mm,height=174*78/160*mm,mask='auto')
    text(17,132,'시험판 1개 + 18 mm 돌기 시험키 1개. 본품 7조각과 별도입니다.',9,True)
    for i,s in enumerate([
        '시험 홈은 3 × 3 배열입니다. 왼쪽 위부터 1-9번, 각 행은 왼쪽에서 오른쪽 순서입니다.',
        '3T용: 2.60-3.40 mm / 5T용: 4.60-5.40 mm, 모두 0.10 mm 간격.',
        '파츠와 같은 판으로 시험키, 받침대와 같은 판으로 시험판을 자릅니다.',
        '숫자는 커팅선이 아닙니다. 인쇄하지 않으면 이 안내도를 보고 펜으로 적어도 됩니다.',
        '손으로 부드럽게 들어가고 기울어짐이 작은 홈을 고릅니다. 억지로 밀어 넣지 마세요.',
        '고른 홈의 표시 숫자를 --slot-width 값으로 입력해 최종 도안을 다시 만듭니다.',
        '전부 안 맞으면 실측 두께를 --part-thickness로 넣어 시험 범위를 옮깁니다.',
        '조립 전 보호필름을 제거합니다. 끼움 돌기와 홈 주변에는 인쇄 잉크를 올리지 않습니다.'
    ]):text(17,117-i*9,s,9)
    text(17,32,'두께 편차와 레이저가 태워 없애는 폭(커프)이 끼움에 영향을 줍니다.',9,True)
    text(17,22,'시험 결과에 맞춰 홈 너비를 조정하며, 장비 자동 보정은 중복 적용하지 않습니다.',8.5)
    c.showPage()
    page('제작 파일과 교체 규격','여섯 장의 그림 판을 순서대로 꽂는 무대형 / 그림은 분리에셋 원본 그대로',4)
    lines=[
        ('01_PRINT_300ppi.png / PDF','UV 인쇄: 여섯 파츠 그림과 베이스 아트, 파란 기준선. 투명 배경.'),
        ('02_MASTER.ai / .vectorcraft / .svg','편집 원본: 그림 / 파란 기준선 / 빨간 커팅선 3개 레이어.'),
        ('03_CUT_ONLY.svg / PDF','재단: 빨강 #FF0000, 두께 0.001 mm, 폐곡선 15개. 홈 8개부터 자릅니다.'),
        ('04_FIT_TEST_*','시험판과 시험키. 본품 전에 사용.'),
        ('06_BASE_ONLY / 06_PIECES_ONLY','서로 다른 두께의 판을 쓸 때 분리해 사용하는 도안.')]
    for i,(a,b) in enumerate(lines):
        y=229-i*23;text(17,y,a,10,True);text(17,y-9,b,8.7)
    text(17,84,'본품 작업영역 320 × 370 mm / 파란 기준선 (4, 4), 312 × 366 mm / 받침대 커트 모서리 R14.4.',9)
    text(17,74,'빨간 선은 홈 8개 + 외곽 7개 = 폐곡선 15개. 홈부터, 외곽은 마지막에 자릅니다.',9)
    text(17,64,'파란 선은 위치 기준이며 자르지 않습니다. 인쇄와 커팅은 같은 원점, 실제 크기 100%.',9)
    text(17,54,'3T와 5T는 대안입니다. 필요한 두께의 폴더 하나만 사용하면 됩니다.',9,True)
    text(17,41,'그림 교체: assets/len_pad에 같은 이름의 PNG를 넣고 빌더를 다시 실행하세요.',8.7)
    text(17,34,'베이스는 전처리 prepare_len_pad_base.py도 다시 실행합니다.',8.7)
    text(17,27,'원본 해상도: 베이스 약 192 ppi · 배경 약 203 ppi · 장식 파츠 155-250 ppi.',8.7)
    text(17,20,'캐릭터·용·배경 일러스트의 저작권은 원저자와 제작자에게 있습니다. 재배포하지 마세요.',8.7)
    text(17,13,'베이스 시안 슬롯 봉합 내역은 assets/len_pad/prepared/provenance.json에 기록되어 있습니다.',8.5,color='#777567')
    c.showPage()
    page('출력 전 치수 확인','A4 100% 출력 / 페이지 맞춤 해제 / 이 페이지는 인쇄 그림으로 사용하지 않습니다.',5)
    c.setStrokeColor('#33362e');c.setLineWidth(.5)
    sc=.5;bw,bh=CFG['base_mm'];x=(210-bw*sc)/2
    c.roundRect(x*mm,190*mm,bw*sc*mm,bh*sc*mm,CFG['base_corner_radius_mm']*sc*mm,stroke=1,fill=0)
    sw=3
    for p in CFG['pieces']:
        for mx,my in p['mounts_mm']:
            c.roundRect((x+(mx-9.4)*sc)*mm,(190+(bh-my-sw/2)*sc)*mm,18.8*sc*mm,sw*sc*mm,.35*sc*mm,stroke=1,fill=0)
    text(17,225,f'받침대 외곽 {bw:.0f} × {bh:.1f} mm (3T 기본 홈 8개 · 깊이 행 4개)',11,True)
    text(17,183,'위 도면은 50% 축소 개념도입니다. 실물 치수는 표기 값을 따르세요.',8.5,color='#777567')
    text(17,110,'조립 순서',11,True)
    for i,s in enumerate(['① 시험 조각으로 홈 너비 선택 → 해당 값으로 도안 재생성.',
                          '② 실제 크기 100%로 인쇄하고 같은 좌표로 커팅.',
                          '③ 배경(별밤·산맥)을 맨 뒤 홈에, 매화 좌·우를 그 앞 행에 삽입.',
                          '④ 용과 캐릭터를 중간 행에, 구름을 맨 앞 홈에 삽입.',
                          '⑤ 각 판의 어깨선이 받침대 윗면에 닿는지 확인.']):text(17,98-i*9,s,9)
    c.line(40*mm,42*mm,140*mm,42*mm)
    for i in range(17):
        xx=40+10*i;c.line(xx*mm,42*mm,xx*mm,(47 if i%5==0 else 45)*mm);text(xx-1.5,35,str(i*10),7)
    text(40,24,'160 mm 확인자 - 실제 자로 확인하세요.',9)
    c.save()


def readme(reports):
    first=reports[0]
    text_out=f'''# 렌 아크릴 슬롯 디오라마 PAD V1 · {CFG['concept_title']}

![조립 예상도]({first['preset']['name']}/preview/assembly.png)

**본품 1세트 = 받침대 1 + 파츠 6, 총 7조각.**
3T와 5T는 같은 세트의 두께별 대안이며, 각 폴더는 1세트 분량입니다.

받침대 **280 × 71.2 mm** (인쇄 아트 275 × 66.2 mm + 사방 2.5 mm 투명 테두리), 완성 높이 3T 약 95.5 mm · 5T 약 97.5 mm, 깊이 71.2 mm.
시안 규격(약 W150)에서는 여섯 실루엣 파츠가 서로를 가리므로, 무대를 **W280 · D71.2**로 키워 네 깊이 행에 나누어 세웁니다(행 사이 웹 3T 8 mm / 5T 6 mm).
레이어 순서(뒤→앞): **① 별밤·산맥 배경(200×90 mm) → ② 매화 좌·우 → ③ 은빛 용 + 캐릭터 → ④ 분홍 구름(맨 앞).**
깊이 행(앞→뒤): 구름 23 → 용·캐릭터 34 → 매화 45 → 배경 56 mm. 홈은 모두 8개입니다.
용(x=95)·캐릭터(x=173)는 같은 행에서 6.4 mm 간격으로 서 있고, 앞 판이 뒷 판의 달·별을 가리지 않습니다(배경 상단 30% 밴드 가림 17%).

**그림 6종과 베이스 아트는 assets/len_pad 원본 PNG를 다시 그리지 않고 그대로 사용했습니다.**
각 그림을 300ppi 인쇄 해상도로만 변환(랜초스)해 인쇄 레이어에 넣었습니다. 03_장식파츠에 뭉쳐 있던 매화 좌·우·용·구름은 알파 섬 단위로 분리해 각각 한 판으로 만들었습니다.
캐릭터는 어두운 오라 배경까지 원본 그대로이며 컷선이 그 실루엣을 따라갑니다.
베이스는 시안에 그려진 슬롯 자리 5개(실측 약 32.5×4.1 / 23.9×4.1 mm로 18 mm 탭과 맞지 않는 예시)를 인접 무늬 이식으로 봉합하고, 실제 홈 8개 위치에만 잉크를 비운 뒤 인쇄합니다(변경 내역: `assets/len_pad/prepared/provenance.json`).

일반 외곽 여백 2.5 mm, 레이저 선 빨강 0.001 mm, 홈 모서리반경 0.35 mm, 돌기끝 사선 0.40 mm.
배경은 돌기 3개, 매화·용·캐릭터·구름은 돌기 1개. 돌기 폭은 공통 18 mm로 서로 교체할 수 있습니다.

## 먼저 시험 조각

기본 홈 너비 3.00/5.00 mm는 **절단 경로의 시작값**입니다. 실물 끼움은 아직 시험하지 않았습니다.
같은 판·같은 설정으로 `04_FIT_TEST`를 잘라 맞는 홈을 고른 뒤 본품을 자르세요.
기본 시험 범위: 3T 2.60-3.40 mm / 5T 4.60-5.40 mm, 0.10 mm 간격.

- 홈의 짧은 너비: **서 있는 파츠 판**의 두께와 시험 결과에 따라 결정.
- 돌기 길이: **받침대**의 실측 두께에서 0.40 mm 뺀 값. 기본 3T 2.60 mm / 5T 4.60 mm.
- 돌기와 홈 주변은 인쇄하지 않습니다. 보호필름 제거 후 손으로 시험합니다.

## 파일

- `00_ASSEMBLY_GUIDE.pdf`: 조립·치수·시험 순서와 A4 실측 확인자.
- 두께별 폴더 `01_PRINT_300ppi.png`(+PDF): 파란 기준선을 포함한 투명 PNG, 300ppi.
- `02_MASTER.ai` / `.vectorcraft` / `.svg`: 그림, 기준선, 재단선의 3개 레이어. 그림은 래스터 임베드.
- `03_CUT_ONLY.svg`(+PDF): 빨강 0.001 mm 폐곡선 15개(홈 8+외곽 7), 홈을 먼저 자릅니다.
- `04_FIT_TEST_*`: 9개 홈 시험판과 18 mm 돌기 시험키.
- `06_BASE_ONLY.svg` / `06_PIECES_ONLY.svg`: 판 두께를 서로 다르게 쓸 때 분리된 편집 도안.
- `parameters.json`, `validation_report.json`: 적용 치수 및 파일검사 결과.

**ZIP에는 인쇄·재단에 바로 쓰는 파일만 넣었습니다**: 인쇄 PNG, 마스터 AI, 재단 파일, 시험편, `06_BASE_ONLY`, 미리보기 PNG.
편집 원본(`.vectorcraft`·`02_MASTER.svg`·`01_PRINT.pdf`·`06_PIECES_ONLY.svg`)은 용량 때문에 이 저장소 폴더에만 들어 있습니다.
빌더를 다시 실행하면 언제든 재생성됩니다.

본품 작업영역 320×370 mm. 3T/5T의 인쇄·재단 좌표는 같습니다.
파란 사각형(4,4), 312×366 mm은 위치기준이며 자르지 않습니다. 실제 크기 100%로 출력합니다.

## 치수 조정

저장소 루트에서:

```powershell
python scripts/prepare_len_pad_base.py
python scripts/build_len_diorama_pad.py
# 시험에서 고른 절단경로 홈 너비가 2.80 mm인 경우(예시일 뿐 권장값 아님)
python scripts/build_len_diorama_pad.py --part-thickness 3 --base-thickness 3 --slot-width 2.80 --name calibrated_3T
# 파츠 3T + 받침대 5T: 두 재료를 따로 커팅
python scripts/build_len_diorama_pad.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
```

`--part-thickness`와 `--base-thickness`에는 실측 소수값도 넣을 수 있습니다.
그림 높이·베이스 치수·홈 위치·돌기 폭은 `configs/len_diorama_pad.json`에서 관리합니다.
에셋 교체는 `assets/len_pad`의 같은 이름 PNG를 바꾸고(베이스는 전처리 스크립트도 다시) 빌더를 다시 실행하면 됩니다.

## 원본 해상도 안내

베이스 원본은 275 mm 폭 기준 약 192 ppi, 배경 약 203 ppi, 장식 파츠 155-250 ppi, 캐릭터는 300 ppi 이상입니다.
300 ppi 출력 파일은 이 원본을 랜초스로 리샘플한 값이며, 원본에 없는 디테일을 더하지 않습니다.

## 가공 참고

아래는 커프와 시험 가공 원칙의 근거입니다. 해당 업체의 장비수치를 우리 장비 값으로 대입하지 않았습니다.

- [Ponoko - Interlocking 3D laser cut designs](https://help.ponoko.com/en/articles/4527166-interlocking-3d-laser-cut-designs)
- [Ponoko - How much material does the laser burn away?](https://help.ponoko.com/en/articles/4442594-how-much-material-does-the-laser-burn-away)

캐릭터·용·배경 일러스트의 저작권은 원저자와 제작자에게 있습니다. 제작 파일을 재배포하지 마세요.
'''
    (OUT/'README.md').write_text(text_out,encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--part-thickness',type=float)
    ap.add_argument('--base-thickness',type=float)
    ap.add_argument('--slot-width',type=float)
    ap.add_argument('--name',default='custom')
    args=ap.parse_args()
    custom=any(v is not None for v in [args.part_thickness,args.base_thickness,args.slot_width])
    if custom:
        if args.part_thickness is None or args.base_thickness is None:ap.error('Custom mode needs both --part-thickness and --base-thickness')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',args.name):ap.error('--name accepts letters, numbers, underscores and hyphens only')
        width=args.slot_width if args.slot_width is not None else args.part_thickness
        if not (2<=args.part_thickness<=6 and 2<=args.base_thickness<=6 and 1.5<=width<=6.5):ap.error('Supported starting range: sheets 2-6 mm, slots 1.5-6.5 mm')
        presets=[{'name':args.name,'part_thickness_mm':args.part_thickness,'base_thickness_mm':args.base_thickness,'slot_width_mm':width}]
    else:presets=CFG['presets']
    OUT.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
    assets={p['id']:load_asset(p) for p in CFG['pieces']}
    assets['base']=load_base()
    reports=[]
    for preset in presets:
        folder=OUT/preset['name'];(folder/'preview').mkdir(parents=True,exist_ok=True)
        shapes={p['id']:standee(assets[p['id']],preset['base_thickness_mm'],p['mounts_mm'],p.get('plinth_rise_mm',8),p.get('simplify_mm',.015)) for p in CFG['pieces']}
        items,gap=make_board(assets,shapes,preset,folder)
        rows=fit_test(preset,folder)
        assembly(assets,shapes,preset,folder)
        for name,subset in [('BASE',[p for p in items if p['name']=='base']),
                            ('PIECES',[p for p in items if p['name']!='base'])]:
            content=layer('3_ARTWORK',artwork_layer(subset))+layer('1_LASER_CUT',cut_layer(subset))
            write_svg(folder/f'06_{name}_ONLY.svg',*BOARD,content)
        report=validate(assets,shapes,preset,items,gap,folder,rows);reports.append(report)
        print(json.dumps({'preset':preset['name'],'pieces':7,'cut_paths':15,
            'same_row_mm':report['same_row_standing_clearance_mm'],
            'coverage':report['front_view_coverage_pct'],
            'art':{k:round(v['w'],1) for k,v in assets.items() if k!='base'},
            'base':[round(assets['base']['w'],1),round(assets['base']['h'],1)]},ensure_ascii=False),flush=True)
    if not custom:
        guide(reports);readme(reports)
        zpath=OUT.parent/ZIP_NAME
        keep={'01_PRINT_300ppi.png','02_MASTER.ai','03_CUT_ONLY.svg','03_CUT_ONLY.pdf',
            '04_FIT_TEST_MASTER.ai','04_FIT_TEST_MASTER.vectorcraft','04_FIT_TEST_CUT_ONLY.svg',
            '04_FIT_TEST_BASE_ONLY.svg','04_FIT_TEST_KEY_ONLY.svg','06_BASE_ONLY.svg',
            'parameters.json','validation_report.json'}
        with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
            for file in sorted(OUT.rglob('*')):
                rel=file.relative_to(OUT)
                if not file.is_file(): continue
                inside=(file.parent==OUT
                    or (rel.parts[0] in ['3T','5T'] and (rel.name in keep
                        or (len(rel.parts)>2 and rel.parts[1]=='preview' and rel.suffix=='.png'))))
                if inside: z.write(file,Path('Danpungbaram_Len_Diorama_PAD_V1')/rel)
        with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
        print(json.dumps({'zip':ZIP_NAME,'zip_bytes':zpath.stat().st_size}),flush=True)
        print('Default package complete',flush=True)


if __name__=='__main__':
    main()
