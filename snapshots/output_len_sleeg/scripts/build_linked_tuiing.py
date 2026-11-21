"""Four separate, full-scale linked-keyring plates from unchanged pixel artwork."""
from pathlib import Path
import sys,json,hashlib,math,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np,cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import box,Point,Polygon
from shapely.ops import unary_union
from shapely import affinity
from vector_utils import svg_doc,poly_path,path,layer,runvc
from build_diorama import write_svg,export_png,render,cut_layer,TMP as VC_TMP
from verify_release import check_ai,check_png,visible_layer,closed_contours

CFG=json.loads((ROOT/'configs/linked_tuiing.json').read_text(encoding='utf-8'))
SRC=ROOT/'assets/linked_tuiing'
OUT=ROOT/'output/linked_tuiing_v1'
TMP=ROOT/'tmp/linked_tuiing'
MM=72/25.4
DOC='https://docs.google.com/document/d/1zasgvxLgu7rkULyPR1h_cZRGx2P14C4--0cpYaosGhA'

def pixel_art(spec):
    source=SRC/(spec['id']+'_original.png');rgba=np.asarray(Image.open(source).convert('RGBA'))
    repeat=CFG['source_pixel_repeat'];native=rgba[::repeat,::repeat]
    assert np.array_equal(rgba,native.repeat(repeat,0).repeat(repeat,1))
    bbox=Image.fromarray(native[:,:,3]).getbbox()
    x0,y0,x1,y1=bbox;pixels=native[y0:y1,x0:x1];ph,pw=pixels.shape[:2]
    reconstructed=np.zeros_like(pixels);groups={};boxes=[]
    for y in range(ph):
        x=0
        while x<pw:
            color=tuple(int(v) for v in pixels[y,x]);end=x+1
            while end<pw and np.array_equal(pixels[y,end],pixels[y,x]):end+=1
            reconstructed[y,x:end]=color
            if color[3]:
                groups.setdefault(color,[]).append(f'M{x} {y}h{end-x}v1h{x-end}Z')
                boxes.append(box(x,y,end,y+1))
            x=end
    assert np.array_equal(reconstructed,pixels)
    ink=[];white=[]
    for (r,g,b,a),ds in groups.items():
        d=' '.join(ds);opacity=f' fill-opacity="{a/255:.10f}"' if a<255 else ''
        ink.append(f'<path d="{d}" fill="#{r:02x}{g:02x}{b:02x}"{opacity}/>')
        white.append(f'<path d="{d}" fill="#000000"{opacity}/>')
    inner=''.join(ink);white_inner=''.join(white)
    (SRC/(spec['id']+'.svg')).write_text(svg_doc(pw,ph,inner,'Unchanged pixel grid; source units, not print dimensions'),encoding='utf-8')
    scale=CFG['art_width_mm']/pw
    art=affinity.scale(unary_union(boxes),scale,scale,origin=(0,0))
    return {'spec':spec,'w':CFG['art_width_mm'],'h':ph*scale,'shape':art,
        'ink':f'<g transform="scale({scale:.12f})">{inner}</g>',
        'white':f'<g transform="scale({scale:.12f})">{white_inner}</g>',
        'source':{'file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_pixels':list(rgba.shape[1::-1]),'original_pixel_grid':list(native.shape[1::-1]),
            'cropped_pixel_grid':[pw,ph],'original_bbox_px':[n*repeat for n in bbox],
            'rgba_colors':len(groups),'pixel_run_roundtrip_exact':True,'alpha_preserved':True}}

def geometry(a):
    art=a['shape'];r=CFG['hole_diameter_mm']/2;ear=r+CFG['hole_edge_mm']
    hx=a['w']/2
    centers=[(hx,-r-CFG['hole_to_art_mm']),(hx,a['h']+r+CFG['hole_to_art_mm'])]
    pieces=[art.buffer(CFG['clear_border_mm'],quad_segs=24)]
    pieces += [Point(x,y).buffer(ear,quad_segs=96) for x,y in centers]
    pieces += [box(hx-ear+.5,centers[0][1],hx+ear-.5,1.5),
               box(hx-ear+.5,a['h']-1.5,hx+ear-.5,centers[1][1])]
    outer=unary_union(pieces).buffer(.5,quad_segs=32).buffer(-.5,quad_segs=32)
    assert outer.geom_type=='Polygon' and outer.is_valid
    outer=Polygon(outer.exterior)
    holes=[Point(x,y).buffer(r,quad_segs=96) for x,y in centers]
    assert outer.contains(art) and all(outer.contains(h) for h in holes)
    clearance=outer.boundary.distance(art)
    assert 2.47<=clearance<=2.501
    assert all(outer.boundary.distance(h)>=2.497 for h in holes)
    assert all(art.distance(h)>=CFG['hole_to_art_mm']-.001 for h in holes)
    return {'poly':outer,'holes':holes,'centers':centers,'art_to_cut_mm':clearance,
            'hole_to_edge_mm':[outer.boundary.distance(h) for h in holes],
            'hole_to_art_mm':[art.distance(h) for h in holes]}

