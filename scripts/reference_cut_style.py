"""Reproduce the supplied fixed-page stand style for new character art.

Original board is read only. The new printed sprite is uniformly scaled and
the linked star base is copied from its actual vectors with translation only.
The exterior surrounding a different sprite is a new approximation, not a
claim that the original generator or a source character path was recovered.
"""
from pathlib import Path
import hashlib,json,sys
import cv2
import numpy as np
import pymupdf as fitz
from PIL import Image
from shapely import affinity
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union
from svgpathtools import parse_path,Line,CubicBezier,Path as SVGPath

from laser_paths import cut_path,audit_path
from build_a3_release import extract_layers,polygon_of,draw_path,MM
from verify_laser_paths import contours
from chain_keyring_parts import stand_body_axis

REFERENCE_SHA256='3cfadac25e60f7650ac18dcf4f1972e078bff9a5adb6fab49b0b34ca51e82fc0'

def _xy(v):return f'{v.real:.9f} {v.imag:.9f}'

def translate_original_path(path,dx,dy):
    """Translate original line and cubic controls without scaling or refitting."""
    delta=complex(dx,dy);parts=[]
    for i,segment in enumerate(parse_path(path)):
        if i==0:parts.append('M'+_xy(segment.start+delta))
        if isinstance(segment,Line):parts.append('L'+_xy(segment.end+delta))
        elif isinstance(segment,CubicBezier):
            parts.append('C'+' '.join(_xy(z+delta) for z in (segment.control1,segment.control2,segment.end)))
        else:raise ValueError('Unexpected original reference segment')
    return ' '.join(parts)+' Z'

def read_reference(path):
    """Read, hash and index the selected reference cutting vectors."""
    path=Path(path);assert hashlib.sha256(path.read_bytes()).hexdigest()==REFERENCE_SHA256,'Unexpected reference source'
    doc=extract_layers(path,['LASER_CUT']);assert len(doc)==1
    assert all(abs(a-b)<.01 for a,b in zip([doc[0].rect.width/MM,doc[0].rect.height/MM],[420,297]))
    raw=[p for d in doc[0].get_drawings() for p in contours(d)]
    assert len(raw)==73,'Unexpected reference contour inventory'
    reference_hole=polygon_of(raw[1]);base=polygon_of(raw[67]);base_hole=polygon_of(raw[68]);slot=polygon_of(raw[69])
    assert base.contains(base_hole) and base.contains(slot)
    assert max(abs(a-b) for a,b in zip([reference_hole.bounds[2]-reference_hole.bounds[0],reference_hole.bounds[3]-reference_hole.bounds[1]],[2.5,2.5]))<.02
    return {'hole':raw[1],'base_outer':raw[67],'base_hole':raw[68],'base_slot':raw[69],
            'original_stand_outer':raw[55],'source_sha256':REFERENCE_SHA256}

def reference_star_paths(reference,origin=(0.,0.)):
    """Exact source star/hole/slot translated to an origin, in laser order."""
    outer=polygon_of(reference['base_outer']);dx=origin[0]-outer.bounds[0];dy=origin[1]-outer.bounds[1]
    paths=[translate_original_path(reference[k],dx,dy) for k in ['base_hole','base_slot','base_outer']]
    actual=[polygon_of(p) for p in paths]
    for p in paths:audit_path(p)
    assert max(a.boundary.hausdorff_distance(affinity.translate(polygon_of(reference[k]),dx,dy).boundary)
               for a,k in zip(actual,['base_hole','base_slot','base_outer'],strict=True))<1e-6
    return paths

