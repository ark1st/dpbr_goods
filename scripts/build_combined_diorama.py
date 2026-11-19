"""Same-scale assembly comparison and a five-piece Illustrator production sheet."""
from pathlib import Path
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tmp/pylibs'))
import numpy as np
from PIL import Image
from pypdf import PdfReader
from shapely import affinity
from shapely.geometry import box
from vector_utils import layer, path, poly_path
import build_diorama as mascot
import build_logo_diorama as logo
from build_diorama import write_svg, render, export_native, export_png, rounded, svg_text

OUT = ROOT/'output/combined_diorama_v1'
BOARD = (310,160)
SCENE = (350,145)
BLUE, RED = '#0000ff', '#ff0000'
POSES = {'garam':(12,12), 'danpaengi':(87,15), 'main_logo':(132,12),
         'mascot_base':(18,108), 'logo_base':(150,108)}


def load_geometry(assets, art, preset):
    shapes = {name:mascot.standee(assets[name],preset['base_thickness_mm'])
              for name in ['garam','danpaengi']}
    main = logo.geometry(art,preset)
    originals = [
        {'name':name,'poly':shapes[name]['poly'],'ink':assets[name]['inner'],'holes':[]}
        for name in ['garam','danpaengi']]
    originals += [
        {'name':'main_logo','poly':main['stand'],'ink':art['ink'],'holes':[]},
        {'name':'mascot_base','poly':rounded(0,0,*mascot.CFG['base_mm'],mascot.CFG['base_corner_radius_mm']),
         'ink':mascot.base_art(assets),'holes':mascot.base_slots(preset['slot_width_mm'])},
        {'name':'logo_base','poly':main['base'],'ink':'','holes':main['slots']}]
    return shapes,main,originals


def layout(originals):
    items=[]
    for original in originals:
        x0,y0,_,_=original['poly'].bounds
        x,y=POSES[original['name']];tx,ty=x-x0,y-y0
        items.append({**original,'tx':tx,'ty':ty,
                      'poly':affinity.translate(original['poly'],tx,ty),
                      'holes':[affinity.translate(h,tx,ty) for h in original['holes']]})
        # Combining only translates the original geometry, never scales it.
        restored=affinity.translate(items[-1]['poly'],-tx,-ty)
        assert restored.hausdorff_distance(original['poly']) < 1e-8
    for p in items:
        assert box(8,8,BOARD[0]-8,BOARD[1]-8).contains(p['poly'])
        assert all(p['poly'].contains(h) for h in p['holes'])
    gap=min(p['poly'].distance(q['poly']) for i,p in enumerate(items) for q in items[:i])
    assert gap>=8, gap
    return items,gap