def export_master(master,folder):
    info=json.loads(runvc(['run','--in',master,'--cmd','document.inspect']).splitlines()[-1])['result']
    layers={v['name']:v for v in info['layers']}
    hidden=[layers[n]['id'] for n in ['1_LASER_CUT','4_WHITE_INK_MASK']]
    commands=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
      {'command':'layer.setProps','params':{'ids':hidden,'visible':False,'printable':False}},
      {'command':'document.save','params':{'path':str(folder/'02_MASTER.vectorcraft'),'format':'vectorcraft','compress':False}},
      {'command':'layer.setProps','params':{'ids':hidden,'visible':True,'printable':True}},
      {'command':'document.export','params':{'path':str(folder/'02_MASTER.ai'),'format':'ai','createLayers':True,'preserveEditing':True}}]
    job=TMP/(folder.name+'-export.json');job.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',master,'--commands',job])
    # Export every plate first; changing initial OCG visibility must not discard cuts.
    with fitz.open(folder/'02_MASTER.ai') as doc:
        groups=doc.get_ocgs();on=[k for k,v in groups.items() if v['name'] in ['3_ARTWORK','2_CORNER_REFERENCE']]
        doc.set_layer(-1,basestate='OFF',on=on,off=[k for k in groups if k not in on])
        doc.save(TMP/(folder.name+'-master.ai'),garbage=4,deflate=True)
    shutil.copy2(TMP/(folder.name+'-master.ai'),folder/'02_MASTER.ai')

