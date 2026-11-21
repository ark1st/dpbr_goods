"""Len layered slot-in acrylic diorama, DOT V1 (character swap only).

Identical geometry and scenery to len_diorama_v1; the character plate
embeds the person's own dot-sprite ranking avatar (official_avatar_180,
prepared as assets/len/05_도트_캐릭터/캐릭터_도트.png with only unprintable
distant sparkles removed) as-is with NEAREST resample so the dot grid
stays crisp at 300 ppi. Scenery stays LANCZOS exactly like V1. No redraw.
One base + six plates = seven pieces; 3T and 5T presets.
"""
from pathlib import Path
import sys,os,json,argparse,zipfile,base64,io,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image,ImageChops,ImageDraw
from shapely.geometry import Polygon,box,Point,LineString
from shapely import affinity,concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from vector_utils import runvc,path,poly_path,layer
from guide_fonts import GUIDE_FONT,GUIDE_BOLD,register_guide_fonts
from build_diorama import write_svg,render,cut_layer,rounded,svg_text,tab_shape,artwork_layer

OUT=ROOT/'output/len_diorama_dot_v1'
TMP=ROOT/'tmp/len_diorama_dot'
CFG=json.loads((ROOT/'configs/len_diorama_dot.json').read_text(encoding='utf-8'))
BOARD=tuple(CFG['board_mm'])
PPI=300/25.4
RED='#ff0000'
BLUE='#0000ff'
ZIP_NAME='Danpungbaram_Len_Diorama_DOT_V1_MAIN_7pcs_3T_5T.zip'
LEN=ROOT/'assets/len'


def _dir(prefix):
    matches=[d for d in os.listdir(LEN) if d.startswith(prefix) and (LEN/d).is_dir()]
    assert len(matches)==1,(prefix,matches)
    return LEN/matches[0]

SRC=_dir('01_')


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
    folder=Path(ROOT/spec['source_dir']) if spec.get('source_dir') else SRC
    matches=[n for n in os.listdir(folder) if n.endswith('.png') and ':' not in n and n.startswith(spec['file_prefix'])]
    assert len(matches)==1,(spec['file_prefix'],matches)
    source=folder/matches[0]
    im=Image.open(source)
    if im.mode!='RGBA': im=im.convert('RGBA')
    # Optional vertical band crop (geometric subset, pixels untouched; the
    # person asked for a shorter backdrop at the same print scale).
    if spec.get('crop_y_frac'):
        f0,f1=spec['crop_y_frac']
        assert 0<=f0<f1<=1,('crop_y_frac',spec['crop_y_frac'])
        Wp,Hp=im.size
        im=im.crop((0,round(f0*Hp),Wp,round(f1*Hp)))
    a=np.asarray(im); alpha=a[...,3]
    ys,xs=np.nonzero(alpha>8)
    assert len(ys),source
    x0,y0,x1,y1=int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1
    crop=im.crop((x0,y0,x1,y1)); pw,ph=crop.size
    h=spec['art_height_mm']; s=h/ph; w=pw*s
    # Print-resolution raster: the deliverable PNG is 300 ppi, so the source is
    # resampled once to that exact size instead of shipping redundant pixels.
    tw,th=max(1,round(w*PPI)),max(1,round(h*PPI))
    resample={'nearest':Image.NEAREST,'lanczos':Image.LANCZOS}[spec.get('resample','lanczos')]
    res=crop.resize((tw,th),resample)
    # Optional visible corner rounding for full-bleed rectangular art (the
    # starfield panel): the raster alpha itself is rounded so the printed
    # art ends at the cut line; the cut outline then inherits the same
    # radius plus the clear border (R8 cut = 5.5 art + 2.5 border).
    corner_r=spec.get('corner_radius_mm')
    if corner_r:
        assert corner_r>=CFG['clear_border_mm'],('corner_radius_mm',corner_r)
        r_art=corner_r-CFG['clear_border_mm']
        cmsk=Image.new('L',(tw,th),0)
        ImageDraw.Draw(cmsk).rounded_rectangle([0,0,tw-1,th-1],radius=round(r_art/s),fill=255)
        res.putalpha(ImageChops.multiply(res.getchannel('A'),cmsk))
    buf=io.BytesIO(); res.save(buf,'PNG',optimize=True)
    b64=base64.b64encode(buf.getvalue()).decode()
    ink=(f'<image x="0" y="0" width="{w:.6f}" height="{h:.6f}" '
         f'xlink:href="data:image/png;base64,{b64}" href="data:image/png;base64,{b64}"/>')
    mask=(np.asarray(crop)[:,:,3]>8).astype('uint8')
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
    if corner_r:
        art=rounded(0,0,w,h,corner_r-CFG['clear_border_mm'])
    else:
        art=unary_union(polys)
    return {'id':spec['id'],'name':spec['id'],'src_name':source.name,
        'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_px':[pw,ph],'source_bbox_px':[x0,y0,x1-x0,y1-y0],'resample_px':[tw,th],
        'w':w,'h':h,'scale_mm_per_px':s,'ink':ink,'art':art,
        'opaque_px':int((np.asarray(res)[:,:,3]>8).sum())}


