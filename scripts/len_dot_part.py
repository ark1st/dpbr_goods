"""Small DOT character with an unscaled 18 mm mechanical tab below its feet."""
from pathlib import Path
import io,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon,box,LineString
from shapely.ops import unary_union
from shapely import affinity
from laser_paths import cut_path,audit_path

def create_dot_documents(root,thickness,draw_path,mm,settings):
    source=Path(root)/'assets/len/05_도트_캐릭터/캐릭터_도트.png'
    im=Image.open(source).convert('RGBA');bbox=im.getchannel('A').getbbox();im=im.crop(bbox)
    height=settings['art_height_mm'];scale=height/im.height;width=im.width*scale
    contours,_=cv2.findContours((np.asarray(im)[:,:,3]>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    shapes=[Polygon(c[:,0,:]).buffer(0) for c in contours if len(c)>=3]
    art=affinity.scale(unary_union(shapes),xfact=scale,yfact=scale,origin=(0,0))
    border=settings['clear_border_mm']
    # Close sub-pixel notches in the cutter body, never in the printed sprite.
    body=art.buffer(border+.35,quad_segs=24).buffer(-.35,quad_segs=24)
    body=Polygon(body.exterior)
    cx=(settings['foot_center_source_x_px']-bbox[0])*scale
    shoulder=body.bounds[3]
    depth=float(thickness.removesuffix('T'))-settings['tab_bottom_clearance_mm']
    half=settings['tab_width_mm']/2
    bridge=box(cx-half-1,shoulder-9,cx+half+1,shoulder)
    tip=.5
    tab=Polygon([(cx-half,shoulder-.1),(cx+half,shoulder-.1),
                 (cx+half,shoulder+depth-tip),(cx+half-tip,shoulder+depth),
                 (cx-half+tip,shoulder+depth),(cx-half,shoulder+depth-tip)])
    solid=unary_union([body,bridge,tab])
    assert solid.geom_type=='Polygon' and solid.is_valid
    solid=Polygon(solid.exterior)
    solid=affinity.translate(solid,10,10)
    path=cut_path(solid);stats,actual=audit_path(path)
    for y in [shoulder+.2,shoulder+depth-.6]:
        section=actual.intersection(LineString([(0,y+10),(200,y+10)]))
        assert abs(section.length-settings['tab_width_mm'])<.002
    assert abs(actual.bounds[3]-(10+shoulder+depth))<.002
    cut=fitz.open();page=cut.new_page(width=110*mm,height=110*mm);draw_path(page,path)
    printdoc=fitz.open();page=printdoc.new_page(width=110*mm,height=110*mm)
    buffer=io.BytesIO();im.save(buffer,format='PNG')
    page.insert_image(fitz.Rect(10*mm,10*mm,(10+width)*mm,(10+height)*mm),stream=buffer.getvalue())
    metadata={'art_height_mm':height,'art_width_mm':width,'source_crop_px':bbox,
        'foot_center_mm':cx+10,'tab_width_mm':settings['tab_width_mm'],'tab_depth_mm':depth,
        'shoulder_y_mm':shoulder+10,'common_base_slot_mm':[18.8,float(thickness.removesuffix('T'))],
        'clear_border_mm':border,'physical_fit_test':False}
    return cut,printdoc,metadata

def render_comparison(root,out,settings):
    """Dimension-faithful review from actual artwork; no generative mockup."""
    from build_a3_release import extract_layers,draw_path,MM
    from source_cache import source_path
    import json
    rows=json.loads((Path(root)/'configs/a3_placements.json').read_text(encoding='utf-8'))['groups']['05_len/3T']
    original=next(r for r in rows if r['id']=='len_3T_06')['source_bounds_mm']
    art=extract_layers(source_path('output/len_diorama_v1/3T/02_MASTER.ai'),['3_ARTWORK'])
    cut,small,meta=create_dot_documents(root,'3T',draw_path,MM,settings)
    doc=fitz.open();page=doc.new_page(width=210*MM,height=140*MM)
    page.draw_rect(page.rect,color=None,fill=(.98,.98,.98))
    ground=108
    def place(source,bounds,x):
        w=bounds[2]-bounds[0];h=bounds[3]-bounds[1]
        dest=fitz.Rect(x*MM,(ground-h)*MM,(x+w)*MM,ground*MM)
        page.show_pdf_page(dest,source,0,clip=fitz.Rect(*[v*MM for v in bounds]))
    place(art,original,15)
    bounds=(7.75,7.75,10+meta['art_width_mm']+2.25,meta['shoulder_y_mm']+meta['tab_depth_mm'])
    place(small,bounds,120)
    place(cut,bounds,120)
    page.draw_line((8*MM,ground*MM),(202*MM,ground*MM),color=(.4,.4,.4),width=.25)
    for x,y,text,size in [(9,10,'LEN / character size and mount review',13),
        (15,119,'Regular artwork: 76 mm',10),(120,119,'DOT artwork: 50 mm',10),
        (9,131,'3T: tab 18 x 2.6 mm; base slot drawn 17.9 x 2.9 mm (kerf-compensated, nominal 18.8 x 3).',9)]:
        page.insert_text((x*MM,y*MM),text,fontsize=size)
    page.get_pixmap(dpi=150,alpha=False).save(out)
