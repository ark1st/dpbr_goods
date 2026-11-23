"""Canonical, source-oriented per-piece deliverables; A3 is only a placement derivative.

Contours are copied with a translation only. No tracing, smoothing or scaling is
performed here. Artwork is isolated from its pinned source at 600 ppi so adjacent
parts and the source sheet's reference frame cannot leak into a movable asset.
"""
from pathlib import Path
import json, math, shutil
from build_a3_release import (ROOT, MM, inputs, clip_art, draw_path,
    transformed_cut_path, polygon_of)
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from vector_utils import svg_doc, layer
from artifact_hash import artifact_sha256
from pdf_layers import mark_pdf_layers

OUT=ROOT/'output/individual_assets'
FILES=['01_PRINT.pdf','01_PRINT_300ppi.png','02_MASTER.pdf','02_MASTER.ai',
       '03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK.pdf',
       '04_WHITE_INK_MASK_300ppi.png','preview.png','asset.json','README.md']

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8',newline='\n')

def collect(only=None):
    assets={}
    for group,parts in inputs():
        for part in parts:
            ident=part.get('canonical_id',part['id'])
            if ident not in assets:assets[ident]={'piece':{**part,'id':ident},'groups':[]}
            if group not in assets[ident]['groups']:assets[ident]['groups'].append(group)
    return {ident:entry for ident,entry in assets.items()
            if not only or any(only in group for group in entry['groups'])}

def isolation(doc,part,size):
    """Return the isolated artwork PDF and transparent pixels, at the same scale."""
    result=fitz.open();p=result.new_page(width=size[0]*MM,height=size[1]*MM)
    if doc is not None and doc[0].get_contents():
        source=clip_art(doc,part);b=part['bounds']
        p.show_pdf_page(fitz.Rect(2*MM,2*MM,(size[0]-2)*MM,(size[1]-2)*MM),source,0,
                        clip=fitz.Rect(*[v*MM for v in b]))
    # A source may contain many off-clip images. Compact each asset into a single
    # independently movable transparent image, retaining the 1:1 vector cutter.
    pix=p.get_pixmap(dpi=600,alpha=True)
    compact=fitz.open();cp=compact.new_page(width=p.rect.width,height=p.rect.height)
    if any(pix.samples[3::4]):cp.insert_image(cp.rect,stream=pix.tobytes('png'))
    return compact

