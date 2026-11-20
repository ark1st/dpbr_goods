"""Small-batch revision: 4 sets + 4 standalone logos (16 acrylic pieces).
Vector artwork, mm geometry, explicit print/reference/cut layers.
"""
from pathlib import Path
import sys, json, math, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, Point, box
from shapely import affinity, concave_hull
from shapely.ops import unary_union
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from guide_fonts import GUIDE_FONT, GUIDE_BOLD, register_guide_fonts
from laser_paths import cut_path
from vector_utils import runvc,svg_doc,path,poly_path,layer

OUT=ROOT/'output/production_v4'
CFG=json.loads((ROOT/'configs/keyring.json').read_text(encoding='utf-8'))
TMP=ROOT/'tmp/v3'
AS=OUT/'assets'
W,H=300,160
SOURCE_RATIO=135/356

def render(svg,png,scale=6):
    dest=TMP/(svg.stem+'.pdf')
    runvc(['convert',svg,dest])
    doc=fitz.open(dest);doc[0].get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=True).save(str(png))
    return dest

def artwork():
    assets=json.loads((ROOT/'assets/artwork.json').read_text(encoding='utf-8'))
    for name,a in assets.items():
        svg=AS/f'{name}.svg'
        svg.write_text(svg_doc(a['w'],a['h'],a['inner']),encoding='utf-8')
        render(svg,AS/f'{name}.png',8)
    (TMP/'assets.json').write_text(json.dumps(assets),encoding='utf-8')
    return assets