def make_sheet(assets,art,preset):
    folder=OUT/preset['name'];(folder/'preview').mkdir(parents=True,exist_ok=True)
    shapes,main,originals=load_geometry(assets,art,preset)
    items,gap=layout(originals);w,h=BOARD
    ink=layer('3_ARTWORK',mascot.artwork_layer(items))
    reference=layer('2_CORNER_REFERENCE',
        f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="{BLUE}" stroke-width="0.3"/>')
    cutting=layer('1_LASER_CUT',mascot.cut_layer(items))
    master=write_svg(folder/'02_COMBINED_MASTER.svg',w,h,ink+reference+cutting,
                     'Garam + Danpaengi + main logo / 5 pieces / 1:1 mm')
    export_native(master,folder,'02_COMBINED_MASTER')
    printing=write_svg(folder/'01_PRINT.svg',w,h,ink+reference)
    export_png(printing,folder/'01_PRINT_300ppi.png')
    write_svg(folder/'03_CUT_ONLY.svg',w,h,cutting)
    labels=svg_text(12,99,f'{preset["name"]} / GARAM + DANPAENGI + MAIN LOGO',3.5)
    labels+=svg_text(w/2,154,'5 PIECES / 2 BASES / ACTUAL SIZE / 310 x 160 mm',3.1,anchor='middle')
    flat=write_svg(folder/'preview/flat_layout.svg',w,h,
        f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'+ink+reference+mascot.cut_layer(items,.17)+labels)
    render(flat,folder/'preview/flat_layout.png',2)
    # One shared coupon for the unchanged 18 mm tab interface.
    rows=mascot.fit_test(preset,folder)
    for name,subset in [('UPRIGHTS',[p for p in items if not p['holes']]),
                        ('BASES',[p for p in items if p['holes']])]:
        write_svg(folder/f'05_{name}_ONLY.svg',w,h,
            layer('3_ARTWORK',mascot.artwork_layer(subset))+reference+layer('1_LASER_CUT',mascot.cut_layer(subset)))
    assembly(assets,art,shapes,main,preset,folder,front=False)
    assembly(assets,art,shapes,main,preset,folder,front=True)
    validate(assets,art,preset,originals,items,gap,folder,rows)


def line(x1,y1,x2,y2,color='#bbc0b4',width=.2,dash=''):
    dashed=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="{width}"{dashed}/>'


def base_view(base,ink,ox,floor,thickness,dx,dy,front):
    bw=base.bounds[2];bh=base.bounds[3]
    if front:
        return f'<rect x="{ox}" y="{floor-thickness}" width="{bw}" height="{thickness}" rx="0.5" fill="#e0e9e4" stroke="#a1b7ae" stroke-width=".25"/>'
    result=f'<ellipse cx="{ox+(bw+dx*bh)/2}" cy="{floor+1.6}" rx="{(bw+dx*bh)/2+3}" ry="4.0" fill="#e6dfd3"/>'
    for z,fill in [(0,'#d6e1dc'),(thickness,'#f8fff9')]:
        matrix=f'matrix(1 0 {-dx} {-dy} {ox+dx*bh} {floor+dy*bh-z})'
        result+=f'<g transform="{matrix}">'+path(poly_path(base),fill,'#a4b8b0',.25)+(ink if z else '')+'</g>'
    return result


def assembly(assets,art,shapes,main,preset,folder,front):
    # Orthographic projection: x and vertical z use exactly one SVG unit per mm.
    # Depth changes translation only; no perspective or per-object scaling.
    w,h=SCENE;floor=110;left_x=22;right_x=170
    dx,dy=(0,0) if front else (.4,-.32)
    bt=preset['base_thickness_mm'];pt=preset['part_thickness_mm']
    parts=[f'<rect width="{w}" height="{h}" fill="#f8f5ee"/>']
    title='FRONT VIEW / COMMON GROUND LINE' if front else 'GARAM + DANPAENGI + MAIN LOGO'
    parts += [svg_text(12,10,title,4.3,'#80564b'),
              svg_text(12,17,f'{preset["name"]} / same scale for all parts / dimensions in mm',3)]
    if front:
        for height in range(0,81,10):
            yy=floor-height
            parts.append(line(12,yy,338,yy,'#dedfd4',.15,'1.2 1.2'))
            parts.append(svg_text(9,yy+1,str(height),2.6,'#929689','end'))
    else:parts.append(line(12,floor+7,338,floor+7,'#e5dfd4',.2))
    mb=rounded(0,0,*mascot.CFG['base_mm'],mascot.CFG['base_corner_radius_mm'])
    parts.append(base_view(mb,mascot.base_art(assets),left_x,floor,bt,dx,dy,front))
    parts.append(base_view(main['base'],'',right_x,floor,bt,dx,dy,front))
    actual=[]
    for name in ['garam','danpaengi']:
        a=assets[name];s=shapes[name];cx,depth=mascot.CFG['mount_centers_mm'][name]
        X=left_x+cx+dx*(mascot.CFG['base_mm'][1]-depth)-s['cx']
        Y=floor+dy*(mascot.CFG['base_mm'][1]-depth)-bt-s['shoulder']
        visible=s['poly'].intersection(box(-50,-50,200,s['shoulder']))
        actual.append((name,X,Y,visible,a['inner']))
    X=right_x+logo.CFG['base_mm'][0]/2+dx*logo.CFG['base_mm'][1]/2-art['w']/2
    Y=floor+dy*logo.CFG['base_mm'][1]/2-bt-main['shoulder']
    actual.append(('main_logo',X,Y,main['stand'].intersection(box(-20,-20,art['w']+20,main['shoulder'])),art['ink']))
    for name,X,Y,visible,ink in actual:
        body=path(poly_path(visible),'#fafffc','#a1b7ac',.25)
        if not front:parts.append(f'<g transform="translate({X+dx*pt} {Y+dy*pt})">{body}</g>')
        parts.append(f'<g id="assembled_{name}" data-scale="1" transform="translate({X} {Y})">{body}{ink}</g>')
    if front:parts.append(line(12,floor,338,floor,'#9caa9d',.25))
    for x,name,aw,ah in [(53,'GARAM',assets['garam']['w'],assets['garam']['h']),
                         (108,'DANPAENGI',assets['danpaengi']['w'],assets['danpaengi']['h']),
                         (246,'MAIN LOGO',art['w'],art['h'])]:
        parts.append(svg_text(x,125,name,3.3,'#5a5b50','middle'))
        parts.append(svg_text(x,131,f'{aw:.2f} x {ah:.2f} mm ART',2.8,anchor='middle'))
    parts.append(svg_text(22,141,'MASCOT BASE 100 x 36 mm',2.7))
    parts.append(svg_text(170,141,'LOGO BASE 140 x 38 mm',2.7))
    filename='front_comparison' if front else 'assembly_together'
    svg=write_svg(folder/f'preview/{filename}.svg',w,h,''.join(parts))
    render(svg,folder/f'preview/{filename}.png',2)
    # Requested combined illustration also remains editable in Illustrator.
    if not front:export_native(svg,folder/'preview','00_DISPLAY_COMPARISON')
    return actual


def validate(assets,art,preset,originals,items,gap,folder,rows):
    master=PdfReader(folder/'02_COMBINED_MASTER.ai')
    layers=[e.get_object()['/Name'] for e in master.trailer['/Root']['/OCProperties']['/OCGs']]
    assert layers==['3_ARTWORK','2_CORNER_REFERENCE','1_LASER_CUT']
    page=master.pages[0]
    assert abs(float(page.mediabox.width)*25.4/72-BOARD[0])<.01
    assert abs(float(page.mediabox.height)*25.4/72-BOARD[1])<.01
    source=(folder/'03_CUT_ONLY.svg').read_text(encoding='utf-8')
    assert source.count('<path ')==source.count(' Z"')==9 and BLUE not in source
    assert len(items)==5 and sum(len(p['holes']) for p in items)==4
    im=Image.open(folder/'01_PRINT_300ppi.png');pixels=np.asarray(im)
    assert im.mode=='RGBA' and im.size==tuple(round(v*300/25.4) for v in BOARD)
    assert abs(im.info['dpi'][0]-300)<.1
    for x,y in [(4,BOARD[1]/2),(BOARD[0]-4,BOARD[1]/2),(BOARD[0]/2,4),(BOARD[0]/2,BOARD[1]-4)]:
        xx,yy=round(x*300/25.4),round(y*300/25.4);a=pixels[yy-3:yy+4,xx-3:xx+4]
        assert ((a[:,:,2]>240)&(a[:,:,0]<10)&(a[:,:,1]<10)&(a[:,:,3]>150)).any()
    # Full tab and slot buffers are blank, not just their center points.
    import cv2
    blank=np.zeros(pixels.shape[:2],np.uint8)
    for p in items:
        if p['holes']:zones=[h.buffer(1.5) for h in p['holes']]
        else:
            shoulder=p['poly'].bounds[3]-(preset['base_thickness_mm']-.4)
            zones=[p['poly'].intersection(box(-10,shoulder+.05,BOARD[0]+10,BOARD[1]))]
            zones=[q for z in zones for q in (z.geoms if z.geom_type=='MultiPolygon' else [z])]
        for z in zones:
            coords=np.round(np.asarray(z.exterior.coords)*300/25.4).astype(np.int32)
            cv2.fillPoly(blank,[coords],1)
    assert not pixels[:,:,3][blank.astype(bool)].any()
    report={'design':'combined-diorama-v1','preset':preset,'quantity':1,'pieces':5,
        'uprights':['garam','danpaengi','main_logo'],'bases':['mascot_base','logo_base'],
        'canvas_mm':BOARD,'original_geometry_translation_only':True,
        'comparison_projection':'orthographic; x and vertical z have identical scale; depth translation only',
        'comparison_scale_for_all_parts':1,'front_view_common_ground_line_mm':110,
        'source_designs':['diorama_v2','logo_diorama_v2'],
        'art_dimensions_mm':{**{n:[assets[n]['w'],assets[n]['h']] for n in ['garam','danpaengi']},
                             'main_logo':[art['w'],art['h']]},
        'base_dimensions_mm':{'mascot_base':mascot.CFG['base_mm'],'logo_base':logo.CFG['base_mm']},
        'minimum_piece_gap_mm':gap,'cut_closed_paths':9,'slot_count':4,'ai_layers':layers,
        'blue_reference_four_sides':True,'rgba_300ppi':True,'tabs_and_slot_buffers_unprinted':True,
        'physical_fit_test':False,'fit_test_slots':rows}
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'parameters.json').write_text(json.dumps({'canvas_mm':BOARD,'positions_top_left_mm':POSES,
        'mascot_config':mascot.CFG,'logo_config':logo.CFG,'selected_preset':preset},ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    OUT.mkdir(parents=True,exist_ok=True);mascot.TMP.mkdir(parents=True,exist_ok=True)
    art=logo.load_logo();assets=mascot.load_art()
    assert mascot.CFG['presets']==logo.CFG['presets']
    for preset in logo.CFG['presets']:make_sheet(assets,art,preset)
    (OUT/'README.md').write_text('''# 가람·단팽이·메인 로고 합본

기존 마스코트 디오라마 V2와 큰 로고 V2를 **그대로, 같은 배율**로 모았습니다.
구성은 가람1 + 단팽이1 + 큰 로고1 + 기존 받침대2 = **총5조각**입니다.
한 개의 공통 받침대로 바꾸지 않았습니다. 마스코트는100×36mm, 로고는140×38mm 받침대에 꽂습니다.
3T와5T는 두께별 대안으로 한 종류만 선택합니다.

![같은 배율로 함께 세운 모습](3T/preview/assembly_together.png)
![동일 바닥선의 정면 크기 비교](3T/preview/front_comparison.png)

| 그림 | 폭×높이(mm) |
|---|---:|
| 가람 | 56.78×65.00 |
| 단팽이 | 28.30×24.65 |
| 제목 포함 큰 로고 | 160.00×56.33 |

비교 그림은 원근 축소가 없는 평행 투영이며 모든 부품의 가로·세로 축척이 같습니다.
정면도는 받침대 바닥선을 맞췄고, 점선 눈금은10mm입니다.
화면 표시 크기는 기기에 따라 달라지지만 세 그림 사이의 실제 제작 비율은 유지됩니다.
그림 치수는 인쇄 부분 기준이며 투명 여백·받침대 두께는 별도입니다.

## Illustrator 파일

- `3T/02_COMBINED_MASTER.ai` / `5T/02_COMBINED_MASTER.ai`: **제작용 합본**. 310×160mm 판에5조각 배치.
- `3T/preview/00_DISPLAY_COMPARISON.ai`: **조립 모습 편집용**. 설명 그림이므로 생산용으로 쓰지 않습니다.
- 각 AI의 `.vectorcraft`, `.svg` 원본도 포함합니다.
- `01_PRINT_300ppi.png`: 그림과 파란 기준선만 있는 투명 UV 인쇄 파일.
- `03_CUT_ONLY.svg`: 빨간0.001mm 재단선. 홈4개를 먼저 자르고 외곽5개를 자릅니다.
- `04_FIT_TEST_*`: 공통18mm 돌기의 홈 너비 시험판.
- `05_UPRIGHTS_ONLY.svg`, `05_BASES_ONLY.svg`: 부품 종류별 확인 파일. 두께가 다르면 별도 두께용 도안으로 생성해야 합니다.

인쇄·재단은 같은 원점과100% 크기를 유지합니다. 파란 사각 기준선은 재단하지 않습니다.
실물 끼움은 시험 전입니다. 기존과 같은18mm 돌기·홈 규격을 유지했으며 같은 재료와 설정으로 시험 후 제작합니다.
`python scripts/build_combined_diorama.py`로 재생성합니다.
''',encoding='utf-8')
    dest=OUT.parent/'Danpungbaram_Combined_Diorama_3T_5T.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(OUT.parent))
    print(json.dumps({'folder':str(OUT),'canvas_mm':BOARD,'pieces':5,'presets':['3T','5T']},ensure_ascii=False))


if __name__=='__main__':main()