def export_asset(entry):
    p=entry['piece'];b=p['bounds'];size=[b[2]-b[0]+4,b[3]-b[1]+4]
    folder=OUT/p['id'];folder.mkdir(parents=True,exist_ok=True)
    place={'piece':p,'x':2,'y':2,'rotation':0}
    paths=[transformed_cut_path(e['path'],place) for e in p['paths']]
    art=isolation(p['art'],p,size);white=isolation(p['white'],p,size)
    for doc,stem in [(art,'01_PRINT'),(white,'04_WHITE_INK_MASK')]:
        doc.save(folder/(stem+'.pdf'),garbage=4,deflate=True)
        doc[0].get_pixmap(dpi=300,alpha=True).save(folder/(stem+'_300ppi.png'))
    cut=fitz.open();cp=cut.new_page(width=size[0]*MM,height=size[1]*MM)
    for path in paths:draw_path(cp,path)
    cut.save(folder/'03_CUT_ONLY.pdf',garbage=4,deflate=True)
    write(folder/'03_CUT_ONLY.svg',svg_doc(*size,layer('LASER_CUT',''.join(
        f'<path d="{path}" fill="none" stroke="#ff0000" stroke-width="0.001"/>' for path in paths))))
    master=fitz.open();mp=master.new_page(width=size[0]*MM,height=size[1]*MM)
    oc={n:master.add_ocg(n,on=n=='PRINT_ARTWORK') for n in ['PRINT_ARTWORK','WHITE_INK_MASK','LASER_CUT']}
    streams={v:[] for v in oc.values()}
    for doc,name in [(art,'PRINT_ARTWORK'),(white,'WHITE_INK_MASK'),(cut,'LASER_CUT')]:
        if doc[0].get_contents():
            mp.show_pdf_page(mp.rect,doc,0)
            streams[oc[name]].append(master.xref_stream(mp.get_contents()[-1]))
    mark_pdf_layers(mp,streams)
    master.set_layer(-1,basestate='OFF',on=[oc['PRINT_ARTWORK']],off=[oc['WHITE_INK_MASK'],oc['LASER_CUT']])
    master.save(folder/'02_MASTER.pdf',garbage=4,deflate=True)
    shutil.copy2(folder/'02_MASTER.pdf',folder/'02_MASTER.ai')
    review=fitz.open();rp=review.new_page(width=mp.rect.width,height=mp.rect.height)
    if art[0].get_contents():rp.show_pdf_page(rp.rect,art,0)
    for path in paths:draw_path(rp,path,color=(.54,.62,.62),width=.10)
    rp.get_pixmap(dpi=120,alpha=False).save(folder/'preview.png')
    spec={'id':p['id'],'canvas_mm':size,'cut_size_mm':[size[0]-4,size[1]-4],
        'artwork_scale':1,'rotation_degrees':0,'translation_mm':[2-b[0],2-b[1]],
        'source_bounds_mm':list(b),'source':p['source'],'a3_groups':entry['groups'],
        'physical_cut_test':False,'pieces':1,'closed_contours':len(paths),
        'parts':[{'id':p['id'],'protected_original':any(e['protected'] for e in p['paths']),
                  'expected_paths':[list(polygon_of(path).exterior.coords) for path in paths]}],
        'design_metadata':p.get('design_metadata'),'artwork_rasterization_ppi':600,
        'ai_format':'PDF-compatible layers; image artwork and original vector contours',
        'white_ink_policy':'Source white only; absent white requires RIP setup',
        'files':{f:artifact_sha256(folder/f) for f in FILES if f not in ['asset.json','README.md']}}
    write(folder/'asset.json',json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    write(folder/'README.md',f'''# {p['id']}

![개별 에셋](preview.png)

실물 외곽 **{size[0]-4:.3f} × {size[1]-4:.3f}mm**. 원본 방향·100%, 외곽 밖 대지 여백2mm.
`02_MASTER.ai` / `.pdf`: 그림·백색·칼선 레이어 편집본(PDF 호환 AI).
`01_PRINT.pdf` / PNG: 그림만. `03_CUT_ONLY.pdf` / SVG: 원래 벡터 칼선, 빨강0.001mm.
`04_WHITE_INK_MASK`: 원본 제공 백색만. 없는 백색은 RIP에서 설정합니다.
그림은 제공 원본을600ppi로 분리했으며 생성형 보정은 없습니다. 실물 미검증.

이 파일은 보관·편집용 개별 에셋입니다. 실제 A3 출력은 [출력판](../../a3_release)에서 받습니다.
원본·대지 배치 대응: `asset.json`. [전체 에셋](../README.md)
''')
    return {'id':p['id'],'folder':folder.relative_to(ROOT/'output').as_posix(),
            'canvas_mm':size,'a3_groups':entry['groups'],'files':FILES}

def font(size,bold=False):
    candidates=[Path('/System/Library/Fonts/AppleSDGothicNeo.ttc'),
        Path('/System/Library/Fonts/Supplemental/AppleGothic.ttf'),
        Path('C:/Windows/Fonts')/('malgunbd.ttf' if bold else 'malgun.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    return ImageFont.truetype(str(next(p for p in candidates if p.exists())),size)

def linked_preview():
    """Actual holes set rigid rotations; metal rings are review-only graphics."""
    from shapely import affinity
    ids=['tuiing_01','golden_01','burnt_01','unfried_01']
    from build_a3_release import pieces_from
    assets={}
    for ident in ids:
        folder=OUT/ident
        part=pieces_from(fitz.open(folder/'03_CUT_ONLY.pdf'),fitz.open(folder/'01_PRINT.pdf'),None,ident)[0]
        assets[ident]={'piece':part}
    placed=[];connections=[];previous=None;pxmm=7
    for ident in ids:
        p=assets[ident]['piece'];holes=sorted([e['poly'] for e in p['paths'][:-1]],key=lambda q:q.centroid.y)
        assert len(holes)==2,(ident,'Need the two original linking holes')
        start,end=[h.centroid for h in holes]
        # Align the upper/lower hole axis to the hanging vertical chain.
        angle=90-math.degrees(math.atan2(end.y-start.y,end.x-start.x))
        rotated=affinity.rotate(p['poly'],angle,origin=(start.x,start.y))
        desired=(0,0) if previous is None else (previous[0],previous[1]+10)
        dx,dy=desired[0]-start.x,desired[1]-start.y
        shape=affinity.translate(rotated,dx,dy)
        newend=affinity.translate(affinity.rotate(end,angle,origin=(start.x,start.y)),dx,dy)
        if previous is not None:connections.append((previous,desired))
        placed.append((ident,p,shape,angle,dx,dy,start))
        previous=(newend.x,newend.y)
    xmin=min(q[2].bounds[0] for q in placed);ymin=min(q[2].bounds[1] for q in placed)-22
    xmax=max(q[2].bounds[2] for q in placed);ymax=max(q[2].bounds[3] for q in placed)+4
    W,H=1600,2350;bg=(247,244,236,255);im=Image.new('RGBA',(W,H),bg);dr=ImageDraw.Draw(im)
    dr.text((70,55),'줄줄이 튀잉 · 연결 완성 예시',font=font(48,True),fill='#3c443d')
    dr.text((72,125),'실제 4조각·구멍 위치 기준 / 원본 그림 합성 / 링은 조립 참고',font=font(23),fill='#77776f')
    origin=(540-(xmin+xmax)*pxmm/2,235-ymin*pxmm)
    def xy(x,y):return (origin[0]+x*pxmm,origin[1]+y*pxmm)
    def ring(a,b,width_mm=6):
        x=(a[0]+b[0])/2;y=(a[1]+b[1])/2;h=abs(b[1]-a[1])+2
        rect=[*xy(x-width_mm/2,y-h/2),*xy(x+width_mm/2,y+h/2)]
        dr.ellipse(rect,outline='#666c6c',width=9);dr.ellipse([rect[0]+2,rect[1]+2,rect[2]-2,rect[3]-2],outline='#c5cacc',width=3)
    ring((0,-21),(0,0),24)
    for a,b in connections:ring(a,b)
    labels=['튀잉','황금 튀잉','탄 튀잉','덜 익은 튀잉']
    for idx,(ident,p,shape,angle,dx,dy,start) in enumerate(placed):
        # Render source with the exact same affine map as its original paths.
        # Fit source into a padded raster; rotate pixels around the same hole.
        art=clip_art(p['art'],p)
        bounds=p['poly'].bounds;pad=2
        source_rect=fitz.Rect((bounds[0]-pad)*MM,(bounds[1]-pad)*MM,(bounds[2]+pad)*MM,(bounds[3]+pad)*MM)
        pix=art[0].get_pixmap(matrix=fitz.Matrix(pxmm/MM,pxmm/MM),clip=source_rect,alpha=True)
        source_im=Image.frombytes('RGBA',(pix.width,pix.height),pix.samples)
        # A direct PIL affine inverse samples artwork at the original coordinates.
        sb=shape.bounds;tw=math.ceil((sb[2]-sb[0]+4)*pxmm);th=math.ceil((sb[3]-sb[1]+4)*pxmm)
        a=math.radians(angle);c,s=math.cos(a),math.sin(a)
        tx=sb[0]-2;ty=sb[1]-2
        # Forward global: R(source-start)+start+(dx,dy).
        ox=start.x+dx-c*start.x+s*start.y;oy=start.y+dy-s*start.x-c*start.y
        inverse=(c,s,(c*(tx-ox)+s*(ty-oy)-(pix.x/pxmm))*pxmm,
                -s,c,(-s*(tx-ox)+c*(ty-oy)-(pix.y/pxmm))*pxmm)
        painted=source_im.transform((tw,th),Image.Transform.AFFINE,inverse,Image.Resampling.BICUBIC)
        panel=Image.new('RGBA',(tw,th),(0,0,0,0));pd=ImageDraw.Draw(panel)
        coords=[((x-tx)*pxmm,(y-ty)*pxmm) for x,y in shape.exterior.coords]
        pd.polygon(coords,fill=(248,255,253,245));pd.line(coords,fill='#a7b6b1',width=2)
        panel.alpha_composite(painted)
        for hole in p['paths'][:-1]:
            h=affinity.translate(affinity.rotate(hole['poly'],angle,origin=(start.x,start.y)),dx,dy)
            hd=[((x-tx)*pxmm,(y-ty)*pxmm) for x,y in h.exterior.coords]
            pd.polygon(hd,fill=bg);pd.line(hd,fill='#a7b6b1',width=2)
        im.alpha_composite(panel,(round(xy(tx,ty)[0]),round(xy(tx,ty)[1])))
        dr.text((1000,round(xy(0,(sb[1]+sb[3])/2)[1]-10)),f'{idx+1:02}  {labels[idx]}',font=font(30,True),fill='#535b52')
    dr.text((70,H-140),'투명 아크릴 3T · 칼선·인쇄 크기는 A3와 동일',font=font(27),fill='#535b52')
    dr.text((70,H-88),'연결 링 간격 10mm는 시안용 가정입니다. 실제 링 규격·조립 간섭은 실물 확인 전입니다.',font=font(22),fill='#77776f')
    im.convert('RGB').save(OUT/'linked_tuiing_assembly.png')
    write(OUT/'linked_tuiing_assembly.json',json.dumps({'ids':ids,'scale_pixels_per_mm':pxmm,
        'linking_holes_per_piece':2,'preview_hole_center_spacing_mm':10,'physical_test':False,
        'rings':'Illustrative hardware only; not acrylic cutting paths'},indent=2)+'\n')

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--finish-only',action='store_true');parser.add_argument('--only-group');args=parser.parse_args()
    records=[]
    OUT.mkdir(parents=True,exist_ok=True)
    if not args.finish_only:
        for ident,entry in sorted(collect(args.only_group).items()):
            export_asset(entry);print('ASSET',ident,flush=True)
    if args.finish_only or args.only_group:
        for file in sorted(OUT.glob('*/asset.json')):
            s=json.loads(file.read_text(encoding='utf-8'))
            records.append({'id':s['id'],'folder':file.parent.relative_to(ROOT/'output').as_posix(),
                'canvas_mm':s['canvas_mm'],'a3_groups':s['a3_groups'],'files':FILES})
    else:
        for file in sorted(OUT.glob('*/asset.json')):
            s=json.loads(file.read_text(encoding='utf-8'));records.append({'id':s['id'],'folder':file.parent.relative_to(ROOT/'output').as_posix(),'canvas_mm':s['canvas_mm'],'a3_groups':s['a3_groups'],'files':FILES})
    linked_preview()
    categories={}
    for row in records:
        for group in row['a3_groups']:categories.setdefault(group,[]).append(row)
    text='# 개별 에셋 · 실물 크기\n\nA3는 출력용 배치이며, 아래 파일은 원본 방향의 독립 에셋입니다. 각 조각의 그림·백색·벡터 칼선을 따로 편집할 수 있습니다. 외부30개 도안은 원본의 회전 상태도 유지합니다. 받침도 별도 조각입니다. 3T가 현재 선택이고 5T는 대안입니다.\n\n[출력용 A3](../a3_release) · [Len PAD 단독 원본·중복 출력 금지](../a3_release/06_len_pad) · [양검 단독 원본·중복 출력 금지](../a3_release/09_yanggum) · [단풍바람 원본 소스](../../assets)\n\n![줄줄이 튀잉 완성 예시](linked_tuiing_assembly.png)\n\n링은 참고용 합성이고 아크릴 제작 파일에 포함하지 않습니다. 실물 조립 미검증.\n'
    gallery=[]
    for group,rows in categories.items():
        tiles=[]
        for row in rows:
            im=Image.open(ROOT/'output'/row['folder']/'preview.png').convert('RGB');im.thumbnail((230,190))
            tile=Image.new('RGB',(250,220),'#f5f4ee');tile.paste(im,((250-im.width)//2,4))
            ImageDraw.Draw(tile).text((6,202),row['id'],font=font(16),fill='black');tiles.append(tile)
        contact=Image.new('RGB',(1500,220*math.ceil(len(tiles)/6)),'#f5f4ee')
        for i,tile in enumerate(tiles):contact.paste(tile,((i%6)*250,(i//6)*220))
        name=group.replace('/','_')+'_catalog.png';contact.save(OUT/name);gallery.append(name)
        text+=f'\n## {group}\n\n| 에셋 | 외곽 크기 mm |\n|---|---|\n'
        for row in rows:
            w,h=[v-4 for v in row['canvas_mm']]
            text+=f'| [{row["id"]}]({row["id"]}) | {w:.3f} × {h:.3f} |\n'
        text+=f'\n![개별 조각 목록]({name})\n'
    write(OUT/'README.md',text)
    manifest={'revision':'individual-assets-v1','assets':records,'asset_count':len(records),
        'files_per_asset':FILES,'support_files':['README.md','manifest.json','linked_tuiing_assembly.png','linked_tuiing_assembly.json']+gallery,
        'physical_test':False,'source_policy':'Same canonical pieces as A3, source orientation with translation only; original art rasterized at600ppi for independent editing.'}
    write(OUT/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'individual_assets':len(records)}),flush=True)

if __name__=='__main__':main()