def build_plate(a,g):
    ident=a['spec']['id'];folder=OUT/ident;folder.mkdir(parents=True,exist_ok=True)
    W,H=CFG['sheet_mm'];x0,y0,x1,y1=g['poly'].bounds
    tx=(W-(x1-x0))/2-x0;ty=(H-(y1-y0))/2-y0
    shift=lambda p:affinity.translate(p,tx,ty)
    item={'poly':shift(g['poly']),'holes':[shift(h) for h in g['holes']]}
    assert box(8,8,W-8,H-8).contains(item['poly'])
    ink=f'<g transform="translate({tx:.9f} {ty:.9f})">{a["ink"]}</g>'
    white=f'<g transform="translate({tx:.9f} {ty:.9f})">{a["white"]}</g>'
    reference=f'<rect x="4" y="4" width="{W-8}" height="{H-8}" fill="none" stroke="#0000ff" stroke-width=".3"/>'
    cuts=cut_layer([item])
    master=write_svg(folder/'02_MASTER.svg',W,H,
        layer('3_ARTWORK',ink)+layer('2_CORNER_REFERENCE',reference)+layer('1_LASER_CUT',cuts)+layer('4_WHITE_INK_MASK',white))
    export_master(master,folder)
    printing=write_svg(folder/'01_PRINT.svg',W,H,ink+reference)
    export_png(printing,folder/'01_PRINT_300ppi.png')
    runvc(['convert',printing,folder/'01_PRINT.pdf'])
    cutting=write_svg(folder/'03_CUT_ONLY.svg',W,H,layer('1_LASER_CUT',cuts))
    runvc(['convert',cutting,folder/'03_CUT_ONLY.pdf'])
    wp=write_svg(folder/'04_WHITE_INK_MASK.svg',W,H,white)
    export_png(wp,folder/'04_WHITE_INK_MASK_300ppi.png')
    runvc(['convert',wp,folder/'04_WHITE_INK_MASK.pdf'])
    preview=f'<rect width="{W}" height="{H}" fill="#fffdf8"/>'
    preview+=path(poly_path(item['poly']),'#e9f4f4','#7d9a9c',.2)+ink
    for hole in item['holes']:preview+=path(poly_path(hole),'#fffdf8','#dd6868',.18)
    preview+=reference
    pv=write_svg(folder/'preview.svg',W,H,preview);render(pv,folder/'preview.png',3)
    check_ai(folder/'02_MASTER.ai',(W,H),3)
    check_png(folder/'01_PRINT_300ppi.png',(W,H))
    with fitz.open(folder/'03_CUT_ONLY.pdf') as doc:
        ds=doc[0].get_drawings();assert len(ds)==closed_contours(ds)==3
        assert all(p['fill'] is None and p['color']==(1,0,0) and abs(p['width']/MM-.001)<1e-5 for p in ds)
        for d,hole in zip(ds[:2],item['holes']):assert max(abs(v/MM-b) for v,b in zip(d['rect'],hole.bounds))<.002
    im=np.asarray(Image.open(folder/'01_PRINT_300ppi.png').convert('RGBA'))
    for h in item['holes']:
        mask=np.zeros(im.shape[:2],np.uint8)
        cv2.fillPoly(mask,[np.round(np.asarray(h.buffer(.5).exterior.coords)*300/25.4).astype(np.int32)],1)
        assert not im[:,:,3][mask.astype(bool)].any()
    with fitz.open(folder/'02_MASTER.ai') as doc:
        with visible_layer(doc,'4_WHITE_INK_MASK') as white_doc:assert white_doc[0].get_drawings()
    report={'variant':a['spec'],'canvas_mm':[W,H],'quantity':1,'art_mm':[a['w'],a['h']],
      'acrylic_mm':[x1-x0,y1-y0],'holes':2,'hole_diameter_mm':4,'hole_centers_mm':[[x+tx,y+ty] for x,y in g['centers']],
      'nominal_art_border_mm':2.5,'measured_art_border_mm':g['art_to_cut_mm'],
      'hole_to_edge_mm':g['hole_to_edge_mm'],'hole_to_art_mm':g['hole_to_art_mm'],
      'closed_cut_paths':3,'cut_stroke_mm':.001,'source':a['source'],
      'source_aspect_ratio_preserved':True,'no_generative_edits':True,'physical_assembly_test':False}
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'README.md').write_text(f'''# {a['spec']['name']} · 연결형 키링 단독 판

![제작 시안](preview.png)

**55×75mm 판에 1개. 위·아래 연결 구멍 각각 지름4mm.**
그림30×{a['h']:.2f}mm, 고리 포함 아크릴 약{x1-x0:.2f}×{y1-y0:.2f}mm입니다.
일반 투명 여백2.5mm, 구멍-외곽2.5mm, 구멍-그림3mm 이상입니다.

| 파일 | 용도 |
|---|---|
| 01_PRINT_300ppi.png / PDF | UV 인쇄용. 그림과 파란 위치 기준선 |
| 02_MASTER.ai / vectorcraft | 그림·기준선·칼선·백색 잉크 4개 레이어 |
| 03_CUT_ONLY.pdf / SVG | 빨강0.001mm. 구멍2개 먼저, 외곽1개 나중에 절단 |
| 04_WHITE_INK_MASK_300ppi.png / PDF | 검정 부분을 백색 잉크로 지정하는 분판. 원본 투명도 유지 |

인쇄·재단 모두 실제 크기100%, 같은 원점, 자동 맞춤 해제. 파란 기준선은 절단하지 않습니다.
AI는 그림·기준선만 보이도록 열립니다. 칼선·백색 레이어는 숨겨져 있으며 파일 안에 들어 있습니다.
03_CUT_ONLY 파일을 사용하면 레이저 경로만 따로 가져올 수 있습니다.
3T와5T는 같은 평면 칼선을 사용합니다. 연결링의 안쪽 크기와 두께는 실제 아크릴 두께에 맞춰 선택합니다.
인쇄 방향과 백색 분판은 작업실의 전면·배면 인쇄 방식에 맞춰 설정합니다.

[4종 전체 시안·연결 예시](../README.md)
''',encoding='utf-8')
    return report