def standee(a,base_thickness,mounts):
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
        bridges.append(box(cx-half-4,shoulder-8,cx+half+4,shoulder))
    union=unary_union([body]+bridges)
    if union.geom_type=='Polygon': union=Polygon(union.exterior)
    body=union.intersection(box(-80,-80,BOARD[0]+80,shoulder))
    if body.geom_type=='Polygon': body=Polygon(body.exterior)
    union=unary_union([body]+tabs)
    if union.geom_type=='Polygon': union=Polygon(union.exterior)
    shape=union.simplify(.015,preserve_topology=True)
    assert shape.geom_type=='Polygon' and shape.is_valid and not shape.interiors
    assert shape.contains(art)
    clearance=shape.boundary.distance(art)
    assert border-.02<=clearance<=border+.05,(a['id'],clearance)
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
    cuts must never touch. Art may overhang the base outline by at most 12 mm
    (serpent coil, by design — V1 shipped with plum_left/serpent cut overlap
    of 1163 mm² at the same row; this check makes that class impossible)."""
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


def printable_region(base,slots):
    region=base.buffer(-CFG['clear_border_mm'])
    # 0.12 mm rasterization slack: clipped edges antialias one pixel wide,
    # the 1.5 mm spec itself is still asserted at exactly 1.5 in validate().
    region=region.difference(unary_union([s[3].buffer(1.62) for s in slots]))
    return region


def petal_shape(cx,cy,r,rot_deg):
    p=Point(0,0).buffer(1,quad_segs=20)
    p=affinity.scale(p,r*1.65,r*.7)
    p=affinity.rotate(p,rot_deg,origin=(0,0))
    return affinity.translate(p,cx,cy)


def base_art(region):
    """Vector decoration for the base, authored after reference A/B:
    lavender-pink cloud band with a central plum-blossom motif."""
    light,mid,deep='#f2dcf7','#e0b6f1','#c795e9'
    petal,petal_deep,core,star='#f1c3dd','#dc9cc8','#c98bd9','#ead2f6'
    shapes=[]
    def cloud(pts,fill):
        shapes.append((unary_union([Point(x,y).buffer(r,quad_segs=24) for x,y,r in pts]),fill))
    cloud([(14,6.1,2.7),(19.5,5.2,3.3),(26,4.6,2.9),(32.5,5.3,3.5),(38,6.3,2.5)],mid)
    cloud([(15.5,4.6,1.5),(21.5,3.8,1.8),(28,3.4,1.6),(34,3.9,1.9)],light)
    cloud([(261,6.1,2.7),(255.5,5.2,3.3),(249,4.6,2.9),(242.5,5.3,3.5),(237,6.3,2.5)],mid)
    cloud([(259.5,4.6,1.5),(253.5,3.8,1.8),(247,3.4,1.6),(241,3.9,1.9)],light)
    cloud([(22,55.5,1.7),(27,54.8,2.2),(33,54.3,1.9),(39,55.1,1.6)],light)
    cloud([(253,55.5,1.7),(248,54.8,2.2),(242,54.3,1.9),(236,55.1,1.6)],light)
    ring=unary_union([Point(137.5+1.0*np.cos(np.radians(90+72*k)),4.15+1.0*np.sin(np.radians(90+72*k))).buffer(.6,quad_segs=24) for k in range(5)])
    shapes.append((ring,petal))
    shapes.append((Point(137.5,4.15).buffer(.65,quad_segs=24),core))
    shapes.append((Point(137.5,4.15).buffer(.3,quad_segs=16),'#fdf0fa'))
    shapes.append((Point(129.3,5.0).buffer(1.0,quad_segs=24),petal_deep))
    shapes.append((Point(145.7,5.0).buffer(1.0,quad_segs=24),petal_deep))
    for cx,cy,rot,fill in [(46.5,4.7,25,petal_deep),(53,6.1,-15,deep),(107.5,4.9,-20,petal_deep),
                           (152,4.9,-15,petal_deep),(146,6.2,10,deep),(228.5,4.7,-25,petal_deep),
                           (222,6.1,15,deep),(21.5,5.6,-30,deep),(253.5,5.6,30,deep)]:
        shapes.append((petal_shape(cx,cy,1.8,rot),fill))
    def fourstar(cx,cy,r):
        k=r*.30
        return Polygon([(cx,cy+r),(cx+k,cy+k),(cx+r,cy),(cx+k,cy-k),(cx,cy-r),(cx-k,cy-k),(cx-r,cy),(cx-k,cy+k)])
    for cx,cy,r in [(11,55.7,.9),(264,55.7,.9),(64,55.4,.55),(211,55.4,.55),(137.5,56.2,.7)]:
        shapes.append((fourstar(cx,cy,r),star))
    out=[]
    for geom,fill in shapes:
        g=geom.intersection(region)
        parts=[g] if g.geom_type=='Polygon' else list(g.geoms)
        for part in parts:
            if part.is_empty or part.area<.3: continue
            if part.geom_type!='Polygon': continue
            if part.interiors: part=Polygon(part.exterior)
            assert part.difference(region).area<1e-9
            out.append(path(poly_path(part),fill))
    assert len(out)>=10
    return ''.join(out),len(out)


def positioned(assets,shapes,preset):
    base=rounded(0,0,*CFG['base_mm'],CFG['base_corner_radius_mm'])
    slots=base_slots(preset)
    for pid,mx,my,s in slots:
        assert base.contains(s) and base.boundary.distance(s)>7.4,(pid,mx,my)
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
                      'art':(tx,ty,a['w'],a['h']),'opaque_px':a['opaque_px']})
    region=printable_region(base,slots)
    ink,n_motifs=base_art(region)
    tx,ty=8,297
    items.append({'name':'base','poly':affinity.translate(base,tx,ty),'tx':tx,'ty':ty,
                  'ink':ink,'holes':[affinity.translate(s[3],tx,ty) for s in slots],'motifs':n_motifs})
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
    labels=(svg_text(13,119,'SKY / 250.9 x 97.7 mm / R8',3.5)
        +svg_text(13,213,'CHARACTER / 76 mm',3.5)
        +svg_text(98,213,'PLUM LEFT / 72 mm',3.2)
        +svg_text(166,187,'SERPENT / 50 mm',3.2)
        +svg_text(13,292,'MOUNTAINS / 52 mm',3.2)
        +svg_text(154,292,'PLUM RIGHT / 60 mm',3.2)
        +svg_text(13,360.5,'BASE / 275 x 60 mm / 8 SLOTS (sky, mountains: 2 tabs)',3.2)
        +svg_text(312,325,f'{preset["name"]} / 7 PIECES',4.3,anchor='end')
        +svg_text(312,332,f'Slots: 18.8 x {preset["slot_width_mm"]:.2f} mm / 8',3.3,anchor='end')
        +svg_text(312,339,f'Tab depth: {shapes["sky"]["depth"]:.2f} mm / rows {depths}',3.3,anchor='end')
        +svg_text(312,346,'FIT TEST FIRST',3.1,'#b55f46',anchor='end'))
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
    cut=''.join(path(poly_path(s),'none',RED,.001) for s in slots+[testbase,key])
    label=layer('2_LABELS_PRINT_OR_COPY_BY_HAND',''.join(labels))
    master=write_svg(folder/'04_FIT_TEST_MASTER.svg',160,78,label+layer('1_LASER_CUT',cut))
    write_svg(folder/'04_FIT_TEST_CUT_ONLY.svg',160,78,layer('1_LASER_CUT',cut))
    export_native(master,folder,'04_FIT_TEST_MASTER')
    write_svg(folder/'04_FIT_TEST_BASE_ONLY.svg',160,78,layer('1_LASER_CUT',''.join(path(poly_path(s),'none',RED,.001) for s in slots+[testbase])))
    write_svg(folder/'04_FIT_TEST_KEY_ONLY.svg',160,78,layer('1_LASER_CUT',path(poly_path(key),'none',RED,.001)))
    review=write_svg(folder/'preview/fit_test.svg',160,78,'<rect width="160" height="78" fill="#fffdf8"/>'+label+cut.replace('stroke-width="0.001"','stroke-width="0.18"'))
    render(review,folder/'preview/fit_test.png',2.2)
    return rows


def assembly(assets,shapes,preset,folder):
    # Axonometric assembly preview from the real cut polygons; illustrative only.
    ox,oy=30,150; dx,dy=.44,-.34
    bw,bh=CFG['base_mm']; front=bh
    bt=preset['base_thickness_mm']; pt=preset['part_thickness_mm']
    base=rounded(0,0,bw,bh,CFG['base_corner_radius_mm'])
    slots=base_slots(preset)
    region=printable_region(base,slots)
    deco,_=base_art(region)
    parts=['<rect width="350" height="190" fill="#f7f3eb"/>']
    parts.append('<ellipse cx="181" cy="166" rx="162" ry="8" fill="#e9e2d5"/>')
    bt_transform=f'matrix(1 0 {dx} {dy} {ox} {oy})'
    parts.append(f'<g transform="{bt_transform}">'+path(poly_path(base),'#d4dedb','#99ada9',.35)+'</g>')
    top_transform=f'matrix(1 0 {dx} {dy} {ox} {oy-bt})'
    stage=path(poly_path(base),'#fafffc','#a4b6b1',.35)+deco
    for _,_,_,s in slots: stage+=path(poly_path(s),'#bdcbc5','#8eaaa1',.25)
    parts.append(f'<g transform="{top_transform}">{stage}</g>')
    # Draw rear first: sky, mountains, plums and serpent, character last.
    for pid in ['sky','mountains','plum_left','serpent','plum_right','character']:
        spec=next(p for p in CFG['pieces'] if p['id']==pid)
        mx=sum(m[0] for m in spec['mounts_mm'])/len(spec['mounts_mm'])
        my=spec['mounts_mm'][0][1]
        a=assets[pid]; s=shapes[pid]
        X=ox+mx+dx*my-a['w']/2; Y=oy+dy*my-bt-s['shoulder']
        body=path(poly_path(s['poly']),'#fafffc','#a6b7b3',.35)
        parts.append(f'<g transform="translate({X+dx*pt:.4f} {Y+dy*pt:.4f})">{body}</g>')
        parts.append(f'<g transform="translate({X:.4f} {Y:.4f})">{body}{a["ink"]}</g>')
    parts.append(svg_text(13,15,'LEN DIORAMA DOT V1',5,'#4d5148'))
    parts.append(svg_text(13,23,'base 275 x 60 mm / 7 pieces / transparent acrylic',3.4))
    parts.append(svg_text(13,182,f'DOT V1 / {preset["name"]} concept / dot character, scenery as supplied',3.1))
    svg=write_svg(folder/'preview/assembly.svg',350,190,''.join(parts))
    render(svg,folder/'preview/assembly.png',2.7)
    svg.unlink()


def validate(assets,shapes,preset,items,gap,folder,rows):
    mind,worst,over=assembly_clearance(shapes)
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
        assert abs((x1-x0)/(y1-y0)-a['source_px'][0]/a['source_px'][1])<.003
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
        if p['name']=='base': continue
        tx,ty,aw,ah=p['art']
        x0,y0=round(tx*PPI),round(ty*PPI)
        region=arr[y0:y0+round(ah*PPI),x0:x0+round(aw*PPI),3]
        cnt=int((region>10).sum())
        assert .55*p['opaque_px']<=cnt<=1.6*p['opaque_px'],(p['name'],cnt,p['opaque_px'])
    depths=sorted({m[1] for p in CFG['pieces'] for m in p['mounts_mm']})
    heights={pid:round(preset['base_thickness_mm']+assets[pid]['h']+CFG['clear_border_mm'],2) for pid in assets}
    report={'revision':1,'product':CFG['product'],'concept_title':CFG['concept_title'],
        'preset':preset,'canvas_mm':list(BOARD),'base_mm':CFG['base_mm'],'pieces':7,
        'finished_size_mm':CFG['finished_size_mm'],'assembled_height_mm':heights,
        'depth_rows_mm':[round(d,2) for d in depths],
        'cut_closed_paths':15,'hole_paths_first':True,'slot_count':8,
        'tab_width_mm':CFG['tab_width_mm'],
        'tab_depth_mm':shapes['sky']['depth'],
        'slot_length_mm':CFG['slot_length_mm'],'slot_width_mm':preset['slot_width_mm'],
        'dimensions_are':'cut path centerlines; no kerf compensation',
        'fit_status':'UNTESTED - cut fit coupon from the same sheets first',
        'physical_fit_test':False,'minimum_piece_gap_mm':gap,'ai_layers':names,
        'same_row_standing_clearance_mm':round(mind,2),'same_row_worst_pair':list(worst),
        'art_overhang_beyond_base_mm':over,
        'blue_reference_four_sides':True,'unprinted_tabs_and_slots':True,
        'slot_ink_clearance_checked_mm':1.5,'margins_nonblue_ink':True,
        'base_decoration':'authored vector, reference A/B palette',
        'base_motif_count':items[-1]['motifs'],
        'assets':{p['id']:{'file':assets[p['id']]['src_name'],
            'sha256':assets[p['id']]['sha256'],'source_px':assets[p['id']]['source_px'],
            'crop_y_frac':p.get('crop_y_frac'),
            'corner_radius_mm':p.get('corner_radius_mm'),
            'source_bbox_px':assets[p['id']]['source_bbox_px'],
            'resample_px':assets[p['id']]['resample_px'],
            'art_width_mm':round(assets[p['id']]['w'],3),'art_height_mm':round(assets[p['id']]['h'],3),
            'minimum_art_to_cut_mm':shapes[p['id']]['clearance'],
            'resample':('NEAREST to exact 300 ppi print size (dot art)' if p.get('resample')=='nearest' else 'LANCZOS to exact 300 ppi print size'),
            'redrawn':False,
            'processing':p.get('processing_note','embedded as-is')}
            for p in CFG['pieces']},
        'fit_test_slots':rows}
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'parameters.json').write_text(json.dumps({**CFG,'selected_preset':preset},ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def guide(reports):
    register_guide_fonts()
    c=canvas.Canvas(str(OUT/'00_ASSEMBLY_GUIDE.pdf'),pagesize=(210*mm,297*mm))
    c.setTitle('렌 아크릴 디오라마 DOT V1 - 3T / 5T 슬롯 조립')
    def text(x,y,s,size=10,bold=False,color='#33362e'):
        c.setFillColor(color);c.setFont(GUIDE_BOLD if bold else GUIDE_FONT,size);c.drawString(x*mm,y*mm,s)
    def page(title,sub,num):
        c.setFillColor('#faf8f2');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        text(17,278,'DANPUNGBARAM / LEN DIORAMA DOT V1',9,True,'#bd664e')
        text(17,262,title,20,True);text(17,250,sub,9,color='#777567')
        c.setStrokeColor('#d8d4c7');c.line(17*mm,243*mm,193*mm,243*mm)
        text(17,10,'2026.11.21 / 1:1 mm / 실물 끼움 시험 전 도안',8,color='#777567');text(190,10,str(num),8)
    first=reports[0]['preset']['name']
    page('달빛과 매화, 그리고 뱀의 수호','렌 아크릴 슬롯 디오라마 · 베이스 1 + 파츠 6 = 총 7조각',1)
    c.drawImage(str(OUT/first/'preview/assembly.png'),19*mm,92*mm,width=172*mm,height=172*190/350*mm,mask='auto')
    text(17,79,'받침대 275 × 60 mm / 완성 높이 3T 약 103 mm · 5T 약 105 mm / 깊이 60 mm.',11,True)
    text(17,71,'레이어 순서(뒤→앞): 별밤 배경판 → 산맥·구름 → 매화 좌·우 → 뱀 수호령 → 캐릭터.',9)
    text(17,62,'그림 5종은 V1과 동일한 원본 PNG를 그대로 쓰고, 캐릭터 판만 본인 도트 아바타 렌더(official_avatar_180)를 그대로 넣었습니다.',9)
    text(17,53,'베이스 앞면 장식은 참고 A·B의 구름·꽃 문양 팔레트로 새로 벡터 디자인했습니다.',9)
    text(17,44,'시안 규격(약 W150)에서 네 파츠가 서로를 가리지 않는 무대 폭을 확보해 W275 · D60으로 키웠습니다.',8.5,color='#777567')
    text(17,35,'네 파츠는 각자 전용 폭을 차지합니다: 매화좌 → 뱀 → 캐릭터 → 매화우. 앞 판이 뒷 판을 가리지 않습니다.',8.5,color='#777567')
    text(17,23,'위 그림은 조립 예상도이며, 실물 끼움·기울어짐은 시험 조각으로 확인하세요.',8.5,color='#777567')
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
            '배경판·산맥은 돌기 2개, 매화·뱀·캐릭터는 돌기 1개입니다. 돌기 폭은 공통 18 mm.']),
        (141,'3. 서로 다른 두께도 조합 가능',[
            '예: 파츠 3T + 받침대 5T → 홈 너비는 3T 기준, 돌기 길이는 4.60 mm.',
            '이 경우 파츠와 받침대는 서로 다른 재료에 나누어 잘라야 합니다.',
            '06_BASE_ONLY / 06_PIECES_ONLY 파일은 같은 좌표를 유지한 분리 도안입니다.'])]:
        text(17,y,title,11,True)
        for i,s in enumerate(lines):text(17,y-12-i*8,s,9)
    text(17,94,'홈의 네 모서리는 반경 0.35 mm, 돌기 끝은 0.40 mm 사선입니다.',9)
    text(17,84,'긴 방향 18.8 mm는 18 mm 돌기와 홈 모서리가 간섭하지 않도록 여유를 둔 값입니다.',9)
    text(17,74,'깊이 행(앞→뒤): 캐릭터 10 → 뱀 20 → 매화 30 → 산맥 40 → 배경판 50 mm. 행 사이 웹 3T 7 mm / 5T 5 mm.',9)
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
    text(17,22,'시험 결과에 맞춰 홈 너비를 조정하는 방식이며, 장비의 자동 보정도 중복 적용하지 않습니다.',8.5)
    c.showPage()
    page('제작 파일과 교체 규격','여섯 장의 그림 판을 순서대로 꽂는 무대형 / 그림은 원본 에셋 그대로',4)
    lines=[
        ('01_PRINT_300ppi.png / PDF','UV 인쇄: 여섯 파츠 그림과 베이스 장식, 파란 기준선. 투명 배경.'),
        ('02_MASTER.ai / .vectorcraft / .svg','편집 원본: 그림 / 파란 기준선 / 빨간 커팅선 3개 레이어.'),
        ('03_CUT_ONLY.svg / PDF','재단: 빨강 #FF0000, 두께 0.001 mm, 폐곡선 15개. 홈 8개부터 자릅니다.'),
        ('04_FIT_TEST_*','시험판과 시험키. 본품 전에 사용.'),
        ('06_BASE_ONLY / 06_PIECES_ONLY','서로 다른 두께의 판을 쓸 때 분리해 사용하는 도안.')]
    for i,(a,b) in enumerate(lines):
        y=229-i*23;text(17,y,a,10,True);text(17,y-9,b,8.7)
    text(17,84,'본품 작업영역 320 × 370 mm / 파란 기준선 (4, 4), 312 × 366 mm / 별밤 판 모서리 R8 · 받침대 R6.',9)
    text(17,74,'빨간 선은 홈 8개 + 외곽 7개 = 폐곡선 15개. 홈부터, 외곽은 마지막에 자릅니다.',9)
    text(17,64,'파란 선은 위치 기준이며 자르지 않습니다. 인쇄와 커팅은 같은 원점, 실제 크기 100%.',9)
    text(17,54,'3T와 5T는 대안입니다. 필요한 두께의 폴더 하나만 사용하면 됩니다.',9,True)
    text(17,41,'그림 교체: 같은 이름의 PNG를 assets/len/01_ 폴더에, 도트 캐릭터는 assets/len/05_도트_캐릭터에 넣고 빌더를 다시 실행하세요.',8.7)
    text(17,32,'캐릭터·뱀·매화 그림의 저작권은 원저자와 제작자에게 있습니다. 파일을 재배포하지 마세요.',8.7)
    text(17,23,'인쇄 방향(전면/후면)과 백색 잉크 분판은 작업실 방식에 맞춰 설정합니다.',8.5,color='#777567')
    c.showPage()
    page('출력 전 치수 확인','A4 100% 출력 / 페이지 맞춤 해제 / 이 페이지는 인쇄 그림으로 사용하지 않습니다.',5)
    c.setStrokeColor('#33362e');c.setLineWidth(.5)
    sc=.5;bw,bh=CFG['base_mm'];x=(210-bw*sc)/2
    c.roundRect(x*mm,190*mm,bw*sc*mm,bh*sc*mm,CFG['base_corner_radius_mm']*sc*mm,stroke=1,fill=0)
    sw=3
    for p in CFG['pieces']:
        for mx,my in p['mounts_mm']:
            c.roundRect((x+(mx-9.4)*sc)*mm,(190+(bh-my-sw/2)*sc)*mm,18.8*sc*mm,sw*sc*mm,.35*sc*mm,stroke=1,fill=0)
    text(17,225,f'받침대 외곽 {bw:.0f} × {bh:.0f} mm (3T 기본 홈 8개 · 깊이 행 5개)',11,True)
    text(17,183,'위 도면은 50% 축소 개념도입니다. 실물 치수는 표기 값을 따르세요.',8.5,color='#777567')
    text(17,110,'조립 순서',11,True)
    for i,s in enumerate(['① 시험 조각으로 홈 너비 선택 → 해당 값으로 도안 재생성.',
                          '② 실제 크기 100%로 인쇄하고 같은 좌표로 커팅.',
                          '③ 배경판(별밤)을 맨 뒤 홈에, 산맥·구름을 그 앞에 수직으로 삽입.',
                          '④ 매화 좌·우를 뒤에서 두 번째 행에, 뱀 수호령을 매화와 캐릭터 사이 행에, 캐릭터를 맨 앞 홈에 삽입.',
                          '⑤ 각 판의 어깨선이 받침대 윗면에 닿는지 확인.']):text(17,98-i*9,s,9)
    c.line(40*mm,42*mm,140*mm,42*mm)
    for i in range(17):
        xx=40+10*i;c.line(xx*mm,42*mm,xx*mm,(47 if i%5==0 else 45)*mm);text(xx-1.5,35,str(i*10),7)
    text(40,24,'160 mm 확인자 - 실제 자로 확인하세요.',9)
    c.save()


def readme(reports):
    first=reports[0]
    text_out=f'''# 렌 아크릴 슬롯 디오라마 DOT V1 · 달빛과 매화, 그리고 뱀의 수호 · 도트 캐릭터판

![조립 예상도]({first['preset']['name']}/preview/assembly.png)

**본품 1세트 = 받침대 1 + 파츠 6, 총 7조각.**
3T와 5T는 같은 세트의 두께별 대안이며, 각 폴더는 1세트 분량입니다.

받침대 **275×60mm**, 완성 높이 3T 약 103mm · 5T 약 105mm, 완성 크기 약 W275×H103(3T)·H105(5T)×D60mm.
시안 규격(약 W150)에서 네 실루엣 파츠(매화좌·뱀·캐릭터·매화우)가 서로를 가리지 않도록 무대를 키워 W275·D60입니다(깊이 행 5개, 행 사이 웹 3T 7mm / 5T 5mm).
레이어 순서(뒤→앞): **① 별밤 배경판(251×98mm) → ② 산맥·구름 → ③ 매화 좌·우 → ④ 뱀 수호령 → ⑤ 캐릭터.**
깊이 행(앞→뒤): 캐릭터 10 → 뱀 20 → 매화 30 → 산맥 40 → 배경판 50mm. 홈은 모두 8개입니다.
네 파츠는 매화좌(x≈31) → 뱀(x≈100) → 캐릭터(x≈170) → 매화우(x≈240) 순으로 각자의 폭을 차지해, 앞 판이 뒷 판의 그림을 가리지 않습니다.

**그림 5종(별밤·산맥·매화 좌우·뱀)은 V1과 동일한 원본 PNG를 다시 그리지 않고 그대로 사용했습니다.**
캐릭터 판만 본인 캐릭터의 인게임 도트 아바타 렌더(official_avatar_180)로 교체했습니다. 도트 계단이 인쇄에서 그대로 보이도록 근접(NEAREST) 리샘플만 하고 재그림은 없습니다.
도트 소스의 장식 광점 11개 가운데 머리 옆 1개만 절단선 안에 들어와 유지했고, 주 실루엣에서 2.4mm 이상 떨어진 10개는 절단선 밖이라 인쇄에서 뺐습니다(알파만 0 처리, 나머지 픽셀은 원본과 바이트 동일 — assets/len/05_도트_캐릭터/provenance.json).
각 그림을 300ppi 인쇄 해상도로만 변환해 인쇄 레이어에 넣습니다. 별밤 배경판은 원본 상단 65% 띠를 사용하고(달·유성 포함, 인쇄 배율 그대로) 모서리는 R8로 재단합니다. 베이스 앞면의 구름·꽃 장식만
참고 A·B의 팔레트로 새로 벡터 디자인한 것입니다.

일반 외곽 여백2.5mm, 레이저 선 빨강0.001mm, 홈 모서리반경0.35mm, 돌기끝 사선0.40mm, 별밤 판 모서리 R8·받침대 R6 라운드.
배경판·산맥은 돌기 2개(±25/±35mm), 매화·뱀·캐릭터는 돌기 1개. 돌기 폭은 공통 18mm로 서로 교체할 수 있습니다.

## 먼저 시험 조각

기본 홈 너비3.00/5.00mm는 **절단 경로의 시작값**입니다. 실물 끼움은 아직 시험하지 않았습니다.
같은 판·같은 설정으로 `04_FIT_TEST`를 잘라 맞는 홈을 고른 뒤 본품을 자르세요.
기본 시험 범위: 3T 2.60-3.40mm / 5T 4.60-5.40mm, 0.10mm 간격.
번호는 왼쪽 위부터 가로 방향으로1-9입니다. 숫자 레이어는 커팅 대상이 아닙니다.

- 홈의 짧은 너비: **서 있는 파츠 판**의 두께와 시험 결과에 따라 결정.
- 돌기 길이: **받침대**의 실측 두께에서0.40mm 뺀 값. 기본3T 2.60mm /5T 4.60mm.
- 돌기와 홈 주변은 인쇄하지 않습니다. 보호필름 제거 후 손으로 시험합니다.
- 본품과 시험판은 별개입니다. 3T/5T 파일을 한꺼번에 출력하지 않습니다.

## 파일

- `00_ASSEMBLY_GUIDE.pdf`: 조립·치수·시험 순서와 A4 실측 확인자.
- 두께별 폴더 `01_PRINT_300ppi.png`(+PDF): 파란 기준선을 포함한 투명 PNG, 300ppi.
- `02_MASTER.ai` / `.vectorcraft` / `.svg`: 그림, 기준선, 재단선의3개 레이어. 그림은 래스터 임베드.
- `03_CUT_ONLY.svg`(+PDF): 빨강0.001mm 폐곡선15개(홈8+외곽7), 홈을 먼저 자릅니다.
- `04_FIT_TEST_*`: 9개 홈 시험판과18mm 돌기 시험키. 혼합두께이면 BASE/KEY 분리파일을 서로 다른 판에 출력.
- `06_BASE_ONLY.svg` / `06_PIECES_ONLY.svg`: 판 두께를 서로 다르게 쓸 때 분리된 편집 도안.
- `parameters.json`, `validation_report.json`: 적용 치수 및 파일검사 결과.

**ZIP에는 인쇄·재단에 바로 쓰는 파일만 넣었습니다**: 인쇄 PNG, 마스터 AI, 재단 파일, 시험편, `06_BASE_ONLY`, 미리보기 PNG.
편집 원본(`.vectorcraft`·`02_MASTER.svg`·`01_PRINT.pdf`·`06_PIECES_ONLY.svg`)은 용량 때문에 이 저장소 폴더에만 들어 있습니다.
빌더를 다시 실행하면 언제든 재생성됩니다.

본품 작업영역320×370mm. 3T/5T의 인쇄·재단 좌표는 같습니다.
파란 사각형(4,4),312×366mm은 위치기준이며 자르지 않습니다. 실제 크기100%로 출력합니다.
전면 정방향 인쇄가 기본입니다. 후면 인쇄라면 백색잉크와 반전 순서를 현장 방식에 맞춥니다.

## 치수 조정

저장소 루트에서:

```powershell
python scripts/build_len_diorama_dot.py
# 시험에서 고른 절단경로 홈 너비가 2.80mm인 경우(예시일 뿐 권장값 아님)
python scripts/build_len_diorama_dot.py --part-thickness 3 --base-thickness 3 --slot-width 2.80 --name calibrated_3T
# 파츠3T + 받침대5T: 두 재료를 따로 커팅
python scripts/build_len_diorama_dot.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
```

`--part-thickness`와`--base-thickness`에는 실측 소수값도 넣을 수 있습니다.
그림 높이·베이스 치수·홈 위치·돌기 폭은 `configs/len_diorama_dot.json`에서 관리합니다.
에셋 교체는 `assets/len/01_…` 폴더의 같은 번호 PNG를 바꾸고 빌더를 다시 실행하면 됩니다(도트 캐릭터는 assets/len/05_도트_캐릭터).

## 가공 참고

아래는 커프와 시험 가공 원칙의 근거입니다. 해당 업체의 장비수치를 우리 장비 값으로 대입하지 않았습니다.

- [Ponoko - Interlocking 3D laser cut designs](https://help.ponoko.com/en/articles/4527166-interlocking-3d-laser-cut-designs)
- [Ponoko - How much material does the laser burn away?](https://help.ponoko.com/en/articles/4442594-how-much-material-does-the-laser-burn-away)

캐릭터·뱀·배경 일러스트의 저작권은 원저자와 제작자에게 있습니다. 제작 파일을 재배포하지 마세요.
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
    reports=[]
    for preset in presets:
        folder=OUT/preset['name'];(folder/'preview').mkdir(parents=True,exist_ok=True)
        shapes={p['id']:standee(assets[p['id']],preset['base_thickness_mm'],p['mounts_mm']) for p in CFG['pieces']}
        items,gap=make_board(assets,shapes,preset,folder)
        rows=fit_test(preset,folder)
        assembly(assets,shapes,preset,folder)
        # Same-coordinate split sheets for mixed-thickness cutting.
        for name,subset in [('BASE',[p for p in items if p['name']=='base']),
                            ('PIECES',[p for p in items if p['name']!='base'])]:
            content=layer('3_ARTWORK',artwork_layer(subset))+layer('1_LASER_CUT',cut_layer(subset))
            write_svg(folder/f'06_{name}_ONLY.svg',*BOARD,content)
        report=validate(assets,shapes,preset,items,gap,folder,rows);reports.append(report)
        print(json.dumps({'preset':preset['name'],'pieces':7,'cut_paths':15,
            'same_row_mm':report['same_row_standing_clearance_mm'],'zip_mb':None,
            'art':{k:round(v['w'],1) for k,v in assets.items()}},ensure_ascii=False),flush=True)
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
                if inside: z.write(file,Path('Danpungbaram_Len_Diorama_DOT_V1')/rel)
        with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
        print(json.dumps({'zip':ZIP_NAME,'zip_bytes':zpath.stat().st_size}),flush=True)
        print('Default package complete',flush=True)


if __name__=='__main__':
    main()
