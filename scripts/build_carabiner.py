"""Dimensioned outline trials and a separate hardware calibration coupon."""
from pathlib import Path
import sys,json,re,math
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
from svgpathtools import parse_path
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union,nearest_points
from shapely import affinity
from vector_utils import layer,path,poly_path,runvc
from build_diorama import write_svg,render,export_native,export_png,rounded,svg_text,TMP,cut_layer

CFG=json.loads((ROOT/'configs/carabiner.json').read_text(encoding='utf-8'))
OUT=ROOT/'output/carabiner_trials_v1'

def source_parts(height):
    raw=json.loads((ROOT/'assets/artwork.json').read_text(encoding='utf-8'))['solo_logo']
    tags=re.findall(r'<(?:svg:)?path\b[^>]+/>',raw['inner'])
    assert len(tags)==7
    scale=.07617809422722394*2/3*(height/30)
    shapes=[];inks=[]
    for i,tag in enumerate(tags):
        d=re.search(r'\bd="([^"]+)"',tag)[1];p=parse_path(d)
        n=max(400,math.ceil(p.length()*scale/.03))
        pts=[p.point(j/n) for j in range(n)]
        poly=Polygon([((z.real-234.32016769325503)*scale,(z.imag-1239.354)*scale) for z in pts])
        dx,dy=CFG['left_arm_shift_mm'] if i in [5,6] else [0,0]
        shapes.append(affinity.translate(poly,dx,dy))
        native=tag.replace('svg:path','path')
        inks.append(f'<g transform="translate({dx} {dy}) scale({scale:.12f}) translate(-234.32016769325503 -1239.354)">{native}</g>')
    return shapes,''.join(inks)

def body(spec):
    parts,ink=source_parts(spec['height_mm']-2*spec['border_mm'])
    art=unary_union(parts);b=spec['border_mm']
    p,q=nearest_points(parts[6],parts[4])
    bridge=LineString([p,q]).buffer(3,quad_segs=64)
    r,s=nearest_points(parts[5],parts[6])
    dotbridge=LineString([r,s]).buffer(2.5,quad_segs=64)
    poly=unary_union([art.buffer(b,quad_segs=64),bridge,dotbridge])
    assert poly.geom_type=='Polygon' and poly.is_valid and not poly.interiors,(spec,poly.geom_type)
    assert poly.contains(art)
    clearance=poly.boundary.distance(art)
    assert b-.002<=clearance<=b+.002
    left=unary_union([parts[5],parts[6]]).buffer(b)
    right=unary_union(parts[:4]).buffer(b)
    mouth=left.distance(right)
    assert mouth>2.5,(spec,mouth)
    h=spec['height_mm']-2*b
    anchor=Point(20.5*h/45,34.2*h/45)
    toward=Point(3*h/45-5,21*h/45-1.5)
    dx,dy=toward.x-anchor.x,toward.y-anchor.y;length=math.hypot(dx,dy)
    tip=Point(anchor.x+dx/length*23.5,anchor.y+dy/length*23.5)
    return {'name':'carabiner_'+spec['id'],'spec':spec,'poly':poly,'holes':[],
        'ink':ink,'blank_zones':[],'gate':[[anchor.x,anchor.y],[tip.x,tip.y]],
        'metrics':{'art_to_cut_min_mm':clearance,'lower_opening_min_mm':mouth,
                   'outer_mm':[poly.bounds[2]-poly.bounds[0],poly.bounds[3]-poly.bounds[1]],
                   'mount_holes_finalized':False}}

def coupon():
    poly=rounded(0,0,52,46,2);holes=[];labels=[];rows=[]
    for j,pitch in enumerate(CFG['coupon_hole_pitches_mm']):
        for i,dia in enumerate(CFG['coupon_hole_diameters_mm']):
            x=8+i*18;y=8+j*14
            for cy in [y-pitch/2,y+pitch/2]:holes.append(Point(x,cy).buffer(dia/2,quad_segs=48))
            labels.append(svg_text(x,y+5.7,f'{dia:.1f}/{pitch:.0f}',2.2,anchor='middle'))
            rows.append({'diameter_mm':dia,'pitch_mm':pitch,'centers_mm':[[x,y-pitch/2],[x,y+pitch/2]]})
    assert all(poly.contains(h) and poly.boundary.distance(h)>3 for h in holes)
    return {'name':'gate_fit_coupon','poly':poly,'holes':holes,'ink':''.join(labels),'blank_zones':[],
            'rows':rows}

def samples():return [body(s) for s in CFG['samples']]+[coupon()]

def placed_samples(y=7):
    result=[];x=8
    for p in samples():
        x0,y0,x1,y1=p['poly'].bounds;tx=x-x0;ty=y-y0
        result.append({**p,'poly':affinity.translate(p['poly'],tx,ty),
            'holes':[affinity.translate(h,tx,ty) for h in p['holes']],
            'matrix':f'translate({tx:.9f} {ty:.9f})','tx':tx,'ty':ty,'angle':0})
        x+=x1-x0+7
    return result