def previews(arts,geoms):
    # The connection example is a flat, same-scale diagram; metal rings are illustrative only.
    w,h=220,145;content=f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'
    for i,(a,g) in enumerate(zip(arts,geoms)):
        x=15+i*52;y=18
        content+=f'<g transform="translate({x} {y})">'+path(poly_path(g['poly']),'#e9f4f4','#7d9a9c',.2)+a['ink']
        for hole in g['holes']:content+=path(poly_path(hole),'#fffdf8','#7d9a9c',.18)
        content+='</g>'
    # Two linked pieces, rotated 90 degrees to fit a compact explanatory row.
    g=geoms[0];height=g['poly'].bounds[3]-g['poly'].bounds[1];pitch=height+4
    connection='<g transform="translate(24 112) rotate(-90)">'
    for i in range(2):
        a=arts[i];g=geoms[i];y=i*pitch
        connection+=f'<g transform="translate(0 {y})">'+path(poly_path(g['poly']),'#e9f4f4','#7d9a9c',.2)+a['ink']
        for hole in g['holes']:connection+=path(poly_path(hole),'#fffdf8','#7d9a9c',.18)
        connection+='</g>'
    mid=(geoms[0]['centers'][1][1]+geoms[1]['centers'][0][1]+pitch)/2
    connection+=f'<ellipse cx="15" cy="{mid}" rx="3" ry="6" fill="none" stroke="#8a9296" stroke-width="1"/>'
    connection+='</g>'
    content+=connection
    pv=write_svg(OUT/'overview.svg',w,h,content);render(pv,OUT/'overview.png',2)

def main():
    for p in [SRC,OUT,TMP,VC_TMP]:p.mkdir(parents=True,exist_ok=True)
    arts=[pixel_art(v) for v in CFG['variants']];geoms=[geometry(a) for a in arts]
    assert all(np.isclose(a['h'],arts[0]['h']) for a in arts)
    records=[build_plate(a,g) for a,g in zip(arts,geoms)];previews(arts,geoms)
    (SRC/'provenance.json').write_text(json.dumps({'document':DOC,'variants':[{'variant':a['spec'],**a['source']} for a in arts]},ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'validation_report.json').write_text(json.dumps({'separate_plates':4,'total_pieces':4,'variants':records},ensure_ascii=False,indent=2),encoding='utf-8')
    rows='\n'.join(f"| [{a['spec']['name']}]({a['spec']['id']}/README.md) | ![]({a['spec']['id']}/preview.png) | 55×75mm ·1개 |" for a in arts)
    (OUT/'README.md').write_text(f'''# 연결형 튀잉 4종 · 각각 별도 판

**기본·황올·탄·안튀잉을 각각 55×75mm 단독 판으로 만들었습니다. 각1개, 총4개입니다.**
단바·엑스트라 합본과 별개의 파일입니다.

| 도안·다운로드 | 시안 | 판 크기·수량 |
|---|---|---|
{rows}

[4종 전체 ZIP](../Tuiing_Linked_4_Separate_Plates.zip)

![같은 크기의 4종과 두 개 연결 예시](overview.png)

위 줄은 기본·황올·탄·안튀잉 순서입니다. 아래는 기본과황올을 연결한 평면 설명도입니다.
금속 연결링은 조립 예시이며 인쇄·재단 파일에는 들어 있지 않습니다.

그림 폭30mm, 높이{arts[0]['h']:.2f}mm. 고리 포함 아크릴은 약35×{records[0]['acrylic_mm'][1]:.2f}mm입니다.
네 원본의 픽셀 배치·색·투명도를 그대로 벡터로 옮겼으며 새로 그리지 않았습니다.
각 부품 위아래에4mm 구멍을 두어 순서를 바꿔 연결할 수 있습니다.
투명 외곽2.5mm, 구멍-외곽2.5mm, 구멍-그림3mm 이상입니다.
최하단도 다른 위치로 바꿀 수 있도록 두 구멍을 모두 유지했습니다.

3T·5T 모두 같은 평면 칼선입니다. 연결링은 실제 판 두께에 맞춰 선택하며 실물 조립은 시험 전입니다.
네 개를 한 줄로 연결하면 길어지므로 먼저2개를 연결해 길이와 회전 여유를 확인하세요.
구멍을 먼저, 외곽을 나중에 절단합니다. 레이저 선은빨강0.001mm입니다.
파란 위치 기준선은 절단하지 않습니다. 인쇄·재단은 같은 원점에서100% 실제 크기입니다.

[참고 원본이 포함된 제작 문서]({DOC}) · [원본·벡터 소스](https://github.com/ark1st/dpbr_goods/tree/main/assets/linked_tuiing)
''',encoding='utf-8')
    zpath=OUT.parent/'Tuiing_Linked_4_Separate_Plates.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(OUT.parent))
    with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
    print(json.dumps({'plates':4,'canvas_mm':CFG['sheet_mm'],'art_mm':[arts[0]['w'],arts[0]['h']],
        'acrylic_mm':records[0]['acrylic_mm'],'cut_paths_per_plate':3,'zip_bytes':zpath.stat().st_size},ensure_ascii=False))

if __name__=='__main__':main()