def _splice_reference_tab(outline,reference,dx,dy,shoulder):
    """Use the exact source insert segments in the fitted new exterior."""
    source=parse_path(reference['original_stand_outer'])
    # Original stand55's seven segments define the insert, from the right
    # shoulder, around the lower corners, to the left shoulder.
    insert=SVGPath(*source[20:27]).reversed().translated(complex(dx,dy))
    path=parse_path(outline)
    below=[i for i,s in enumerate(path) if max(s.start.imag,s.end.imag)>shoulder+.05]
    assert below and below==list(range(min(below),max(below)+1)),'Cannot isolate one insert'
    start,end=min(below),max(below)
    # Exterior fitting can use a point inside the tiny source corner fillet;
    # a shoulder-length connector keeps the entire source insert unchanged.
    first,last=path[start].start,path[end].end
    assert abs(first.imag-shoulder)<.002 and abs(last.imag-shoulder)<.002
    segments=[*path[:start]]
    after=[*path[end+1:]]
    def lies_inside_line(line,target):
        # A source tab's tiny shoulder fillet can begin just behind the fitted
        # body line's endpoint. Connecting backward creates a microscopic loop.
        # Only trim a line when the tab point projects onto its interior.
        if not isinstance(line,Line):return False
        direction=line.end-line.start
        if abs(direction)<1e-9:return False
        t=((target-line.start)*direction.conjugate()).real/(abs(direction)**2)
        return 0<t<1 and abs(line.start+t*direction-target)<.002
    if segments and lies_inside_line(segments[-1],insert.start):
        segments[-1]=Line(segments[-1].start,insert.start)
    elif abs(first-insert.start)>1e-7:
        segments.append(Line(first,insert.start))
    segments.extend(insert)
    if after and lies_inside_line(after[0],insert.end):
        after[0]=Line(insert.end,after[0].end)
    elif abs(insert.end-last)>1e-7:
        segments.append(Line(insert.end,last))
    segments.extend(after)
    combined=SVGPath(*segments);assert combined.isclosed()
    return combined.d()