def sheet():
    OUT.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
    items=placed_samples();w=math.ceil(max(p['poly'].bounds[2] for p in items)+8);h=72
    artwork=''.join(f'<g transform="{p["matrix"]}">{p["ink"]}</g>' for p in items)
    ref=f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="#0000ff" stroke-width=".3"/>'
    cuts=cut_layer(items)
    master=write_svg(OUT/'02_MASTER.svg',w,h,layer('3_ARTWORK',artwork)+layer('2_CORNER_REFERENCE',ref)+layer('1_LASER_CUT',cuts))
    export_native(master,OUT)
    printing=write_svg(OUT/'01_PRINT.svg',w,h,artwork+ref);export_png(printing,OUT/'01_PRINT_300ppi.png')
    cut=write_svg(OUT/'03_CUT_ONLY.svg',w,h,layer('1_LASER_CUT',cuts))
    runvc(['convert',cut,OUT/'03_CUT_ONLY.pdf'])
    preview=f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'
    for p in items:
        preview+=path(poly_path(p['poly']),'#edf6f6','#81a1a2',.2)
        preview+=f'<g transform="{p["matrix"]}">{p["ink"]}</g>'
        for hole in p['holes']:preview+=path(poly_path(hole),'#fffdf8','#bb5555',.15)
        if 'gate' in p:
            a,b=p['gate'];a=[a[0]+p['tx'],a[1]+p['ty']];b=[b[0]+p['tx'],b[1]+p['ty']]
            preview+=f'<path d="M{a[0]} {a[1]} L{b[0]} {b[1]}" stroke="#66727a" stroke-width=".65" fill="none"/>'
            spec=p['spec'];label=f'{spec["id"]}: H{spec["height_mm"]} / rim {spec["border_mm"]}'
        else:label='hole / pitch (mm)'
        preview+=svg_text((p['poly'].bounds[0]+p['poly'].bounds[2])/2,65,label,2.7,anchor='middle')
    flat=write_svg(OUT/'preview.svg',w,h,preview);render(flat,OUT/'preview.png',2)
    report={'canvas_mm':[w,h],'pieces':5,'cut_paths':23,'hardware':CFG,'samples':{p['name']:p['metrics'] for p in items if 'metrics' in p},'coupon':coupon()['rows']}
    (OUT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text(README,encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

README="""# 단풍바람 카라비너 샘플 4종 + 구멍 시험편

![실척 비율 시안](preview.png)

| 샘플 | 몸체 높이 | 일반 투명 여백 |
|---|---:|---:|
| A | 50mm | 2.0mm |
| B | 50mm | 2.5mm |
| C | 55mm | 2.0mm |
| D | 55mm | 2.5mm |

구매한 금속 부품은 **9×23.5×1mm**. 회색 막대는 길이 참고용이며 인쇄·재단 파일에는 없습니다.
왼쪽 아래가 열리는 형태입니다. 5cm 원본 배치에서는 여백2.5mm를 두르면 개방부가 닫히므로,
카라비너용으로만 왼쪽 노란 팔과 주황 점을 왼쪽5mm·위1.5mm 이동했습니다.
원본7개 경로·색상과 각 경로 자체의 비율은 유지합니다. 위쪽 투명 연결부로 하나의 조각이 됩니다.
일반 외곽 여백은 표의 값이며 연결부는 더 넓습니다. 다른 키링과 로고 원본 배치에는 이 변형을 적용하지 않습니다.

**시험용입니다. 금속 부품 장착과 개폐는 실물 검증 전입니다.**
문서에는 부품의 바깥 치수만 있어 두 다리의 구멍 간격·꺾임 깊이를 확정할 수 없습니다.
따라서 본체 장착 부분은 미타공입니다. 시험편으로 지름1.2/1.4/1.6mm와 중심간격3/4/5mm를 비교한 뒤,
본체에 실제 부품을 대고 위치를 표시해 타공합니다. 맞는 조합이 없으면 실측값으로 config를 수정합니다.
시험편의 '1.4/4' 표기는 구멍 지름1.4mm / 중심간격4mm입니다. 커프 보정 전입니다.
23.5mm는 부품 전체 높이이며 유효 회전 길이와 같다고 가정하지 않습니다.
3T·5T 판에 같은 평면 경로를 사용할 수 있지만 부품의 폭·다리 깊이·스프링 예압은 두께마다 확인해야 합니다.
장식용으로만 사용합니다.

- 02_MASTER.ai: 편집용. 빨간 칼선0.001mm.
- 01_PRINT_300ppi.png: 투명 인쇄 파일. 파란 기준 사각형 포함.
- 03_CUT_ONLY.pdf / SVG: 23폐곡선, 5외곽 + 시험편 구멍18개.
- 단바 합본에도 **동일한 샘플5조각**이 들어갑니다. 별도 시트와 중복 제작하지 마세요.

문서의 레진·실리콘 몰드는 다음 제작 방식 검토 항목입니다.
이번 파일은 평판 아크릴 형상·장착 시험용이며 레진 금형 도면이 아닙니다.
"""

if __name__=='__main__':sheet()
