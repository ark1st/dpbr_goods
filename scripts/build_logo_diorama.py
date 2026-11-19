"""One larger main-logo stand + compact base; 3T/5T are alternatives."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pylibs'))
import numpy as np
import pymupdf as fitz
from PIL import Image
from pypdf import PdfReader
from shapely.geometry import MultiPoint, Polygon, box, LineString
from shapely import affinity
from shapely.ops import unary_union
from svgpathtools import parse_path
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from vector_utils import SVG, path, poly_path, layer, runvc
from guide_fonts import GUIDE_FONT, GUIDE_BOLD, register_guide_fonts
# Reuse the existing 18 mm fit coupon and VectorCraft export helpers.
import build_diorama as acrylic
from build_diorama import rounded, write_svg, render, export_native, export_png, svg_text

CFG = json.loads((ROOT / 'configs/logo_diorama.json').read_text(encoding='utf-8'))
OUT = ROOT / 'output/logo_diorama_v3'
TMP = ROOT / 'tmp/logo_diorama'
RED, BLUE = '#ff0000', '#0000ff'


def load_logo():
    root = ET.parse(ROOT / 'assets/logo_full.svg').getroot()
    x, y, w, h = map(float, root.get('viewBox').split())
    provenance = json.loads((ROOT / 'assets/logo_full_provenance.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT / provenance['source']).read_bytes()).hexdigest() == provenance['source_sha256']
    # Text-mode reading normalizes Git's Windows/macOS line-ending differences.
    assert hashlib.sha256((ROOT / 'assets/logo_full.svg').read_text(encoding='utf-8').encode('utf-8')).hexdigest() == provenance['extracted_svg_sha256_lf']
    groups = [e for e in root if e.tag == f'{{{SVG}}}g']
    paths = [p for g in groups for p in g.iter() if p.tag == f'{{{SVG}}}path']
    assert len(paths) == provenance['path_count'] == 38
    assert not any(e.tag == f'{{{SVG}}}text' for e in root.iter())
    scale = CFG['art_width_mm']/w
    points = []
    for p in paths:
        for segment in parse_path(p.get('d')):
            for t in np.linspace(0, 1, max(4, int(segment.length()/2)+1)):
                z = segment.point(float(t))
                points.append(((z.real-x)*scale, (z.imag-y)*scale))
    ET.register_namespace('', SVG)
    content = ''.join(ET.tostring(g, encoding='unicode') for g in groups)
    inner = f'<g transform="scale({scale:.12f}) translate({-x:.12f} {-y:.12f})">{content}</g>'
    return {'w': CFG['art_width_mm'], 'h': h*scale, 'ink': inner,
            'hull': MultiPoint(points).convex_hull, 'provenance': provenance}


def tab(cx, shoulder, depth):
    half = CFG['tab_width_mm']/2
    return Polygon([(cx-half, shoulder-1), (cx+half, shoulder-1),
                    (cx+half, shoulder+depth-.4), (cx+half-.4, shoulder+depth),
                    (cx-half+.4, shoulder+depth), (cx-half, shoulder+depth-.4)])


def geometry(art, preset):
    shoulder = art['h']+CFG['clear_border_mm']
    depth = preset['base_thickness_mm']-CFG['tab_bottom_clearance_mm']
    centers = [art['w']/2-CFG['tab_center_spacing_mm']/2,
               art['w']/2+CFG['tab_center_spacing_mm']/2]
    body = art['hull'].buffer(CFG['clear_border_mm'], quad_segs=64)
    plinth = box(centers[0]-13, shoulder-9, centers[1]+13, shoulder)
    body = unary_union([body, plinth]).convex_hull.intersection(box(-20, -20, art['w']+20, shoulder))
    stand = unary_union([body]+[tab(x, shoulder, depth) for x in centers])
    base = rounded(0, 0, *CFG['base_mm'], CFG['base_corner_radius_mm'])
    bw, bh = CFG['base_mm']
    slots = [rounded(bw/2+(x-art['w']/2)-CFG['slot_length_mm']/2,
                     bh/2-preset['slot_width_mm']/2,
                     CFG['slot_length_mm'], preset['slot_width_mm'], CFG['slot_corner_radius_mm'])
             for x in centers]
    assert stand.is_valid and stand.geom_type == 'Polygon' and not stand.interiors
    assert stand.contains(art['hull'])
    assert CFG['clear_border_mm']-.002 <= stand.boundary.distance(art['hull']) <= CFG['clear_border_mm']+.001
    assert all(base.contains(s) and base.boundary.distance(s) > 8 for s in slots)
    for x in centers:
        section = stand.intersection(LineString([(x-10, shoulder+.1), (x+10, shoulder+.1)]))
        assert abs(section.length-CFG['tab_width_mm']) < 1e-6
    return {'stand': stand, 'base': base, 'slots': slots, 'shoulder': shoulder,
            'depth': depth, 'centers': centers, 'above_base_mm': shoulder-stand.bounds[1]}


def position(geo):
    x0, y0, x1, _ = geo['stand'].bounds
    tx, ty = (CFG['canvas_mm'][0]-(x1-x0))/2-x0, 11-y0
    stand = affinity.translate(geo['stand'], tx, ty)
    bx, by = (CFG['canvas_mm'][0]-CFG['base_mm'][0])/2, CFG['layout_base_y_mm']
    base = affinity.translate(geo['base'], bx, by)
    slots = [affinity.translate(s, bx, by) for s in geo['slots']]
    gap = stand.distance(base)
    assert gap >= 8
    safe = box(8, 8, CFG['canvas_mm'][0]-8, CFG['canvas_mm'][1]-8)
    assert safe.contains(stand) and safe.contains(base)
    return tx, ty, stand, base, slots, gap


def cuts(polygons, stroke=.001):
    return ''.join(path(poly_path(p), 'none', RED, stroke) for p in polygons)


def build(preset, art):
    folder = OUT/preset['name']
    (folder/'preview').mkdir(parents=True, exist_ok=True)
    geo = geometry(art, preset)
    tx, ty, stand, base, slots, gap = position(geo)
    ink = layer('3_ARTWORK', f'<g transform="translate({tx:.9f} {ty:.9f})">{art["ink"]}</g>')
    w, h = CFG['canvas_mm']
    reference = layer('2_CORNER_REFERENCE',
        f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="{BLUE}" stroke-width="0.3"/>')
    cut = layer('1_LASER_CUT', cuts(slots+[stand, base]))
    master = write_svg(folder/'02_MASTER.svg', w, h, ink+reference+cut)
    guide_svg = write_svg(TMP/f'guide-board-{preset["name"]}.svg', w, h,
                          ink+reference+cuts(slots+[stand,base],.15))
    runvc(['convert',guide_svg,TMP/f'guide-board-{preset["name"]}.pdf'])
    printing = write_svg(folder/'01_PRINT.svg', w, h, ink+reference)
    write_svg(folder/'03_CUT_ONLY.svg', w, h, cut)
    export_native(master, folder)
    export_png(printing, folder/'01_PRINT_300ppi.png')
    write_svg(folder/'05_UPRIGHT_ONLY.svg', w, h, ink+reference+layer('1_LASER_CUT', cuts([stand])))
    write_svg(folder/'05_BASE_ONLY.svg', w, h, layer('1_LASER_CUT', cuts(slots+[base])))
    bw,bh = CFG['base_mm']
    labels = svg_text(w/2,CFG['layout_base_y_mm']-4,f'{preset["name"]} / 1 SET = 2 PIECES',3.2,anchor='middle')
    labels += svg_text(w/2,h-5,f'{bw} x {bh} mm BASE / TWO 18 mm TABS',2.8,anchor='middle')
    flat = write_svg(folder/'preview/flat_layout.svg', w, h,
        f'<rect width="{w}" height="{h}" fill="#fffdf8"/>'+ink+reference+cuts(slots+[stand,base],.16)+labels)
    render(flat, folder/'preview/flat_layout.png', 2.7)
    assembly(art, geo, preset, folder)
    # Shared test coupon exactly matches this design's tab/slot interface.
    for key in ['tab_width_mm','slot_length_mm','slot_corner_radius_mm','tab_bottom_clearance_mm']:
        assert CFG[key] == acrylic.CFG[key]
    rows = acrylic.fit_test(preset, folder)
    im = Image.open(folder/'01_PRINT_300ppi.png')
    assert im.mode == 'RGBA' and im.size == tuple(round(v*300/25.4) for v in CFG['canvas_mm'])
    assert abs(im.info['dpi'][0]-300) < .1
    pixels = np.asarray(im)
    for x,y in [(4,h/2),(w-4,h/2),(w/2,4),(w/2,h-4)]:
        xx, yy = round(x*300/25.4), round(y*300/25.4)
        sample = pixels[yy-3:yy+4,xx-3:xx+4]
        assert ((sample[:,:,2]>240)&(sample[:,:,0]<10)&(sample[:,:,1]<10)&(sample[:,:,3]>150)).any()
    for cx in geo['centers']:
        xx,yy = round((tx+cx)*300/25.4), round((ty+geo['shoulder']+geo['depth']/2)*300/25.4)
        assert pixels[yy,xx,3] == 0
    for slot in slots:
        x,y=slot.centroid.coords[0]
        assert pixels[round(y*300/25.4), round(x*300/25.4),3] == 0
    ai = PdfReader(folder/'02_MASTER.ai')
    names = [p.get_object()['/Name'] for p in ai.trailer['/Root']['/OCProperties']['/OCGs']]
    assert names == ['3_ARTWORK','2_CORNER_REFERENCE','1_LASER_CUT']
    assert abs(float(ai.pages[0].mediabox.width)*25.4/72-w) < .01
    assert abs(float(ai.pages[0].mediabox.height)*25.4/72-h) < .01
    cut_text = (folder/'03_CUT_ONLY.svg').read_text(encoding='utf-8')
    assert cut_text.count('<path ') == cut_text.count(' Z"') == 4
    assert BLUE not in cut_text
    report = {'design':'full-logo-diorama-v3-main', 'quantity':1, 'pieces':2, 'preset':preset,
        'canvas_mm':CFG['canvas_mm'], 'base_mm':CFG['base_mm'], 'nominal_art_border_mm':CFG['clear_border_mm'],
        'art_mm':[art['w'],art['h']], 'source_aspect_ratio':art['provenance']['aspect_ratio'],
        'art_aspect_ratio':art['w']/art['h'], 'original_paths_unchanged':38,
        'stand_width_mm':stand.bounds[2]-stand.bounds[0],
        'stand_height_above_base_mm':geo['above_base_mm'],
        'assembled_height_mm':geo['above_base_mm']+preset['base_thickness_mm'],
        'minimum_art_to_cut_mm':geo['stand'].boundary.distance(art['hull']),
        'minimum_piece_gap_mm':gap, 'tab_count':2, 'tab_width_mm':CFG['tab_width_mm'],
        'tab_depth_mm':geo['depth'], 'tab_center_spacing_mm':CFG['tab_center_spacing_mm'],
        'slot_length_mm':CFG['slot_length_mm'], 'slot_width_mm':preset['slot_width_mm'],
        'slot_minimum_edge_margin_mm':min(geo['base'].boundary.distance(s) for s in geo['slots']),
        'cut_closed_paths':4,'slots_cut_before_outer_profiles':True,
        'ai_layers':names, 'rgba_print_300ppi':True, 'blue_reference_four_sides':True,
        'unprinted_tabs_and_base':True, 'physical_fit_test':False,
        'fit_status':'UNTESTED: path dimensions without kerf compensation; test same material and settings first.',
        'fit_test_slots':rows}
    assert abs(report['source_aspect_ratio']-report['art_aspect_ratio']) < 1e-9
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'parameters.json').write_text(json.dumps({**CFG,'selected_preset':preset},ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def assembly(art, geo, preset, folder):
    # Actual cut outlines in an orthographic illustration. No generated logo art.
    bw,bh=CFG['base_mm'];bt=preset['base_thickness_mm'];pt=preset['part_thickness_mm']
    sw,sh=art['w']+50,art['h']+76
    dx,dy=.38,-.37
    ox,oy=(sw-bw-dx*bh)/2,sh-26
    floor = f'matrix(1 0 {-dx} {-dy} {ox+dx*bh} {oy+dy*bh})'
    top = f'matrix(1 0 {-dx} {-dy} {ox+dx*bh} {oy+dy*bh-bt})'
    parts=[f'<rect width="{sw}" height="{sh}" fill="#f7f3eb"/>',
           f'<ellipse cx="{sw/2}" cy="{oy+1.5}" rx="{(bw+dx*bh)/2+5}" ry="5.5" fill="#e6ded0"/>',
           f'<g transform="{floor}">'+path(poly_path(geo['base']),'#d8e2df','#a4b5b1',.25)+'</g>',
           f'<g transform="{top}">'+path(poly_path(geo['base']),'#f9fffc','#a3b7b0',.25)+'</g>']
    X=ox+bw/2+dx*bh/2-art['w']/2
    Y=oy+dy*bh/2-bt-geo['shoulder']
    # Hide the inserted portion behind the base; the source SVG stays unchanged.
    visible=geo['stand'].intersection(box(-20,-20,art['w']+20,geo['shoulder']))
    body=path(poly_path(visible),'#fafffd','#a5bab2',.28)
    parts.append(f'<g transform="translate({X+dx*pt} {Y+dy*pt})">{body}</g>')
    parts.append(f'<g transform="translate({X} {Y})">{body}{art["ink"]}</g>')
    parts.append(svg_text(10,12,'DANPUNGBARAM',4,'#8d594b'))
    parts.append(svg_text(10,19,f'MAIN DISPLAY / {art["w"]:g} mm original logo',2.8))
    parts.append(svg_text(10,sh-10,f'{bw} x {bh} mm BASE / ONE DIORAMA',3.1))
    parts.append(svg_text(10,sh-4,f'{preset["name"]} / assembly illustration',2.6))
    svg=write_svg(folder/'preview/assembly.svg',sw,sh,''.join(parts))
    render(svg,folder/'preview/assembly.png',3)


def guide(reports):
    register_guide_fonts()
    draft=TMP/'guide_draft.pdf'
    c=canvas.Canvas(str(draft),pagesize=(210*mm,297*mm))
    c.setTitle('단풍바람 메인 로고 디오라마 V3 - 1세트 제작 안내')
    def text(x,y,s,size=10,bold=False,color='#3f413a'):
        c.setFillColor(color);c.setFont(GUIDE_BOLD if bold else GUIDE_FONT,size);c.drawString(x*mm,y*mm,s)
    def page(title,sub,n):
        c.setFillColor('#faf8f2');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        text(17,278,'DANPUNGBARAM / FULL LOGO DIORAMA',9,True,'#b6634e')
        text(17,261,title,21,True);text(17,249,sub,9)
        c.setStrokeColor('#d8d4c7');c.line(17*mm,241*mm,193*mm,241*mm)
        text(17,11,'2026.11.20 / 실물 끼움 시험 전 도안 / 제작 수량 1세트',8,color='#76776b')
        text(190,11,str(n),8)
    first=reports[0];folder=OUT/first['preset']['name']
    bw,bh=CFG['base_mm'];cw,ch=CFG['canvas_mm']
    aw,ah=first['art_mm']
    pw,ph=first['stand_width_mm'],first['stand_height_above_base_mm']
    page('메인으로 세우는 단풍바람','원본 심벌 + 제목 그대로, 기존96 mm에서160 mm로 약1.67배 확대.',1)
    preview=Image.open(folder/'preview/assembly.png')
    display_h=176*preview.height/preview.width
    c.drawImage(str(folder/'preview/assembly.png'),17*mm,(99+(132-display_h)/2)*mm,width=176*mm,height=display_h*mm,mask='auto')
    for y,s in [(88,'구성: 제목 포함 로고판 1개 + 투명 받침대 1개 = 2조각'),
                (77,f'받침대: {bw} × {bh} mm / 로고 그림: {aw:g} × {ah:.2f} mm'),
                (66,f'로고판 외곽: 약 {pw:.1f} × {ph:.1f} mm (끼움 돌기 제외)'),
                (55,'원본 AI의 38개 벡터 경로·색상·글자 간격·비율을 그대로 유지'),
                (39,'3T와 5T는 같은 디자인의 두께별 대안입니다. 한 종류만 선택하세요.')]:
        text(17,y,s,10,bold=y==88)
    c.showPage()
    page('두께를 정하고, 시험 후 끼우기','홈 너비는 로고판 두께, 돌기 길이는 받침대 두께를 기준으로 합니다.',2)
    text(17,226,f'공통 돌기 18 mm × 2개 / 중심 간격 {CFG["tab_center_spacing_mm"]} mm / 홈 길이 18.8 mm',11,True)
    edge=min(r['slot_minimum_edge_margin_mm'] for r in reports)
    text(17,214,f'일반 외곽 여백2.5 mm, 홈과 받침대 가장자리는 최소 {edge:.1f} mm 여유.',9)
    y=199
    for r in reports:
        p=r['preset']
        text(17,y,f'{p["name"]}: 홈 {r["slot_length_mm"]:.1f} × {p["slot_width_mm"]:.2f} mm / 돌기 길이 {r["tab_depth_mm"]:.2f} mm',11,True)
        y-=12
    text(17,y-5,'위 값은 커프 보정 전 절단경로 치수입니다. 실물 결합은 아직 시험하지 않았습니다.',9)
    c.drawImage(str(folder/'preview/fit_test.png'),23*mm,83*mm,width=164*mm,height=164*78/160*mm,mask='auto')
    instructions=[
        '1. 실제 로고판·받침대 두께를 재고, 같은 판·같은 가공 설정으로 시험판을 자릅니다.',
        '2. 9개 홈 중 무리 없이 들어가고 흔들림이 적은 너비를 선택합니다.',
        '3. 선택한 홈 너비로 다시 생성한 뒤 최종 판을 출력·재단합니다.',
        '4. PRINT는 UV 인쇄용, CUT_ONLY는 재단용입니다. 같은 크기·원점을 유지합니다.',
        '5. 파란 사각선은 위치 맞춤 기준선입니다. 빨간 0.001 mm 선만 재단합니다.'
    ]
    for i,s in enumerate(instructions):text(17,70-i*10,s,9)
    c.showPage()
    for i,r in enumerate(reports):
        p=r['preset'];page(f'{p["name"]} 실제 크기 확인', 'A4에 100%로 출력하세요. 이 안내서 페이지 자체는 생산용 파일이 아닙니다.',3+i)
        text(17,225,f'아래 배치: {cw} × {ch} mm / 상단 로고판, 하단 받침대 / 총 2조각',10,True)
        text(17,64,f'홈 {r["slot_length_mm"]:.1f} × {p["slot_width_mm"]:.2f} mm / 돌기 길이 {r["tab_depth_mm"]:.2f} mm',10)
        text(17,52,'그림과 파란 기준선만 인쇄하고, 빨간 선을 커팅 레이어로 사용합니다.',9)
        c.setStrokeColor('#333333');c.setLineWidth(.5)
        c.line(17*mm,35*mm,67*mm,35*mm)
        c.line(17*mm,33*mm,17*mm,37*mm);c.line(67*mm,33*mm,67*mm,37*mm)
        text(17,26,'이 선이 50 mm인지 확인하세요.',9)
        c.showPage()
    c.save()
    doc=fitz.open(draft)
    for i,r in enumerate(reports):
        source=fitz.open(TMP/f'guide-board-{r["preset"]["name"]}.pdf')
        # Copy at 1:1, centered on A4, without rasterizing original logo paths.
        left=(210-cw)/2
        doc[2+i].show_pdf_page(fitz.Rect(left*mm,80*mm,(left+cw)*mm,(80+ch)*mm),source,0)
        source.close()
    doc.save(OUT/'00_ASSEMBLY_GUIDE.pdf',garbage=4,deflate=True)
    doc.close()


def readme(reports):
    text='''# 단풍바람 메인 로고 디오라마 V3

**한 디자인, 1세트 2조각**: 로고판 1개 + 투명 받침대 1개. 3T와 5T는 두께별 대안이며 둘 다 생산하지 않습니다.

![조립 예상도](3T/preview/assembly.png)

- 받침대 **140×38 mm**, 로고 그림 **160×56.33 mm**. 이전96 mm 로고의 가로·높이 약1.67배입니다.
- 원본 `assets/source_logo.ai`의 `기본` 그룹: 심벌 7개 + 제목 31개 벡터 경로를 그대로 사용했습니다.
- 글꼴을 새로 입력하지 않았으며 원본 색상·상대 위치·가로세로 비율을 보존했습니다.
- 로고판 외곽은 약165.0×61.3 mm, 투명 연결판으로 전체 로고가 한 조각이 됩니다.
- 일반 외곽 여백2.5mm 기준. 글자·심벌 사이 연결판과 돌기 주변은 구조상 더 넓습니다.
- 레이저 선 자체는0.001mm이고 원본 그림 크기는 유지했습니다.
- 18 mm 돌기 2개, 중심 간격84 mm. 받침대는 인쇄 없이 투명하게 사용합니다.

## 파일 선택

- `00_ASSEMBLY_GUIDE.pdf`: 조립 예상도, 끼움 시험, A4 실측 확인.
- `3T/` 또는 `5T/`: 실제 재료 두께에 맞는 한 폴더를 선택.
- `01_PRINT_300ppi.png`: 투명 배경 UV 인쇄, 파란 기준선 포함.
- `02_MASTER.ai`, `.vectorcraft`, `.svg`: 그림·기준선·커팅선 3개 레이어.
- `03_CUT_ONLY.svg`: 빨간0.001 mm, 홈2개와 외곽2개인 총4개 폐곡선. 홈을 먼저 가공.
- `04_FIT_TEST_*`: 9단계 홈 시험판과18 mm 시험 돌기. 최종 제품에 포함하지 않음.
- `05_UPRIGHT_ONLY.svg`, `05_BASE_ONLY.svg`: 로고판과 받침대의 두께가 다를 때 재료별 분리 파일.
- `preview/`: 설명용 미리보기. 인쇄·커팅용으로 사용하지 않음.

## 두께와 끼움 보정

홈 너비는 로고판의 **실제 두께**, 돌기 길이는 받침대 두께에서0.40 mm를 뺀 값입니다.
3T 기본: 홈18.8×3.00 mm / 돌기2.60 mm. 5T 기본: 홈18.8×5.00 mm / 돌기4.60 mm.
이는 커프 보정 전 경로 치수이며 **실물 끼움은 시험 전**입니다.
동봉 시험판을 같은 재료·같은 가공 설정으로 잘라 적합한 너비를 선택합니다.
두 돌기가 모두 수직으로 들어가는지도 최종 조립에서 확인합니다.

```powershell
python scripts/build_logo_diorama.py
# 2.80은 시험 결과 그 값을 선택했을 때의 예시일 뿐입니다.
python scripts/build_logo_diorama.py --part-thickness 3 --base-thickness 3 --slot-width 2.80 --name calibrated_3T
# 로고판3T / 받침대5T: 각 부품을 해당 재료에 따로 출력합니다.
python scripts/build_logo_diorama.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
```

작업영역200×140 mm, 기준선은(4,4)에서192×132 mm의 파란 사각선입니다.
파란 선은 위치·방향 맞춤용이며 커팅하지 않습니다. 모든 파일은 같은 원점, 실제 크기100%로 사용합니다.
UV 백색 잉크 처리는 장비 담당자가 그림의 불투명 부분 기준으로 설정합니다. 투명 여백과 돌기는 인쇄하지 않습니다.
원본 재추출은 `python scripts/extract_logo_full.py`로 할 수 있습니다.
이전 작은 버전은 `logo_diorama_v1`에 보관되어 있습니다. 메인 장식용 제작은 이 V3를 사용합니다.
'''
    if reports[0]['preset']['name']!='3T':
        text=text.replace('(3T/preview/assembly.png)',f'({reports[0]["preset"]["name"]}/preview/assembly.png)')
    (OUT/'README.md').write_text(text,encoding='utf-8')


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--part-thickness',type=float)
    parser.add_argument('--base-thickness',type=float)
    parser.add_argument('--slot-width',type=float)
    parser.add_argument('--name',default='custom')
    args=parser.parse_args()
    values=[args.part_thickness,args.base_thickness,args.slot_width]
    if any(v is not None for v in values):
        if not all(v is not None for v in values):parser.error('Supply all three thickness/slot arguments together')
        if not (2<=args.part_thickness<=6 and 2<=args.base_thickness<=6):parser.error('Thickness range: 2 to 6 mm')
        if not (args.part_thickness-.6<=args.slot_width<=args.part_thickness+.6):parser.error('Slot width must be within 0.6 mm of the part thickness')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',args.name):parser.error('Name may contain ASCII letters, numbers, underscore and hyphen')
        OUT=ROOT/'output'/f'logo_diorama_v3_{args.name}'
        presets=[{'name':args.name,'part_thickness_mm':args.part_thickness,
                  'base_thickness_mm':args.base_thickness,'slot_width_mm':args.slot_width}]
    else:presets=CFG['presets']
    TMP.mkdir(parents=True,exist_ok=True);acrylic.TMP.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    art=load_logo()
    reports=[build(p,art) for p in presets]
    guide(reports);readme(reports)
    (OUT/'validation_summary.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    zipname='Danpungbaram_Logo_Diorama_V3_MAIN_3T_5T.zip' if len(presets)==2 else f'Danpungbaram_Logo_Diorama_V3_{args.name}.zip'
    with zipfile.ZipFile(OUT.parent/zipname,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(OUT.rglob('*')):
            if file.is_file():archive.write(file,file.relative_to(OUT.parent))
    print(json.dumps({'folder':str(OUT),'sets':1,'pieces':2,'art_mm':[art['w'],art['h']],
                      'base_mm':CFG['base_mm'],'presets':[p['name'] for p in presets]},ensure_ascii=False))


if __name__ == '__main__':
    main()
