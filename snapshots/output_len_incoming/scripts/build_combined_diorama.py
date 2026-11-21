"""Same-scale assembly comparison and eleven-piece sheets with carabiner trials."""
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
from shapely.geometry import box, Point
from vector_utils import layer, path, poly_path
import build_diorama as mascot
import build_logo_diorama as logo
import build_goods_v3 as keyring
import build_carabiner as carabiner
from build_diorama import write_svg, render, export_native, export_png, rounded, svg_text

OUT = ROOT/'output/combined_diorama_v3'
PACKING = json.loads((ROOT/'configs/combined_layout.json').read_text(encoding='utf-8'))
BOARD = tuple(PACKING['board_mm'])
SCENE = (350,145)
BLUE, RED = '#0000ff', '#ff0000'
POSES = {p['name']:p for p in PACKING['placements']}


def logo_keyring():
    a=json.loads((ROOT/'assets/artwork.json').read_text(encoding='utf-8'))['solo_logo']
    folder=mascot.TMP/'combined_keyring';folder.mkdir(parents=True,exist_ok=True)
    svg=write_svg(folder/'solo_logo.svg',a['w'],a['h'],a['inner'])
    render(svg,folder/'solo_logo.png',8)
    original_folder=keyring.AS
    try:
        keyring.AS=folder
        shape=keyring.geometry({'solo_logo':a})['solo_logo']
    finally:keyring.AS=original_folder
    return {'name':'logo_keyring','poly':shape['poly'],'ink':a['inner'],
            'holes':[Point(*shape['hole']).buffer(2,quad_segs=64)],
            'keyring_metrics':{'art_mm':[a['w'],a['h']],'hole_diameter_mm':4,
                'art_to_cut_mm':shape['clearance'],'hole_to_art_mm':shape['hole_art'],
                'hole_to_edge_mm':shape['hole_edge']}}


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
    originals.append(logo_keyring())
    for p in originals:
        if p['holes']:p['blank_zones']=[h.buffer(1.5) for h in p['holes']]
        else:
            shoulder=p['poly'].bounds[3]-(preset['base_thickness_mm']-.4)
            region=p['poly'].intersection(box(-50,shoulder+.05,400,400))
            p['blank_zones']=list(region.geoms) if region.geom_type=='MultiPolygon' else [region]
    return shapes,main,originals


def layout(originals):
    items=[]
    for original in originals+carabiner.samples():
        pose=POSES[original['name']];tx,ty=pose['tx'],pose['ty'];angle=pose['angle']
        assert angle in [0,90,180,270]
        a,b,c,d={0:(1,0,0,1),90:(0,1,-1,0),180:(-1,0,0,-1),270:(0,-1,1,0)}[angle]
        transform=lambda p:affinity.affine_transform(p,[a,c,b,d,tx,ty])
        items.append({**original,'tx':tx,'ty':ty,'angle':angle,
                      'matrix':f'matrix({a} {b} {c} {d} {tx:.9f} {ty:.9f})',
                      'poly':transform(original['poly']),
                      'holes':[transform(h) for h in original['holes']],
                      'blank_zones':[transform(z) for z in original['blank_zones']]})
        # Quarter-turn rotation and translation only; dimensions and proportions stay exact.
        restored=affinity.rotate(affinity.translate(items[-1]['poly'],-tx,-ty),-angle,origin=(0,0))
        assert restored.hausdorff_distance(original['poly']) < 1e-8
    for p in items:
        assert box(8,8,BOARD[0]-8,BOARD[1]-8).contains(p['poly'])
        assert all(p['poly'].contains(h) for h in p['holes'])
    gap=min(p['poly'].distance(q['poly']) for i,p in enumerate(items) for q in items[:i])
    assert gap>=PACKING['minimum_gap_mm'], gap
    return items,gap


def artwork(items):
    return ''.join(f'<g id="{p["name"]}" transform="{p["matrix"]}">{p["ink"]}</g>' for p in items)