def geometry(assets):
    shapes={}
    for name,a in assets.items():
        im=Image.open(AS/f'{name}.png').convert('RGBA');alpha=np.array(im)[:,:,3]
        contours,_=cv2.findContours((alpha>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        polys=[Polygon(c[:,0,:]*[a['w']/im.width,a['h']/im.height]).buffer(0) for c in contours if cv2.contourArea(c)>6]
        art=unary_union(polys)
        carrier=concave_hull(art,ratio=.45) if 'logo' in name else art
        body=carrier.buffer(CFG['clear_border_mm'],quad_segs=24)
        if body.geom_type!='Polygon':body=concave_hull(body,ratio=.5)
        body=Polygon(body.exterior)
        cs=np.array(art.convex_hull.exterior.coords);top=cs[cs[:,1]<cs[:,1].min()+.2]
        hx=float(np.mean(top[:,0]));hy=float(art.bounds[1]-2-CFG['hole_to_art_mm'])
        radius=2+CFG['hole_edge_mm']
        tab=Point(hx,hy).buffer(radius,quad_segs=128)
        neck=box(hx-radius+.5,hy,hx+radius-.5,art.bounds[1]+1.5)
        outer=unary_union([body,tab,neck]).buffer(.5,quad_segs=32).buffer(-.5,quad_segs=32)
        assert outer.geom_type=='Polygon'
        outer=Polygon(outer.exterior)
        hole=Point(hx,hy).buffer(2,quad_segs=64)
        assert outer.contains(art) and outer.contains(hole)
        clearance=outer.boundary.distance(art)
        hole_art=hole.distance(art);hole_edge=outer.boundary.distance(hole)
        assert CFG['clear_border_mm']-.03 <= clearance <= CFG['clear_border_mm']+.001,(name,clearance)
        assert hole_art>=CFG['hole_to_art_mm']-.001,(name,hole_art)
        assert CFG['hole_edge_mm']-.003<=hole_edge<=CFG['hole_edge_mm']+.001,(name,hole_edge)
        shapes[name]={'poly':outer,'hole':(hx,hy),'art':art,'clearance':clearance,'hole_art':hole_art,'hole_edge':hole_edge}
    return shapes

def at(name,x,y,shapes,ident):
    p=shapes[name]['poly'];bx,by,_,_=p.bounds
    tx=x-bx;ty=y-by
    return {'name':name,'tx':tx,'ty':ty,'poly':affinity.translate(p,tx,ty),'id':ident}

def place(shapes):
    # Fixed inventory: four of each design. Preserve upright orientation.
    occ=np.zeros((H,W),np.float32)
    occ[:7,:]=1;occ[-7:,:]=1;occ[:,:7]=1;occ[:,-7:]=1
    items=[]
    # Reviewed nesting order. Interleave smaller pieces in the mascot gaps.
    order=['solo_logo','garam','garam','mini_logo','mini_logo','mini_logo',
           'solo_logo','danpaengi','mini_logo','danpaengi','garam','solo_logo',
           'garam','solo_logo','danpaengi','danpaengi']
    for name in order:
        expanded=shapes[name]['poly'].buffer(3.05)
        bx,by,rx,ry=expanded.bounds
        mask=np.zeros((math.ceil(ry-by)+1,math.ceil(rx-bx)+1),np.uint8)
        cv2.fillPoly(mask,[np.round(np.array(expanded.exterior.coords)-[bx,by]).astype(np.int32)],1)
        scores=cv2.matchTemplate(occ,mask.astype(np.float32),cv2.TM_CCORR)
        ys,xs=np.where(scores<.25)
        if not len(ys):raise ValueError(f'No space for {name}; do not silently drop pieces')
        rank=(ys+mask.shape[0])+.12*xs
        index=int(np.argmin(rank));x=int(xs[index]);y=int(ys[index])
        mh,mw=mask.shape;occ[y:y+mh,x:x+mw]=np.maximum(occ[y:y+mh,x:x+mw],mask)
        tx=x-bx;ty=y-by;ident=f'{name}_{sum(p["name"]==name for p in items)+1}'
        items.append({'name':name,'tx':tx,'ty':ty,'poly':affinity.translate(shapes[name]['poly'],tx,ty),'id':ident})
    for p in items:assert box(9,9,W-9,H-9).contains(p['poly'])
    gap=min(p['poly'].distance(q['poly']) for i,p in enumerate(items) for q in items[:i])
    assert gap>=5,gap
    return items,gap

def make_layers(assets,shapes,items,board_w,board_h,shift=(0,0),review=False):
    arts=[];holes=[];outlines=[]
    sw=.22 if review else .001
    for i,p in enumerate(items):
        a=assets[p['name']];s=shapes[p['name']]
        tx=p['tx']+shift[0];ty=p['ty']+shift[1]
        t=f'translate({tx:.6f} {ty:.6f})'
        arts.append(f'<g id="{p["id"]}" transform="{t}">{a["inner"].replace("hat_clip",f"hat_clip_{i}")}</g>')
        hx,hy=s['hole']
        holes.append(f'<g transform="{t}"><circle cx="{hx:.6f}" cy="{hy:.6f}" r="2" fill="none" stroke="#ff0000" stroke-width="{sw}"/></g>')
        outlines.append(f'<g transform="{t}">{path(cut_path(s["poly"]),"none","#ff0000",sw)}</g>')
    # Match the guide's continuous blue rectangle. It encloses the common work
    # area; no per-character rectangle and no blue strokes in CUT_ONLY.
    x=4+shift[0];y=4+shift[1]
    reference=f'<rect x="{x}" y="{y}" width="{W-8}" height="{H-8}" fill="none" stroke="#0000ff" stroke-width="0.3"/>'
    return layer('3_ARTWORK',''.join(arts)),layer('2_CORNER_REFERENCE',reference),layer('1_LASER_CUT',''.join(holes+outlines))

def cut_pdf(items,shapes):
    # Use the same checked curves as SVG/AI; do not rebuild polylines here.
    runvc(['convert',OUT/'04_CUT_ONLY.svg',OUT/'04_CUT_ONLY.pdf'])


def files(assets,shapes,items):
    ar,ref,cut=make_layers(assets,shapes,items,W,H)
    master=OUT/'02_MASTER.svg';master.write_text(svg_doc(W,H,ar+ref+cut,'V4 16 pieces - 300 x 160 mm'),encoding='utf-8')
    printing=OUT/'01_PRINT.svg';printing.write_text(svg_doc(W,H,ar+ref),encoding='utf-8')
    (OUT/'04_CUT_ONLY.svg').write_text(svg_doc(W,H,cut),encoding='utf-8')
    commands=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
        {'command':'document.save','params':{'path':str(OUT/'03_MASTER.vectorcraft'),'format':'vectorcraft','compress':False}},
        {'command':'document.export','params':{'path':str(OUT/'02_MASTER.ai'),'format':'ai','createLayers':True,'preserveEditing':True}}]
    cmd=TMP/'export-master.json';cmd.write_text(json.dumps(commands),encoding='utf-8')
    (TMP/'master-export.log').write_text(runvc(['run','--in',master,'--commands',cmd]),encoding='utf-8')
    commands=[{'command':'document.export','params':{'path':str(OUT/'01_PRINT_300ppi.png'),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}}]
    cmd=TMP/'export-print.json';cmd.write_text(json.dumps(commands),encoding='utf-8')
    (TMP/'print-export.log').write_text(runvc(['run','--in',printing,'--commands',cmd]),encoding='utf-8')
    ar,ref,cut=make_layers(assets,shapes,items,W,H,review=True)
    rv=OUT/'preview/board_layout.svg';rv.write_text(svg_doc(W,H,'<rect width="300" height="160" fill="white"/>'+ar+ref+cut),encoding='utf-8')
    render(rv,OUT/'preview/board_layout.png',1.7)
    # Optional full-sheet coordinates contain THE SAME sixteen pieces only.
    ar,ref,cut=make_layers(assets,shapes,items,800,600,shift=(15,15))
    folder=OUT/'optional_800x600'
    for name,content in [('MASTER',ar+ref+cut),('PRINT',ar+ref),('CUT_ONLY',cut)]:
        (folder/f'800x600_SAME_16_{name}.svg').write_text(svg_doc(800,600,content),encoding='utf-8')
    runvc(['convert',folder/'800x600_SAME_16_MASTER.svg',folder/'800x600_SAME_16_MASTER.vectorcraft'])
    runvc(['convert',folder/'800x600_SAME_16_MASTER.svg',folder/'800x600_SAME_16_MASTER.ai'])
    commands=[{'command':'document.export','params':{'path':str(folder/'800x600_SAME_16_PRINT_300ppi.png'),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}}]
    cmd=TMP/'export-fullsheet.json';cmd.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',folder/'800x600_SAME_16_PRINT.svg','--commands',cmd])
    cut_pdf(items,shapes)

def single_keyring(name,assets,shapes):
    a=assets[name];s=shapes[name];p=s['poly'];x0,y0,x1,y1=p.bounds
    hx,hy=s['hole'];margin=2
    inner=f'<g transform="translate({margin-x0} {margin-y0})">'+a['inner']+path(poly_path(p),'none','#ff0000',.22)+f'<circle cx="{hx}" cy="{hy}" r="2" fill="none" stroke="#ff0000" stroke-width="0.22"/></g>'
    svg=OUT/f'preview/{name}_keyring.svg';svg.write_text(svg_doc(x1-x0+4,y1-y0+4,inner),encoding='utf-8')
    render(svg,OUT/f'preview/{name}_keyring.png',4)
    return x1-x0+4,y1-y0+4

def source_ratio_preview(font_path):
    im=Image.open(ROOT/'assets/mascot_card.png').convert('RGB')
    crop=im.crop((525,565,1055,945)).resize((1060,760))
    d=ImageDraw.Draw(crop);font=ImageFont.truetype(str(font_path),24)
    for label,(x,y,w,h),color in [('가람 356px',(551,579,311,356),'#195aac'),('단팽이 135px',(884,794,155,135),'#ba4242')]:
        x=(x-525)*2;y=(y-565)*2;w*=2;h*=2
        d.rectangle((x,y,x+w,y+h),outline=color,width=3)
        d.text((x,y-25 if y>=25 else y+5),label,font=font,fill=color,stroke_width=1,stroke_fill='white')
    crop.save(OUT/'preview/source_ratio_evidence.png')

def label(c,x,y,s,size=10,bold=False,color='#252525'):
    c.setFillColor(color);c.setFont(GUIDE_BOLD if bold else GUIDE_FONT,size);c.drawString(x*mm,y*mm,s)

def guides(assets,shapes,gap):
    def outline(name):
        x0,y0,x1,y1=shapes[name]['poly'].bounds
        return f'약 {x1-x0:.1f} × {y1-y0:.1f} mm'
    c=canvas.Canvas(str(OUT/'00_REVISION_GUIDE.pdf'),pagesize=(210*mm,297*mm));c.setTitle('단풍바람 키링 수정본 V4 - 소량 제작 16조각')
    def page(title,sub,n):
        c.setFillColor('#faf8f3');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        label(c,17,279,'DANPUNGBARAM / REVISION 04',9,True,'#d46850')
        label(c,17,264,title,22,True);label(c,17,252,sub,9,color='#666666')
        c.setStrokeColor('#d7d1c7');c.line(17*mm,245*mm,193*mm,245*mm)
        label(c,17,10,'2026.11.20 수정 / 투명 여백 2.5 mm / 실제 크기 100%',8,color='#666666');label(c,190,10,str(n),8)
    def section(y,title,rows):
        label(c,17,y,title,12,True);y-=10
        for row in rows:label(c,17,y,row,9.4);y-=6.2
        return y-9
    page('투명 테두리를 줄였습니다','4세트 + 로고 단독 4개 = 총 16조각',1)
    y=section(231,'이번 제작 수량',[
        '한 세트: 가람 1개 + 작은 단팽이 1개 + 미니 로고 1개. 네 세트입니다.',
        '로고만 달 수 있는 단독 키링은 4개를 추가했습니다.',
        '수량 16조각과 그림 크기는 유지하고, 일반 외곽 여백만 2.5 mm로 줄였습니다.',
        '기본 파일과 optional_800x600 파일은 같은 16조각입니다. 둘 다 찍지 마세요.'
    ])
    y=section(y,'그림 크기 - 투명 테두리와 고리 부분 제외',[
        f'가람 높이 55 mm / 단팽이 높이 {55*SOURCE_RATIO:.2f} mm.',
        '같은 원본 카드에서 가람 356px, 단팽이 135px로 측정했습니다.',
        f'원본 높이 비율 1 : {SOURCE_RATIO:.3f}를 적용했습니다. 원본에 물리적 치수는 없습니다.',
        '세트용 미니 로고 높이 18 mm: 가람 높이의 약 33%.',
        '단독 로고 높이 30 mm: 가람보다 작지만 단독으로 달기 편한 별도 크기.',
        '단팽이 몸통과 껍데기 경계를 다시 그리고 회색 삼각형을 제거했습니다.'
    ])
    y=section(y,'구멍과 재단 여유',[
        '일반 외곽 여백: 2.5 mm 기준. 고리 목과 로고 연결부는 구조상 더 넓습니다.',
        '구멍 지름: 4 mm. 그림 위로 별도의 둥근 고리 부분을 올렸습니다.',
        '구멍 가장자리와 그림: 최소 3 mm.',
        '구멍 가장자리와 아크릴 외곽: 약 2.5 mm. 고리 외경은 약 9 mm입니다.',
        f'배치된 조각끼리 외곽 간격은 최소 {gap:.2f} mm입니다.',
        f'완성 외곽: 가람 {outline("garam")} / 단팽이 {outline("danpaengi")}.',
        f'미니 로고 {outline("mini_logo")} / 단독 로고 {outline("solo_logo")}.'
    ])
    c.drawImage(str(OUT/'preview/board_layout.png'),55*mm,19*mm,width=100*mm,height=100*H/W*mm,mask='auto')
    # Overview sits in a reserved bottom area; the text layout is kept above it.
    c.showPage()
    page('모서리 기준선은 이렇게 씁니다','파란색 = 위치 기준 / 빨간색 = 레이저 재단 / 그림 = UV 인쇄',2)
    y=section(231,'설명서 예시대로 파란 사각형을 포함',[
        '설명서 1쪽의 파란 사각 모서리 기준선을 연속된 사각형으로 넣었습니다.',
        '기본 캔버스 300 × 160 mm, 기준 사각형은 (4, 4)에서 292 × 152 mm입니다.',
        '선 색 #0000FF, 두께 0.3 mm. 인쇄 PNG와 AI에서 좌표가 같습니다.',
        '인쇄와 커팅 위치·방향을 같은 원점에 맞추고, 크기 변형 여부를 확인하는 표식입니다.',
        '자동 인식용 마크라고 가정하면 안 됩니다. 실제 정합 방법은 현장 장비에 따릅니다.',
        '파란 사각형은 자르는 선이 아닙니다. 레이저 출력 대상에서 제외하세요.'
    ])
    y=section(y,'기본 파일 - 이 순서로 사용',[
        '01_PRINT_300ppi.png: 투명 PNG 3543 × 1890 px, 파란 기준선 + 그림.',
        '02_MASTER.ai / 03_MASTER.vectorcraft: 레이어 3개를 보존한 편집 원본.',
        '1_LASER_CUT = 빨간 절단선 / 2_CORNER_REFERENCE = 파란 기준선.',
        '3_ARTWORK = 그림. UV 인쇄할 때는 2 + 3만 켭니다.',
        '04_CUT_ONLY.svg 또는 PDF: 빨간 #FF0000, 0.001 mm, 채움 없음.',
        '32개 폐곡선: 외곽 16개 + 구멍 16개. 구멍부터, 외곽은 나중에 자릅니다.',
        '커팅 전용 파일에서는 파란 기준선을 제외했습니다. 원점과 캔버스 크기는 같습니다.'
    ])
    y=section(y,'판·색상·현장 설정',[
        '기본 작업영역은 설명서의 800 × 500 mm 제한 안에 들어갑니다.',
        '800 × 600 판 전체 좌표가 필요하면 optional_800x600 폴더를 사용하세요.',
        '그 파일은 같은 16조각을 좌상단에서 15 mm 이동해 배치한 대안입니다.',
        '큰 판을 받는 장비인지 먼저 확인하고, 인쇄와 커팅에 같은 버전을 사용합니다.',
        '실제 크기 100%, 자동 맞춤 해제, 전면 정방향 인쇄. 거울 반전하지 않습니다.',
        'PNG는 CMYK를 지원하지 않아 sRGB로 저장했습니다. RIP에서 장비 색상으로 변환.',
        '백색 잉크는 PNG의 불투명 영역 기준으로 설정하고, 먼저 1개를 시험합니다.',
        '마스코트는 카드뉴스를 참고한 벡터 재구성본입니다. 로고는 원본 AI 경로입니다.'
    ])
    c.showPage()
    page('실물 크기 확인용','A4 용지에 100% 출력 / 인쇄용 그림 파일로 사용하지 마세요',3)
    labels={'garam':'가람 55 mm','danpaengi':f'단팽이 {55*SOURCE_RATIO:.1f} mm','mini_logo':'미니 로고 18 mm','solo_logo':'단독 로고 30 mm'}
    positions={'garam':(24,151),'danpaengi':(100,189),'mini_logo':(153,193),'solo_logo':(112,116)}
    for name,(x,y) in positions.items():
        w,h=single_keyring(name,assets,shapes)
        c.drawImage(str(OUT/f'preview/{name}_keyring.png'),x*mm,y*mm,width=w*mm,height=h*mm,mask='auto')
        label(c,x,y-7,labels[name],9,True)
    label(c,17,94,'빨간 선은 확대해 보이도록 표시한 재단 위치입니다.',9)
    label(c,17,87,'그림 크기 비율과 고리 구멍 주변의 투명 여유를 함께 확인하세요.',9)
    c.setStrokeColor('#252525');c.setLineWidth(.5);c.line(25*mm,66*mm,125*mm,66*mm)
    for i in range(11):
        x=25+i*10;c.line(x*mm,66*mm,x*mm,(70 if i%5==0 else 68)*mm);label(c,x-1,59,str(i*10),7)
    label(c,25,48,'100 mm 확인자 - 실제 자로 길이를 확인하세요.',9,True)
    c.save()

def assembly_preview(assets,shapes):
    # A separate assembly diagram, never included in print/cut layers.
    poses=[at('garam',12,37,shapes,'assembly_garam'),
           at('mini_logo',77,42,shapes,'assembly_logo'),
           at('danpaengi',79,88,shapes,'assembly_snail')]
    content=['<rect width="132" height="135" fill="#faf8f3"/>']
    for p in poses:
        hx,hy=shapes[p['name']]['hole'];hx+=p['tx'];hy+=p['ty']
        content.append(path(f'M60 24 Q{hx} 24 {hx} {hy}','none','#96938e',.45))
    content.append('<ellipse cx="60" cy="15" rx="11" ry="9" fill="none" stroke="#5a5854" stroke-width="1.1"/>')
    for p in poses:
        sh=shapes[p['name']];a=assets[p['name']];hx,hy=sh['hole']
        # Show the clear carrier on an off-white field with a soft grey edge.
        carrier=path(poly_path(sh['poly']),'#ffffff','#c4c6c6',.28)
        hole=f'<circle cx="{hx}" cy="{hy}" r="2" fill="#faf8f3" stroke="#c4c6c6" stroke-width="0.28"/>'
        content.append(f'<g transform="translate({p["tx"]} {p["ty"]})">{carrier}{a["inner"]}{hole}</g>')
    svg=OUT/'preview/assembly_example.svg';svg.write_text(svg_doc(132,135,''.join(content)),encoding='utf-8')
    render(svg,OUT/'preview/assembly_example.png',2.2)

def validate(assets,shapes,items,gap):
    assert len(items)==16 and all(sum(p['name']==name for p in items)==4 for name in assets)
    report={'revision':4,'nominal_art_border_mm':CFG['clear_border_mm'],'quantity':16,'set_count':4,'standalone_logos':4,'canvas_mm':[W,H],
        'source_measurement':{'garam_bbox_px':[551,579,311,356],'danpaengi_bbox_px':[884,794,155,135],'height_ratio':SOURCE_RATIO},
        'min_piece_gap_mm':gap,'hole_diameter_mm':4,'assets':{}}
    for name,a in assets.items():
        s=shapes[name];x0,y0,x1,y1=s['poly'].bounds
        report['assets'][name]={'art_mm':[a['w'],a['h']],'acrylic_mm':[x1-x0,y1-y0],'art_to_cut_mm':s['clearance'],'hole_to_art_mm':s['hole_art'],'hole_to_edge_mm':s['hole_edge']}
    assert abs(assets['danpaengi']['h']/assets['garam']['h']-SOURCE_RATIO)<1e-8
    assert '#e5e5e5' not in assets['danpaengi']['inner']
    png=Image.open(OUT/'01_PRINT_300ppi.png');assert png.mode=='RGBA' and png.size==(3543,1890)
    assert abs(png.info['dpi'][0]-300)<.1
    arr=np.array(png);blue=(arr[:,:,2]>240)&(arr[:,:,0]<20)&(arr[:,:,1]<20)&(arr[:,:,3]>150)
    # Check the middle of each side, away from any artwork.
    ratio=300/25.4
    for x,y in [(150,4),(150,156),(4,80),(296,80)]:
        xx=round(x*ratio);yy=round(y*ratio);assert blue[yy-3:yy+4,xx-3:xx+4].any(),(x,y)
    reader=PdfReader(OUT/'02_MASTER.ai');names=[r.get_object()['/Name'] for r in reader.trailer['/Root']['/OCProperties']['/OCGs']]
    assert names==['3_ARTWORK','2_CORNER_REFERENCE','1_LASER_CUT']
    dims=[float(reader.pages[0].mediabox.width)*25.4/72,float(reader.pages[0].mediabox.height)*25.4/72]
    assert max(abs(dims[0]-W),abs(dims[1]-H))<.01
    cut=PdfReader(OUT/'04_CUT_ONLY.pdf');ops=cut.pages[0].get_contents().operations
    assert sum(o==b'h' for _,o in ops)==32
    doc=fitz.open(OUT/'04_CUT_ONLY.pdf');paths=doc[0].get_drawings();assert len(paths)==32
    assert all(p['color']==(1,0,0) and p['fill'] is None and abs(p['width']-.001*72/25.4)<1e-5 for p in paths)
    report['checks']={'quantity':16,'closed_cut_paths':32,'ai_layers':names,'png_pixels':list(png.size),'png_ppi':png.info['dpi'],'blue_reference_four_sides':True,'physical_print_cut_test':False}
    (OUT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def package(report):
    readme='''단풍바람 아크릴 수정본 V4 / 2026-11-20

확정 수량: 4세트 + 로고 단독 4개 = 총 16조각.
세트 1개 = 가람 1 + 단팽이 1 + 미니 로고 1.

먼저 00_REVISION_GUIDE.pdf, preview/board_layout.png를 확인하세요.
기본 작업영역은 300x160mm입니다. 안내문의 800x500mm 제한 이내입니다.
큰 아크릴판의 일부만 사용하고 나머지 판은 보존할 수 있습니다.

UV 인쇄: 01_PRINT_300ppi.png (파란 사각 기준선 포함, 빨간 커팅선 제외)
편집: 02_MASTER.ai 또는 03_MASTER.vectorcraft (레이어 3개)
커팅: 04_CUT_ONLY.svg 또는 PDF (빨강 #FF0000, 0.001mm, 32개 폐곡선)
인쇄와 커팅 모두 실제 크기 100%, 같은 원점, 자동 맞춤 해제.

optional_800x600은 같은 16조각을 800x600mm 좌표에 배치한 대안입니다.
기본 파일과 추가 파일을 둘 다 출력하지 마세요. 큰 판 사용 가능 장비인지 확인하세요.

그림 높이: 가람55mm / 단팽이20.86mm / 미니로고18mm / 단독로고30mm.
구멍4mm, 구멍-그림3mm 이상, 구멍-외곽2.5mm 기준, 일반 그림-재단선2.5mm 기준(근사오차 0.03mm 이내).
고리 목·로고 연결부는 구조상 더 넓으며, 빨간 레이저 선은 0.001mm입니다.
마스코트는 원본 카드뉴스 참고 벡터 재구성본, 로고는 원본AI 심볼입니다.
티셔츠 파일 수정 요청은 없어서 이번 ZIP은 수정된 아크릴 파일만 담았습니다.
'''
    (OUT/'00_START_HERE.txt').write_text(readme,encoding='utf-8-sig')
    (OUT/'README.md').write_text('''# 마스코트·로고 키링 V4 · 16조각

![전체 배치 시안](preview/board_layout.png)

4세트 + 로고 단독 4개입니다. 한 세트는 가람·단팽이·미니 로고 각 1개입니다.
작업 영역 300×160mm, 가람 높이 55mm, 단팽이 높이 20.86mm로 원본 비율을 유지했습니다.
일반 투명 여백과 구멍-외곽 여유는 2.5mm입니다. 실제 레이저 선은 빨강 0.001mm입니다.

- [UV 인쇄 PNG](01_PRINT_300ppi.png): 투명 300ppi, 파란 위치 기준선 포함.
- [편집용 AI](02_MASTER.ai): 그림·위치 기준선·칼선 3개 레이어.
- [재단 전용 PDF](04_CUT_ONLY.pdf): 32개 폐곡선.
- [시안과 제작 안내 PDF](00_REVISION_GUIDE.pdf)
- [전체 ZIP](../Danpungbaram_V4_SMALL_BATCH_16pcs.zip)

인쇄·재단은 같은 원점과 실제 크기 100%로 진행합니다. 파란 기준선은 절단하지 않습니다.
optional_800x600은 같은 16조각을 큰 대지에 놓은 대안이므로 중복 출력하지 않습니다.
''' ,encoding='utf-8')
    sources='''Sources
Maker-space guide: user-supplied 2026-11-16_scan_QuickScanApp.com.pdf, page 1.
Notion: https://ark1st.notion.site/4199cd9d18388078b431c5573819102d
Ratio measurement: original mascot_01.png card, not separate profile thumbnails.
Garam dark outline bbox 311x356px; Danpaengi dark outline bbox 155x135px.
Pixel outlines are approximate visual measurements, not original character model-sheet dimensions.
User supplied keyring sketch: 2026-11-17, used for the smaller secondary-logo relationship.
Logo: assets/source_logo.ai, 7 original symbol paths.
VectorCraft export: genuine PDF-compatible AI, native VectorCraft, RGB PNG.
'''
    (OUT/'SOURCES.txt').write_text(sources,encoding='utf-8')
    zpath=ROOT/'output/Danpungbaram_V4_SMALL_BATCH_16pcs.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,Path('Danpungbaram_V4')/p.relative_to(OUT))
    with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
    print('ZIP',zpath,zpath.stat().st_size,flush=True)

if __name__=='__main__':
    font_path=register_guide_fonts()
    for folder in [OUT,AS,TMP,OUT/'preview',OUT/'optional_800x600']:
        folder.mkdir(parents=True,exist_ok=True)
    assets=artwork();shapes=geometry(assets);items,gap=place(shapes)
    print('geometry',json.dumps({k:{'size':v['poly'].bounds,'art_cut':v['clearance'],'hole_art':v['hole_art'],'hole_edge':v['hole_edge']} for k,v in shapes.items()}),flush=True)
    files(assets,shapes,items);source_ratio_preview(font_path);guides(assets,shapes,gap);assembly_preview(assets,shapes)
    report=validate(assets,shapes,items,gap)
    (TMP/'placements.json').write_text(json.dumps([{k:v for k,v in p.items() if k!='poly'} for p in items]),encoding='utf-8')
    doc=fitz.open(OUT/'00_REVISION_GUIDE.pdf')
    for i,p in enumerate(doc):p.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(str(TMP/f'guide-{i+1}.png'))
    package(report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
