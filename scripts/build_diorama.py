"""Parametric, interchangeable acrylic standees. Dimensions are cut-path mm.

Default: 3T and 5T alternatives, one base + Garam + Danpaengi per alternative.
The uncalibrated presets require the included fit test before final production.
"""
from pathlib import Path
import sys, json, argparse, zipfile, html, re

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon, box, LineString
from shapely import affinity, concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from vector_utils import runvc, svg_doc, path, poly_path, layer

OUT=ROOT/'output/diorama_v1'
TMP=ROOT/'tmp/diorama'
CFG=json.loads((ROOT/'configs/diorama.json').read_text(encoding='utf-8'))
BOARD=(220,150)
RED='#ff0000'
BLUE='#0000ff'


def write_svg(dest,w,h,content,title=''):
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(svg_doc(w,h,content,title),encoding='utf-8')
    return dest


def render(svg,png,scale=2):
    pdf=TMP/(svg.stem+'-'+str(round(scale*100))+'.pdf')
    runvc(['convert',svg,pdf])
    with fitz.open(pdf) as doc:
        doc[0].get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=True).save(str(png))


def rounded(x,y,w,h,r):
    return box(x+r,y+r,x+w-r,y+h-r).buffer(r,quad_segs=24)


def svg_text(x,y,text,size=3.2,color='#5e5a51',anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-family="Arial">{html.escape(text)}</text>'


def load_art():
    raw=json.loads((ROOT/'assets/artwork.json').read_text(encoding='utf-8'))
    assets={}
    for name,height in [('garam',CFG['garam_art_height_mm']),
                        ('danpaengi',CFG['garam_art_height_mm']*CFG['danpaengi_height_ratio'])]:
        a=raw[name];s=height/a['h']
        a={'w':a['w']*s,'h':height,'inner':f'<g transform="scale({s:.9f})">{a["inner"]}</g>'}
        p=write_svg(TMP/f'{name}_art.svg',a['w'],a['h'],a['inner'])
        render(p,TMP/f'{name}_art.png',8)
        im=Image.open(TMP/f'{name}_art.png').convert('RGBA')
        alpha=np.asarray(im)[:,:,3]
        contours,_=cv2.findContours((alpha>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        polygons=[Polygon(c[:,0,:]*[a['w']/im.width,a['h']/im.height]).buffer(0)
                  for c in contours if cv2.contourArea(c)>6]
        a['shape']=unary_union(polygons)
        assets[name]=a
    assets['logo']=raw['mini_logo']
    return assets


def tab_shape(cx,shoulder,depth):
    half=CFG['tab_width_mm']/2;chamfer=.4
    # Rounded slot corners are accommodated by the longer slot, not a force fit.
    return Polygon([(cx-half,shoulder-1),(cx+half,shoulder-1),
                    (cx+half,shoulder+depth-chamfer),
                    (cx+half-chamfer,shoulder+depth),
                    (cx-half+chamfer,shoulder+depth),
                    (cx-half,shoulder+depth-chamfer)])


def standee(a,base_thickness):
    border=CFG['clear_border_mm'];art=a['shape']
    body=art.buffer(border,quad_segs=28)
    if body.geom_type!='Polygon':body=concave_hull(body,ratio=.5)
    body=Polygon(body.exterior)
    cx=a['w']/2;shoulder=art.bounds[3]+border
    # A clear plinth bridges the feet and gives 4 mm shoulders beside the tab.
    half=CFG['tab_width_mm']/2+4
    bridge=box(cx-half,shoulder-8,cx+half,shoulder)
    body=unary_union([body,bridge]).intersection(box(-50,-50,200,shoulder))
    depth=base_thickness-CFG['tab_bottom_clearance_mm']
    shape=unary_union([body,tab_shape(cx,shoulder,depth)]).simplify(.015,preserve_topology=True)
    assert shape.geom_type=='Polygon' and shape.is_valid and not shape.interiors
    assert shape.contains(art)
    clearance=shape.boundary.distance(art)
    assert clearance>3.5,(clearance,a['h'])
    # Confirm the two contact shoulders and the standard-width stem exist.
    section=shape.intersection(LineString([(cx-30,shoulder+.15),(cx+30,shoulder+.15)]))
    assert abs(section.length-CFG['tab_width_mm'])<.001
    assert depth>1 and abs(shape.bounds[3]-shoulder-depth)<.001
    return {'poly':shape,'cx':cx,'shoulder':shoulder,'depth':depth,'clearance':clearance}


def base_slots(width):
    length=CFG['slot_length_mm'];r=CFG['slot_corner_radius_mm']
    return [rounded(x-length/2,y-width/2,length,width,r) for x,y in CFG['mount_centers_mm'].values()]


def base_art(assets):
    # Transparent stage with a quiet autumn motif; no ink on tabs or in slots.
    logo=assets['logo'];s=11/logo['h']
    lines=[f'<g transform="translate(53 49) scale({s})">{logo["inner"]}</g>']
    lines.append('<path d="M15 52 C27 47 35 58 46 53 M70 54 C83 58 96 51 105 53" fill="none" stroke="#ffd475" stroke-width="0.9" stroke-linecap="round"/>')
    for x,y,rot,color in [(19,48,-25,'#ff9b74'),(25,54,25,'#ffd475'),(103,50,25,'#ff9b74'),(104,55,-20,'#ffd475')]:
        lines.append(f'<path transform="translate({x} {y}) rotate({rot})" d="M-2 0 Q0 -4 2 0 Q0 3 -2 0 Z" fill="{color}"/>')
    return ''.join(lines)


def positioned(assets,shapes,preset):
    bw,bh=CFG['base_mm']
    base=rounded(0,0,bw,bh,CFG['base_corner_radius_mm'])
    # Three separate pieces in one 220 x 150 mm work area.
    poses={'garam':(15,13),'danpaengi':(88,34),'base':(85,78)}
    items=[]
    for name in ['garam','danpaengi']:
        s=shapes[name];bx,by,_,_=s['poly'].bounds
        x,y=poses[name];tx=x-bx;ty=y-by
        items.append({'name':name,'poly':affinity.translate(s['poly'],tx,ty),
                      'tx':tx,'ty':ty,'ink':assets[name]['inner'],'holes':[]})
    tx,ty=poses['base']
    slots=base_slots(preset['slot_width_mm'])
    items.append({'name':'base','poly':affinity.translate(base,tx,ty),'tx':tx,'ty':ty,
                  'ink':base_art(assets),'holes':[affinity.translate(s,tx,ty) for s in slots]})
    for p in items:assert box(8,8,BOARD[0]-8,BOARD[1]-6).contains(p['poly'])
    gap=min(p['poly'].distance(q['poly']) for i,p in enumerate(items) for q in items[:i])
    assert gap>=6,gap
    assert all(base.contains(s) and base.boundary.distance(s)>8 for s in slots)
    return items,gap


def artwork_layer(items):
    return ''.join(f'<g id="{p["name"]}" transform="translate({p["tx"]:.6f} {p["ty"]:.6f})">{p["ink"]}</g>' for p in items)


def cut_layer(items,stroke=.001):
    # Interior slots first, closed outside profiles second.
    holes=[h for p in items for h in p['holes']]
    return ''.join(path(poly_path(p),'none',RED,stroke) for p in holes+[p['poly'] for p in items])


def export_native(svg,folder,name='02_MASTER'):
    commands=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
        {'command':'document.save','params':{'path':str(folder/f'{name}.vectorcraft'),'format':'vectorcraft','compress':False}},
        {'command':'document.export','params':{'path':str(folder/f'{name}.ai'),'format':'ai','createLayers':True,'preserveEditing':True}}]
    command_file=TMP/f'{folder.name}-{name}.json';command_file.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',svg,'--commands',command_file])


def export_png(svg,dest):
    cmd=TMP/f'{dest.parent.name}-{dest.stem}.json'
    cmd.write_text(json.dumps([{'command':'document.export','params':{'path':str(dest),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}}]),encoding='utf-8')
    runvc(['run','--in',svg,'--commands',cmd])


def make_board(assets,shapes,preset,folder):
    items,gap=positioned(assets,shapes,preset);w,h=BOARD
    ink=layer('3_ARTWORK',artwork_layer(items))
    reference=layer('2_CORNER_REFERENCE',f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="none" stroke="{BLUE}" stroke-width="0.3"/>')
    cutting=layer('1_LASER_CUT',cut_layer(items))
    master=write_svg(folder/'02_MASTER.svg',w,h,ink+reference+cutting)
    printing=write_svg(folder/'01_PRINT.svg',w,h,ink+reference)
    write_svg(folder/'03_CUT_ONLY.svg',w,h,cutting)
    export_native(master,folder)
    export_png(printing,folder/'01_PRINT_300ppi.png')
    labels=svg_text(15,102,'GARAM / 65 mm',3.5)+svg_text(88,29,'DANPAENGI / 24.65 mm',3.5)
    labels+=svg_text(146,19,f'{preset["name"]} / 3 PIECES',4.3)
    labels+=svg_text(146,27,f'Slot: {CFG["slot_length_mm"]:.1f} x {preset["slot_width_mm"]:.2f} mm',3.3)
    labels+=svg_text(146,34,f'Tab depth: {shapes["garam"]["depth"]:.2f} mm',3.3)
    labels+=svg_text(146,42,'FIT TEST FIRST',3.1,'#b55f46')
    preview=write_svg(folder/'preview/flat_layout.svg',w,h,
        '<rect width="220" height="150" fill="#fffdf8"/>'+ink+reference+cut_layer(items,.17)+labels)
    render(preview,folder/'preview/flat_layout.png',2.2)
    return items,gap


def fit_test(preset,folder):
    # The matrix is separate from the three-piece production layout.
    pw=CFG['slot_length_mm'];t=preset['part_thickness_mm']
    bw,bh=112,67;testbase=rounded(5,5,bw,bh,3)
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
    # A mixed-thickness build must cut the coupon base and key from different sheets.
    write_svg(folder/'04_FIT_TEST_BASE_ONLY.svg',160,78,layer('1_LASER_CUT',''.join(path(poly_path(s),'none',RED,.001) for s in slots+[testbase])))
    write_svg(folder/'04_FIT_TEST_KEY_ONLY.svg',160,78,layer('1_LASER_CUT',path(poly_path(key),'none',RED,.001)))
    review=write_svg(folder/'preview/fit_test.svg',160,78,'<rect width="160" height="78" fill="#fffdf8"/>'+label+cut.replace('stroke-width="0.001"','stroke-width="0.18"'))
    render(review,folder/'preview/fit_test.png',2.2)
    return rows


def assembly(assets,shapes,preset,folder):
    # Orthographic axonometric drawing from the actual cut polygons; illustrative, not a cut file.
    # x moves right, depth moves up/right, z moves vertically upward.
    ox,oy=19,119;dx,dy=.44,-.34
    base=rounded(0,0,*CFG['base_mm'],CFG['base_corner_radius_mm'])
    bt=preset['base_thickness_mm'];pt=preset['part_thickness_mm']
    parts=['<rect width="198" height="150" fill="#f7f3eb"/>']
    parts.append('<ellipse cx="100" cy="123" rx="75" ry="10" fill="#e9e2d5"/>')
    # Base drawing y=0 is the rear edge; y=65 is the front edge.
    front=CFG['base_mm'][1]
    bt_transform=f'matrix(1 0 {-dx} {-dy} {ox+dx*front} {oy+dy*front})'
    parts.append(f'<g transform="{bt_transform}">'+path(poly_path(base),'#d4dedb','#99ada9',.35)+'</g>')
    top_transform=f'matrix(1 0 {-dx} {-dy} {ox+dx*front} {oy+dy*front-bt})'
    stage=path(poly_path(base),'#fafffc','#a4b6b1',.35)+base_art(assets)
    for s in base_slots(preset['slot_width_mm']):stage+=path(poly_path(s),'#bdcbc5','#8eaaa1',.25)
    parts.append(f'<g transform="{top_transform}">{stage}</g>')
    # Draw rear first. Increase visual thickness only by actual material thickness projection.
    for name in ['garam','danpaengi']:
        x,y=CFG['mount_centers_mm'][name];s=shapes[name];a=assets[name]
        X=ox+x+dx*(front-y)-s['cx'];Y=oy+dy*(front-y)-bt-s['shoulder']
        body=path(poly_path(s['poly']),'#fafffc','#a6b7b3',.35)
        parts.append(f'<g transform="translate({X+dx*pt} {Y+dy*pt})">{body}</g>')
        parts.append(f'<g transform="translate({X} {Y})">{body}{a["inner"]}</g>')
    parts.append(svg_text(13,15,'GAR AM + DANPAENGI'.replace('GAR AM','GARAM'),5,'#4d5148'))
    parts.append(svg_text(13,23,'120 x 65 mm / removable standees',3.4))
    parts.append(svg_text(13,141,f'{preset["name"]} concept / transparent acrylic edges shown',3.1))
    svg=write_svg(folder/'preview/assembly.svg',198,150,''.join(parts))
    render(svg,folder/'preview/assembly.png',2.7)


def templates(assets,shapes,preset,folder):
    # Reusable piece coordinate system: tab centered on x=0, shoulder on y=0.
    depth=preset['base_thickness_mm']-CFG['tab_bottom_clearance_mm']
    body=unary_union([rounded(5,5,50,55,5),box(17,53,43,60),tab_shape(30,60,depth)])
    guides='<rect x="9" y="9" width="42" height="43" fill="none" stroke="#9faca3" stroke-dasharray="1 1" stroke-width="0.2"/>'
    guides+=svg_text(30,25,'YOUR CHARACTER',3.3,anchor='middle')+svg_text(30,33,'Replace artwork',3.1,anchor='middle')
    guides+=svg_text(30,41,'Keep the 18 mm tab',3,anchor='middle')
    write_svg(folder/'05_CHARACTER_TEMPLATE.svg',60,70,layer('2_GUIDES_DELETE_BEFORE_PRINT',guides)+layer('1_LASER_CUT',path(poly_path(body),'none',RED,.001)))
    # Separate material boards for mixed base/upright thicknesses.
    items,_=positioned(assets,shapes,preset)
    for name,subset in [('BASE',[p for p in items if p['name']=='base']),('STANDEES',[p for p in items if p['name']!='base'])]:
        content=layer('3_ARTWORK',artwork_layer(subset))+layer('1_LASER_CUT',cut_layer(subset))
        write_svg(folder/f'06_{name}_ONLY.svg',*BOARD,content)


def validate(assets,shapes,preset,items,gap,folder,rows):
    im=Image.open(folder/'01_PRINT_300ppi.png')
    assert im.mode=='RGBA' and im.size==(2598,1772)
    assert abs(im.info['dpi'][0]-300)<.1
    arr=np.asarray(im);blue=(arr[:,:,2]>240)&(arr[:,:,0]<10)&(arr[:,:,1]<10)&(arr[:,:,3]>150)
    for x,y in [(110,4),(110,146),(4,75),(216,75)]:
        xx=round(x*300/25.4);yy=round(y*300/25.4)
        assert blue[yy-3:yy+4,xx-3:xx+4].any()
    reader=PdfReader(folder/'02_MASTER.ai');page=reader.pages[0]
    assert abs(float(page.mediabox.width)*25.4/72-BOARD[0])<.01
    assert abs(float(page.mediabox.height)*25.4/72-BOARD[1])<.01
    names=[r.get_object()['/Name'] for r in reader.trailer['/Root']['/OCProperties']['/OCGs']]
    assert names==['3_ARTWORK','2_CORNER_REFERENCE','1_LASER_CUT']
    text=(folder/'03_CUT_ONLY.svg').read_text(encoding='utf-8')
    assert text.count('<path ')==5 and text.count(' Z"')==5 and BLUE not in text
    assert len(items)==3 and sum(len(p['holes']) for p in items)==2
    for p in items:
        for h in p['holes']:assert p['poly'].contains(h)
    assert abs(assets['danpaengi']['h']/assets['garam']['h']-CFG['danpaengi_height_ratio'])<1e-9
    # Center of each base slot has no print ink, and the tab tips are unprinted.
    for p in items:
        if p['name']=='base':
            points=[h.centroid.coords[0] for h in p['holes']]
            mask=np.zeros(arr.shape[:2],np.uint8)
            for h in p['holes']:
                outline=np.round(np.asarray(h.buffer(1.5).exterior.coords)*300/25.4).astype(np.int32)
                cv2.fillPoly(mask,[outline],1)
            assert not arr[:,:,3][mask.astype(bool)].any(),'Ink must clear every slot by at least 1.5 mm'
        else:
            s=shapes[p['name']];points=[(p['tx']+s['cx'],p['ty']+s['shoulder']+s['depth']/2)]
        for x,y in points:
            xx=round(x*300/25.4);yy=round(y*300/25.4);assert arr[yy,xx,3]==0
    report={'preset':preset,'canvas_mm':BOARD,'base_mm':CFG['base_mm'],'pieces':3,
            'cut_closed_paths':5,'hole_paths_first':True,'hole_count':2,
            'tab_width_mm':CFG['tab_width_mm'],'tab_depth_mm':shapes['garam']['depth'],
            'slot_length_mm':CFG['slot_length_mm'],'slot_width_mm':preset['slot_width_mm'],
            'dimensions_are':'cut path centerlines; no kerf compensation',
            'fit_status':'UNTESTED - cut fit coupon from the same sheets first',
            'physical_fit_test':False,'minimum_piece_gap_mm':gap,'ai_layers':names,
            'blue_reference_four_sides':True,'unprinted_tabs_and_slots':True,'slot_ink_clearance_checked_mm':1.5,
            'assets':{n:{'art_height_mm':assets[n]['h'],'minimum_art_to_cut_mm':s['clearance']} for n,s in shapes.items()},
            'fit_test_slots':rows}
    (folder/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'parameters.json').write_text(json.dumps({**CFG,'selected_preset':preset},ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def guide(reports):
    pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
    pdfmetrics.registerFont(TTFont('MalgunB','C:/Windows/Fonts/malgunbd.ttf'))
    c=canvas.Canvas(str(OUT/'00_ASSEMBLY_GUIDE.pdf'),pagesize=(210*mm,297*mm))
    c.setTitle('가람과 단팽이 - 3T / 5T 끼움형 아크릴 디오라마')
    def text(x,y,s,size=10,bold=False,color='#33362e'):
        c.setFillColor(color);c.setFont('MalgunB' if bold else 'Malgun',size);c.drawString(x*mm,y*mm,s)
    def page(title,sub,num):
        c.setFillColor('#faf8f2');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        text(17,278,'DANPUNGBARAM / ACRYLIC DIORAMA 01',9,True,'#bd664e')
        text(17,262,title,21,True);text(17,250,sub,9,color='#777567')
        c.setStrokeColor('#d8d4c7');c.line(17*mm,243*mm,193*mm,243*mm)
        text(17,10,'2026.11.20 / 1:1 mm / 실물 끼움 시험 전 도안',8,color='#777567');text(190,10,str(num),8)
    first=reports[0]['preset']['name']
    page('두 친구를 꽂아 세우는 작은 무대','기본 구성: 받침대 1 + 가람 1 + 단팽이 1 = 총 3조각',1)
    c.drawImage(str(OUT/first/'preview/assembly.png'),19*mm,96*mm,width=172*mm,height=172*150/198*mm,mask='auto')
    text(17,83,'받침대 120 × 65 mm / 모서리가 둥근 투명 아크릴',11,True)
    text(17,71,'가람 그림 높이 65 mm / 단팽이 24.65 mm. 기존 원본 높이 비율을 유지했습니다.',9)
    text(17,62,'가람은 뒤쪽 왼편, 단팽이는 앞쪽 오른편. 두 개의 독립된 홈에 각각 꽂습니다.',9)
    text(17,53,'그림 바깥 투명 여백 3.5 mm 이상. 키링 구멍은 없고 아래쪽에 끼움 돌기가 있습니다.',9)
    text(17,44,'공통 돌기 폭 18 mm로 두 자리를 바꾸거나 같은 규격의 다른 캐릭터로 교체합니다.',9)
    text(17,31,'위 그림은 도안 기반 조립 예상도입니다. 실물 조립을 검증한 사진은 아닙니다.',8.5,color='#777567')
    c.showPage()
    page('3T와 5T, 달라지는 두 치수','T = 판 두께(mm). 홈 너비와 돌기 길이는 서로 다른 판을 기준으로 정합니다.',2)
    for y,title,lines in [
        (229,'1. 홈의 짧은 방향 = 서 있는 캐릭터 판 두께',[
            '3T 기본 홈: 18.8 × 3.00 mm / 5T 기본 홈: 18.8 × 5.00 mm.',
            '위 숫자는 절단 경로 치수이며, 실제 완성 홈 너비를 보장하는 값은 아닙니다.',
            '기본 파일에는 커프 보정이 없습니다. 같은 판의 시험 홈으로 너비를 결정하세요.']),
        (185,'2. 아래로 들어가는 돌기 길이 = 받침대 두께 - 0.40 mm',[
            '3T 받침대: 2.60 mm / 5T 받침대: 4.60 mm.',
            '돌기가 바닥 아래로 튀어나오지 않게 0.40 mm 짧게 설계했습니다.',
            '받침대의 실측 두께가 다르면 돌기 길이도 다시 계산합니다.']),
        (141,'3. 서로 다른 두께도 조합 가능',[
            '예: 캐릭터 3T + 받침대 5T → 홈 너비는 3T 기준, 돌기 길이는 4.60 mm.',
            '이 경우 캐릭터와 받침대는 서로 다른 재료에 나누어 잘라야 합니다.',
            '06_BASE_ONLY / 06_STANDEES_ONLY 파일은 같은 좌표를 유지한 분리 도안입니다.'])]:
        text(17,y,title,11,True)
        for i,s in enumerate(lines):text(17,y-12-i*8,s,9)
    text(17,94,'홈의 네 모서리는 반경 0.35 mm, 돌기 끝은 0.40 mm 사선입니다.',9)
    text(17,84,'긴 방향 18.8 mm는 18 mm 돌기와 홈 모서리가 간섭하지 않도록 여유를 둔 값입니다.',9)
    text(17,69,'단면 개념도',10,True)
    # Side-section schematic, exaggerated clearance for legibility.
    c.setStrokeColor('#879d94');c.setFillColor('#e4eee8');c.rect(25*mm,38*mm,69*mm,16*mm,fill=1)
    c.setFillColor('#faf8f2');c.rect(53*mm,38*mm,13*mm,16*mm,fill=1,stroke=0)
    c.setFillColor('#f1b18e');c.rect(54*mm,42*mm,11*mm,28*mm,fill=1,stroke=1)
    text(106,58,'위쪽: 캐릭터 판',9);text(106,49,'가로 판: 받침대',9)
    text(106,40,'아래쪽 틈: 0.40 mm',9)
    text(25,28,'설명용 확대도 / 실제 비례 아님',8,color='#777567')
    c.showPage()
    page('시험 조각부터 잘라 맞춰봅니다','최종 도안과 같은 판·같은 장비·같은 가공 설정에서 시험하세요.',3)
    c.drawImage(str(OUT/first/'preview/fit_test.png'),18*mm,143*mm,width=174*mm,height=174*78/160*mm,mask='auto')
    text(17,132,'시험판 1개 + 18 mm 돌기 시험키 1개. 본품 3조각과 별도입니다.',9,True)
    for i,s in enumerate([
        '시험 홈은 3 × 3 배열입니다. 왼쪽 위부터 1-9번, 각 행은 왼쪽에서 오른쪽 순서입니다.',
        '3T용: 2.60-3.40 mm / 5T용: 4.60-5.40 mm, 모두 0.10 mm 간격.',
        '캐릭터와 같은 판으로 시험키, 받침대와 같은 판으로 시험판을 자릅니다.',
        '숫자는 커팅선이 아닙니다. 인쇄하지 않으면 이 안내도를 보고 펜으로 적어도 됩니다.',
        '손으로 부드럽게 들어가고 기울어짐이 작은 홈을 고릅니다. 억지로 밀어 넣지 마세요.',
        '고른 홈의 표시 숫자를 --slot-width 값으로 입력해 최종 도안을 다시 만듭니다.',
        '전부 안 맞으면 실측 두께를 --part-thickness로 넣어 시험 범위를 옮깁니다.',
        '조립 전 보호필름을 제거합니다. 끼움 돌기와 홈 주변에는 인쇄 잉크를 올리지 않습니다.'
    ]):text(17,117-i*9,s,9)
    text(17,32,'두께 편차와 레이저가 태워 없애는 폭(커프)이 끼움에 영향을 줍니다.',9,True)
    text(17,22,'시험 결과에 맞춰 홈 너비를 조정하는 방식이며, 장비의 자동 보정도 중복 적용하지 않습니다.',8.5)
    c.showPage()
    page('제작 파일과 교체 규격','사진처럼 뺐다 꽂는 기본형 / 캐릭터 그림을 바꿔도 결합부 규격은 유지',4)
    lines=[
        ('01_PRINT_300ppi.png','UV 인쇄: 그림과 파란 기준선만 포함. 투명 배경.'),
        ('02_MASTER.ai / .vectorcraft','편집 원본: 그림 / 파란 기준선 / 빨간 커팅선 3개 레이어.'),
        ('03_CUT_ONLY.svg','재단: 빨강 #FF0000, 두께 0.001 mm, 채움 없음.'),
        ('04_FIT_TEST_*','시험판과 시험키. 본품 전에 사용.'),
        ('05_CHARACTER_TEMPLATE.svg','그림 교체용 빈 도안. 18 mm 돌기와 아래 어깨선을 유지.'),
        ('06_BASE_ONLY / STANDEES_ONLY','서로 다른 두께의 판을 쓸 때 분리해 사용하는 도안.')]
    for i,(a,b) in enumerate(lines):
        y=229-i*23;text(17,y,a,10,True);text(17,y-9,b,8.7)
    text(17,84,'본품 작업영역 220 × 150 mm / 파란 기준선 (4, 4), 212 × 142 mm.',9)
    text(17,74,'빨간 선은 홈 2개 + 외곽 3개 = 폐곡선 5개. 홈부터, 외곽은 마지막에 자릅니다.',9)
    text(17,64,'파란 선은 위치 기준이며 자르지 않습니다. 인쇄와 커팅은 같은 원점, 실제 크기 100%.',9)
    text(17,54,'3T와 5T는 대안입니다. 필요한 두께의 폴더 하나만 사용하면 됩니다.',9,True)
    text(17,41,'다른 캐릭터: 템플릿 안내 레이어를 지우고 그림을 넣으세요. 돌기에는 인쇄하지 않습니다.',8.7)
    text(17,32,'기본 받침대에서 교체하려면 외곽 폭 약 64 mm, 그림 높이 약 65 mm 이내로 시작하세요.',8.7)
    text(17,23,'마스코트 벡터는 기존 제작 파일을 재사용했습니다. 조립 구조만 새로 설계했습니다.',8.5,color='#777567')
    c.showPage()
    page('출력 전 치수 확인','A4 100% 출력 / 페이지 맞춤 해제 / 이 페이지는 인쇄 그림으로 사용하지 않습니다.',5)
    # Actual-size base drawing plus dimension labels and two preset slots.
    c.setStrokeColor('#33362e');c.setLineWidth(.5)
    x,y=40,144;c.roundRect(x*mm,y*mm,120*mm,65*mm,11*mm,stroke=1,fill=0)
    for xx,yy in CFG['mount_centers_mm'].values():
        c.roundRect((x+xx-9.4)*mm,(y+65-yy-1.5)*mm,18.8*mm,3*mm,.35*mm,stroke=1,fill=0)
    text(68,220,'받침대 외곽 120 × 65 mm',11,True)
    text(49,132,'위 도면은 3T 기본 홈을 표시한 실물 크기 받침대입니다.',9)
    text(17,110,'조립 순서',11,True)
    for i,s in enumerate(['① 시험 조각으로 홈 너비 선택 → 해당 값으로 도안 재생성.',
                          '② 실제 크기 100%로 인쇄하고 같은 좌표로 커팅.',
                          '③ 가람을 뒤 왼쪽 홈, 단팽이를 앞 오른쪽 홈에 수직으로 삽입.',
                          '④ 두 캐릭터의 어깨선이 받침대 윗면에 닿는지 확인.']):text(17,98-i*9,s,9)
    c.line(30*mm,42*mm,130*mm,42*mm)
    for i in range(11):
        x=30+10*i;c.line(x*mm,42*mm,x*mm,(47 if i%5==0 else 45)*mm);text(x-1,35,str(i*10),7)
    text(30,24,'100 mm 확인자 - 실제 자로 확인하세요.',9)
    c.save()


def readme(reports):
    text='''# 가람 + 단팽이 끼움형 디오라마 V1

![조립 예상도](3T/preview/assembly.png)

**본품 1세트 = 받침대 1 + 가람 1 + 단팽이 1, 총 3조각.**
3T와 5T는 같은 세트의 두께별 대안이며, 각 폴더는 1세트 분량입니다.

받침대 120×65mm / 가람 그림 높이65mm / 단팽이24.65mm.
같은 원본 카드의 캐릭터 높이 비율을 유지합니다. 두 캐릭터의 돌기 폭은 공통18mm로 서로 교체할 수 있습니다.
다른 캐릭터는 `05_CHARACTER_TEMPLATE.svg`의 그림과 윗부분 윤곽을 바꾸고 아래 결합부를 유지하세요.

## 먼저 시험 조각

기본 홈 너비3.00/5.00mm는 **절단 경로의 시작값**입니다. 실물 끼움은 아직 시험하지 않았습니다.
같은 판·같은 설정으로 `04_FIT_TEST`를 잘라 맞는 홈을 고른 뒤 본품을 자르세요.
기본 시험 범위: 3T 2.60-3.40mm / 5T 4.60-5.40mm, 0.10mm 간격.
번호는 왼쪽 위부터 가로 방향으로1-9입니다. 숫자 레이어는 커팅 대상이 아닙니다.

- 홈의 짧은 너비: **서 있는 캐릭터 판**의 두께와 시험 결과에 따라 결정.
- 돌기 길이: **받침대**의 실측 두께에서0.40mm 뺀 값. 기본3T 2.60mm /5T 4.60mm.
- 홈 긴 방향18.8mm, 모서리반경0.35mm, 돌기끝 사선0.40mm.
- 돌기와 홈 주변은 인쇄하지 않습니다. 보호필름 제거 후 손으로 시험합니다.
- 본품과 시험판은 별도입니다. 3T/5T 파일을 한꺼번에 출력하지 않습니다.

## 파일

- `00_ASSEMBLY_GUIDE.pdf`: 조립·치수·시험 순서와 A4 실측 확인자.
- 두께별 폴더 `01_PRINT_300ppi.png`: 파란 기준선을 포함한 투명 PNG, 300ppi.
- `02_MASTER.ai` / `.vectorcraft` / `.svg`: 그림, 기준선, 재단선의3개 레이어.
- `03_CUT_ONLY.svg`: 빨간0.001mm 폐곡선5개(홈2+외곽3), 홈을 먼저 자릅니다.
- `04_FIT_TEST_*`: 9개 홈 시험판과18mm 돌기 시험키. 혼합두께이면 BASE/KEY 분리파일을 서로 다른 판에 출력.
- `05_CHARACTER_TEMPLATE.svg`: 다른 캐릭터용 공통 돌기 템플릿. 안내 레이어는 삭제하고 출력.
- `06_BASE_ONLY.svg` / `06_STANDEES_ONLY.svg`: 판 두께를 서로 다르게 쓸 때 분리된 편집 도안.
- `parameters.json`, `validation_report.json`: 적용 치수 및 파일검사 결과.

본품 작업영역220×150mm. 3T/5T의 인쇄·재단 좌표는 같습니다.
파란 사각형(4,4),212×142mm은 위치기준이며 자르지 않습니다. 실제 크기100%로 출력합니다.
전면 정방향 인쇄가 기본입니다. 후면 인쇄라면 백색잉크와 반전 순서를 현장 방식에 맞춥니다.

## 치수 조정

저장소 루트에서:

```powershell
python scripts/build_diorama.py
# 시험에서 고른 절단경로 홈 너비가 2.80mm인 경우(예시일 뿐 권장값 아님)
python scripts/build_diorama.py --part-thickness 3 --base-thickness 3 --slot-width 2.80 --name calibrated_3T
# 캐릭터3T + 받침대5T: 두 재료를 따로 커팅
python scripts/build_diorama.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
```

`--part-thickness`와`--base-thickness`에는 실측 소수값도 넣을 수 있습니다.
기본 캐릭터 높이·베이스 치수·홈 위치·돌기 폭은 `configs/diorama.json`에서 관리합니다.
그림 파일만 통째로 확대하면 돌기도 확대되므로, 다른 캐릭터를 넣을 때 결합부 규격을 유지합니다.
기본 허용 크기의 출발점은 외곽폭64mm·그림높이65mm 이내입니다. 실제 조립간섭·무게·안정성은 교체 그림마다 확인합니다.

## 가공 참고

아래는 커프와 시험 가공 원칙의 근거입니다. 해당 업체의 장비수치를 우리 장비 값으로 대입하지 않았습니다.

- [Ponoko - Interlocking 3D laser cut designs](https://help.ponoko.com/en/articles/4527166-interlocking-3d-laser-cut-designs)
- [Ponoko - How much material does the laser burn away?](https://help.ponoko.com/en/articles/4442594-how-much-material-does-the-laser-burn-away)

사용자 제공 사진은 끼움 방식 참고용이며, 사진 속 상품 그림을 복제하지 않았습니다.
'''
    (OUT/'README.md').write_text(text,encoding='utf-8')


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
    assets=load_art();reports=[]
    for preset in presets:
        folder=OUT/preset['name'];(folder/'preview').mkdir(parents=True,exist_ok=True)
        shapes={n:standee(assets[n],preset['base_thickness_mm']) for n in ['garam','danpaengi']}
        items,gap=make_board(assets,shapes,preset,folder)
        rows=fit_test(preset,folder);assembly(assets,shapes,preset,folder);templates(assets,shapes,preset,folder)
        report=validate(assets,shapes,preset,items,gap,folder,rows);reports.append(report)
        print(json.dumps(report,ensure_ascii=False),flush=True)
    if not custom:
        guide(reports);readme(reports)
        with zipfile.ZipFile(ROOT/'output/Danpungbaram_Diorama_V1_3T_5T.zip','w',zipfile.ZIP_DEFLATED) as z:
            for file in sorted(OUT.rglob('*')):
                if file.is_file() and (file.parent==OUT or file.relative_to(OUT).parts[0] in ['3T','5T']):
                    z.write(file,Path('Danpungbaram_Diorama_V1')/file.relative_to(OUT))
        print('Default package complete',flush=True)


if __name__=='__main__':main()