def make_sheet(assets,art,preset):
    folder=OUT/preset['name'];(folder/'preview').mkdir(parents=True,exist_ok=True)
    shapes,main,originals=load_geometry(assets,art,preset)
    items,gap=layout(originals);w,h=BOARD
    ink=layer('3_ARTWORK',artwork(items))
    reference=layer('2_CORNER_REFERENCE',
        f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="{BLUE}" stroke-width="0.3"/>')
    cutting=layer('1_LASER_CUT',mascot.cut_layer(items))
    master=write_svg(folder/'02_COMBINED_MASTER.svg',w,h,ink+reference+cutting,
                     'Compact: diorama + one logo keyring / 11 pieces / 1:1 mm')
    export_native(master,folder,'02_COMBINED_MASTER')
    printing=write_svg(folder/'01_PRINT.svg',w,h,ink+reference)
    export_png(printing,folder/'01_PRINT_300ppi.png')
    cut_svg=write_svg(folder/'03_CUT_ONLY.svg',w,h,cutting)
    from vector_utils import runvc
    runvc(['convert',cut_svg,folder/'03_CUT_ONLY.pdf'])
    labels=svg_text(w/2,h+7,f'{preset["name"]} / {w} x {h} mm / 11 PIECES / 4 CARABINERS + FIT COUPON',3.2,anchor='middle')
    flat=write_svg(folder/'preview/flat_layout.svg',w,h+12,
        f'<rect width="{w}" height="{h+12}" fill="#fffdf8"/>'+ink+reference+mascot.cut_layer(items,.17)+labels)
    render(flat,folder/'preview/flat_layout.png',2)
    # One shared coupon for the unchanged 18 mm tab interface.
    rows=mascot.fit_test(preset,folder)
    for name,subset in [('UPRIGHTS',[p for p in items if p['name'] in ['garam','danpaengi','main_logo']]),
                        ('BASES',[p for p in items if p['name'].endswith('_base')]),
                        ('KEYRING',[p for p in items if p['name']=='logo_keyring']),
                        ('CARABINERS',[p for p in items if p['name'].startswith('carabiner_') or p['name']=='gate_fit_coupon'])]:
        write_svg(folder/f'05_{name}_ONLY.svg',w,h,
            layer('3_ARTWORK',artwork(subset))+reference+layer('1_LASER_CUT',mascot.cut_layer(subset)))
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
    assert source.count('<path ')==source.count(' Z"')==42 and BLUE not in source
    assert len(items)==11 and sum(len(p['holes']) for p in items)==31
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
        for z in p['blank_zones']:
            coords=np.round(np.asarray(z.exterior.coords)*300/25.4).astype(np.int32)
            cv2.fillPoly(blank,[coords],1)
    assert not pixels[:,:,3][blank.astype(bool)].any()
    report={'design':'combined-diorama-v3-compact','preset':preset,'quantity':1,'pieces':11,
        'uprights':['garam','danpaengi','main_logo'],'bases':['mascot_base','logo_base'],
        'canvas_mm':BOARD,'nominal_art_border_mm':mascot.CFG['clear_border_mm'],'original_geometry_rigid_transform_only':True,
        'previous_canvas_mm':[310,205],'added_carabiner_trials':4,'added_gate_coupon':1,
        'area_reduction_percent':round(100*(1-BOARD[0]*BOARD[1]/(310*205)),2),
        'keyring_count':1,'keyring':next(p['keyring_metrics'] for p in items if p['name']=='logo_keyring'),
        'comparison_projection':'orthographic; x and vertical z have identical scale; depth translation only',
        'comparison_scale_for_all_parts':1,'front_view_common_ground_line_mm':110,
        'source_designs':['diorama_v3','logo_diorama_v3'],
        'art_dimensions_mm':{**{n:[assets[n]['w'],assets[n]['h']] for n in ['garam','danpaengi']},
                             'main_logo':[art['w'],art['h']]},
        'base_dimensions_mm':{'mascot_base':mascot.CFG['base_mm'],'logo_base':logo.CFG['base_mm']},
        'minimum_piece_gap_mm':gap,'cut_closed_paths':42,'slot_count':4,'keyring_hole_count':1,'gate_coupon_holes':18,
        'body_mount_holes':8,'carabiner_samples':{p['name']:p['metrics'] for p in items if p['name'].startswith('carabiner_')},'ai_layers':layers,
        'blue_reference_four_sides':True,'rgba_300ppi':True,'tabs_and_slot_buffers_unprinted':True,
        'physical_fit_test':False,'fit_test_slots':rows}
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'parameters.json').write_text(json.dumps({'canvas_mm':BOARD,'rigid_placements':POSES,
        'mascot_config':mascot.CFG,'logo_config':logo.CFG,'carabiner_config':carabiner.CFG,'selected_preset':preset},ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    OUT.mkdir(parents=True,exist_ok=True);mascot.TMP.mkdir(parents=True,exist_ok=True)
    art=logo.load_logo();assets=mascot.load_art()
    assert mascot.CFG['presets']==logo.CFG['presets']
    for preset in logo.CFG['presets']:make_sheet(assets,art,preset)
    (OUT/'README.md').write_text(f'''# 가람·단팽이·메인 로고 합본 V3 · 간격 3mm 압축 배치 + 카라비너 레이저 타공

**{BOARD[0]}×{BOARD[1]}mm, 총 11조각. 조각 사이 최소 간격 3mm.**
이전 310×205mm보다 대지 면적을 {100*(1-BOARD[0]*BOARD[1]/(310*205)):.1f}% 줄였습니다.
그림과 부품 크기는 그대로이며 회전·이동만으로 재배치했습니다.
기존6조각(가람·단팽이·큰 로고·받침2·로고 키링)에 카라비너4종과 구멍 시험편1개를 추가했습니다.
3T·5T는 두께별 대안으로 **실제 판 두께에 맞는 한 종류만** 사용합니다.

![전체 배치](3T/preview/flat_layout.png)
![실제 비율의 조립 시안](3T/preview/assembly_together.png)
![정면 크기 비교](3T/preview/front_comparison.png)

| 파일 | 용도 |
|---|---|
| 3T/02_COMBINED_MASTER.ai 또는 5T/02_COMBINED_MASTER.ai | Illustrator 편집용 합본 |
| 같은 폴더의 01_PRINT_300ppi.png | UV 인쇄용 투명 PNG |
| 03_CUT_ONLY.pdf / SVG | 빨간0.001mm, 42개 폐곡선 |
| 04_FIT_TEST_* | 디오라마18mm 돌기의 홈 너비 시험판 |
| 05_CARABINERS_ONLY.svg | 합본과 같은 좌표의 카라비너·구멍 시험편만 |
| preview/00_DISPLAY_COMPARISON.ai | 조립 시안 편집용, 제작용 아님 |

**구멍31개(받침 홈4+키링1+카라비너 본체8+시험편18)를 먼저 자르고 외곽11개를 나중에 자릅니다.**
파란 사각형은 위치 기준선입니다. 재단 대상이 아닙니다.
인쇄·재단 모두 원점과100% 크기를 유지하고 자동 맞춤은 끕니다.
작업영역은 안내문의800×500mm 이내입니다.

마스코트와 큰 로고의 그림 크기·원본 비율은 V2와 같습니다.
가람56.78×65mm / 단팽이28.30×24.65mm / 제목 포함 로고160×56.33mm.
받침은100×36mm와140×38mm입니다. 일반 투명 여백2.5mm, 키링 구멍 지름4mm,
구멍-외곽2.5mm, 구멍-그림3mm 기준으로 줄였습니다. 구조 연결부·받침 어깨는 더 넓습니다.

카라비너는 A=50mm/2mm, B=50mm/2.5mm, C=55mm/2mm, D=55mm/2.5mm입니다.
아래쪽 왼편 개방형이며 원본 로고의 왼팔·주황 점만 외측으로 이동한 시험용 변형입니다.
**각 본체에 장착 구멍 2개를 레이저 칼선으로 넣었습니다. 이전 미타공 도안을 대체합니다.**
A=지름1.2/간격4mm, B=1.4/4mm, C=1.6/4mm, D=1.4/5mm입니다.
구멍-외곽 여유는 최소2.5mm 이상입니다. 구멍 주변0.25mm는 인쇄하지 않습니다.
구매 부품9×23.5×1mm의 실제 다리 간격은 미확정이므로 네 조합은 조립 시험용 시작값입니다.
[카라비너 상세 시안과 시험 절차](../carabiner_trials_v1/README.md)의 수치는 미검증 시작값입니다.
독립 카라비너 시트와 이 합본의 샘플은 같습니다. 중복 출력하지 마세요.

실물 끼움·개폐 시험은 아직 하지 않았습니다.
동봉 시험판으로 실제 재료와 장비의 커프를 확인한 뒤 나머지를 가공합니다.
이전 V2는 보관용이며 이번 수정 파일은 V3입니다.
''',encoding='utf-8')
    dest=OUT.parent/'Danpungbaram_Combined_Diorama_V3_TRIALS_11pcs.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(OUT.parent))
    print(json.dumps({'folder':str(OUT),'canvas_mm':BOARD,'pieces':11,'presets':['3T','5T']},ensure_ascii=False))


if __name__=='__main__':main()