def reference_stand(image,reference,ink_height_mm=51.16):
    """Return source-style head-hole + stand-tab paths and artwork coordinates.

    51.16 mm matches the visible ink height measured in the supplied Muhani
    example; the entire transparent sprite keeps its aspect ratio. Alpha is
    traced with 2.5 mm bleed and fitted to cubic cuts, without a convex hull or
    a large closing operation. A short, wide foot web carries the original tab.
    """
    image=Image.open(image).convert('RGBA') if not isinstance(image,Image.Image) else image.convert('RGBA')
    alpha=np.asarray(image)[:,:,3];found,_=cv2.findContours((alpha>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    polygons=[Polygon(c[:,0,:]).buffer(0) for c in found if len(c)>=3]
    assert polygons,'Empty character image'
    alpha_ink=unary_union(polygons);scale=ink_height_mm/image.height
    ink=affinity.translate(affinity.scale(alpha_ink,xfact=scale,yfact=scale,origin=(0,0)),10,10)
    # The supplied board uses a sparse, smooth organic contour, not an exact
    # follower of each pixel edge. Simplify only the offset silhouette; the
    # artwork and the original mechanical vectors are never simplified.
    body=ink.buffer(2.5,quad_segs=24).simplify(.20,preserve_topology=True).buffer(-.4,quad_segs=16).buffer(.4,quad_segs=16).simplify(.015,preserve_topology=True)
    assert body.geom_type=='Polygon' and body.is_valid,'Art effects require an explicit reviewed connector'
    body=Polygon(body.exterior)
    axis=10+stand_body_axis(image)*scale
    # The reference hole is copied from its actual line/cubic controls.
    raw_hole=polygon_of(reference['hole']);hc=raw_hole.centroid
    # Anchor on the actual body centerline. A high side wing or weapon must not
    # suspend the ring above empty space at the body's horizontal center.
    center_section=body.intersection(LineString([(axis,body.bounds[1]-10),(axis,body.bounds[3]+10)]))
    assert not center_section.is_empty,'No body at the selected ring axis'
    target_hole=Point(axis,center_section.bounds[1]-1.25)
    holepath=translate_original_path(reference['hole'],target_hole.x-hc.x,target_hole.y-hc.y)
    hole=polygon_of(holepath);ring=target_hole.buffer(3.75,quad_segs=32)
    assert hole.distance(ink)>=1.0,'Reference hole would cut character ink'
    # Copy the bottom 2.296mm of the actual sample as a mechanical insert.
    refstand=polygon_of(reference['original_stand_outer']);tab_left=387.6604;tab_right=403.5556
    tab_top=122.0787;tab_bottom=124.3746542
    ref_tab=refstand.intersection(box(tab_left-.001,tab_top,tab_right+.001,tab_bottom+.001))
    assert ref_tab.geom_type=='Polygon' and not ref_tab.is_empty
    shoulder=body.bounds[3]
    tab=affinity.translate(ref_tab,xoff=axis-(tab_left+tab_right)/2,yoff=shoulder-tab_top)
    web=box(axis-10,shoulder-9,axis+10,shoulder)
    solid=unary_union([body,web,tab,ring])
    assert solid.geom_type=='Polygon' and solid.is_valid and solid.contains(hole),'Detached outline or head hole'
    solid=Polygon(solid.exterior);outline=cut_path(solid)
    outline=_splice_reference_tab(outline,reference,axis-(tab_left+tab_right)/2,shoulder-tab_top,shoulder)
    stats,actual=audit_path(outline)
    assert actual.buffer(.035).covers(ink),'Cut may enter the artwork'
    assert actual.contains(hole),'Hole no longer enclosed'
    # The generated insert must retain the reference's wall/slot interface.
    lower=box(axis-8.1,shoulder+.04,axis+8.1,shoulder+2.31)
    tab_delta=solid.intersection(lower).boundary.hausdorff_distance(actual.intersection(lower).boundary)
    assert tab_delta<.002,('Changed source-style tab',tab_delta)
    return {'paths':[holepath,outline], 'bounds_mm':list(actual.bounds),
            'art_rect_mm':[10,10,10+image.width*scale,10+image.height*scale],
            'art_height_mm':ink_height_mm,'head_hole_diameter_mm':2.5,
            'head_hole_to_edge_mm':actual.boundary.distance(hole.boundary),
            'tab_width_mm':tab_right-tab_left,'tab_depth_mm':tab_bottom-tab_top,
            'tab_boundary_deviation_mm':tab_delta,'outline_segments':stats['segments'],
            'source_sha256':REFERENCE_SHA256,'physical_test':False}

def reference_keyring(image, reference, ink_height_mm=40., *, linked=False):
    """Fit a top carrier and, for a linked charm, a second carrier at the foot.

    The 40 mm alpha height is measured from the fixed board's 16 keyrings.
    Carrier holes are copied from its actual vectors; silhouette is newly fitted.
    The image must first be tightly cropped without modifying its pixels.
    """
    image=Image.open(image).convert('RGBA') if not isinstance(image,Image.Image) else image.convert('RGBA')
    alpha=np.asarray(image)[:,:,3]
    ys,xs=np.nonzero(alpha>8)
    assert len(ys)>0,'Empty character image'
    scale=ink_height_mm/(ys.max()-ys.min()+1)
    found,_=cv2.findContours((alpha>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    ink0=unary_union([Polygon(c[:,0,:]).buffer(0) for c in found if len(c)>=3])
    ink=affinity.translate(affinity.scale(ink0,xfact=scale,yfact=scale,origin=(0,0)),10,10)
    body=ink.buffer(2.5,quad_segs=24).simplify(.20,preserve_topology=True).buffer(-.4,quad_segs=16).buffer(.4,quad_segs=16).simplify(.015,preserve_topology=True)
    assert body.geom_type=='Polygon' and body.is_valid,'Character requires a reviewed connecting web'
    body=Polygon(body.exterior)
    axis=10+stand_body_axis(image)*scale
    section=body.intersection(LineString([(axis,body.bounds[1]-10),(axis,body.bounds[3]+10)]))
    assert not section.is_empty,'No character at chosen carrier axis'
    hole_source=polygon_of(reference['hole']); hc=hole_source.centroid
    hole_paths=[];hole_polys=[];carriers=[]
    centers=[section.bounds[1]-1.25]
    if linked:
        centers.append(section.bounds[3]+1.25)
    for cy in centers:
        hole_path=translate_original_path(reference['hole'],axis-hc.x,cy-hc.y)
        hole=polygon_of(hole_path)
        assert hole.distance(ink)>=1.,'Carrier hole intersects or approaches artwork'
        hole_paths.append(hole_path);hole_polys.append(hole);carriers.append(Point(axis,cy).buffer(3.75,quad_segs=32))
    solid=unary_union([body,*carriers])
    assert solid.geom_type=='Polygon' and solid.is_valid,'Detached carrier'
    outline=cut_path(Polygon(solid.exterior));stats,actual=audit_path(outline)
    assert actual.buffer(.035).covers(ink),'Contour enters artwork'
    assert all(actual.contains(h) and actual.boundary.distance(h.boundary)>=2.35 for h in hole_polys),'Carrier wall too thin'
    for path in hole_paths:audit_path(path)
    return {'paths':[*hole_paths,outline],'bounds_mm':list(actual.bounds),
            'art_rect_mm':[10,10,10+image.width*scale,10+image.height*scale],
            'alpha_height_mm':ink_height_mm,'hole_diameter_mm':2.5,
            'hole_to_edge_mm':[actual.boundary.distance(h.boundary) for h in hole_polys],
            'hole_to_ink_mm':[h.distance(ink) for h in hole_polys],
            'ink_to_edge_mm':actual.boundary.distance(ink),'outline_segments':stats['segments'],
            'source_sha256':REFERENCE_SHA256,'physical_test':False}

def prepared_chain_image(image):
    """Crop transparent margins only; preserve all nonzero source RGBA pixels."""
    image=Image.open(image).convert('RGBA') if not isinstance(image,Image.Image) else image.convert('RGBA')
    bbox=image.getchannel('A').getbbox()
    assert bbox,'Empty source image'
    return image.crop(bbox)

def build_reference_additions(reference_path, output_dir, muhani_image):
    """Build three stand sets and four single-hole character keyrings.

    ``output_dir`` must be a caller-owned asset/cache directory; it receives
    cropped RGBA copies only. Original reference and source PNGs are read-only.
    Returned paths and art rectangles use millimetres and each base reuses an
    exact translated copy of the original vectors.
    """
    ref=read_reference(reference_path);output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    source=Path('assets/chain_keyring/추가스탠드')
    additions=[]
    for name in ('렘샤','적매화검'):
        image=source/f'{name}_stand60_prepared.png'
        item=reference_stand(image,ref);item.update(id=f'{name}_stand',kind='stand',image=str(image));additions.append(item)
        paths=reference_star_paths(ref,origin=(10,100));base=polygon_of(paths[-1])
        additions.append({'id':f'{name}_star_base','kind':'base','paths':paths,'bounds_mm':list(base.bounds),'source_sha256':REFERENCE_SHA256,'physical_test':False})
    # The archived Magadarakbang print keeps both reviewed Zero poses and their relative scale.
    zero=prepared_chain_image(Path('output/individual_assets/강민_stand_01/01_PRINT_300ppi.png'))
    pair_file=output_dir/'마가다락방_zero_pair.png';zero.save(pair_file)
    pair=reference_stand(zero,ref,ink_height_mm=44)
    pair.update(id='마가다락방_stand',kind='stand',image=str(pair_file));additions.append(pair)
    additions.append(dict(additions[1],id='마가다락방_star_base'))
    for name,image,kind in [('렘샤',source/'렘샤_fly300.png','keyring'),('적매화검',source/'적매화검_fly300.png','keyring'),('무한이',Path(muhani_image),'keyring'),('마가다락방',pair_file,'keyring')]:
        prepared=prepared_chain_image(image);path=output_dir/f'{name}_{kind}_prepared.png';prepared.save(path)
        item=reference_keyring(prepared,ref,ink_height_mm=38 if name=='마가다락방' else 40,linked=kind=='chain')
        item.update(id=f'{name}_{kind}',kind=kind,image=str(path),original_image=str(image));additions.append(item)
    return additions

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['stand','chain','keyring'],default='stand')
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--images',required=True,nargs='+',type=Path)
    parser.add_argument('--outdir',required=True,type=Path)
    args=parser.parse_args();ref=read_reference(args.reference);args.outdir.mkdir(parents=True,exist_ok=True)
    star=reference_star_paths(ref,origin=(10,100));results=[]
    for image in args.images:
        if args.kind in ('chain','keyring'):
            prepared=prepared_chain_image(image); prepared_path=args.outdir/(image.stem+'_prepared.png'); prepared.save(prepared_path)
            part=reference_keyring(prepared,ref,linked=args.kind=='chain');part['original_image']=str(image);part['image']=str(prepared_path)
        else:
            part=reference_stand(image,ref);part['image']=str(image)
        doc=fitz.open();page=doc.new_page(width=120*MM,height=150*MM)
        page.insert_image(fitz.Rect(*(v*MM for v in part['art_rect_mm'])),filename=part['image'])
        for path in [*part['paths'],*(star if args.kind=='stand' else [])]:draw_path(page,path,color=(1,0,0),width=.08)
        page.get_pixmap(dpi=120,alpha=False).save(str(args.outdir/(image.stem+'_REVIEW_ONLY.png')))
        results.append(part)
    group=args.kind+'s'
    (args.outdir/f'reference_{group}.json').write_text(json.dumps({'source_reference_sha256':REFERENCE_SHA256,'reference_star_paths':star,group:results,'physical_test':False},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'reference':REFERENCE_SHA256,'kind':args.kind,'count':len(results),'output':str(args.outdir)},ensure_ascii=False))

if __name__=='__main__':main()
