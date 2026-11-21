"""Small-batch revision: 3 sets + 3 standalone logos (12 acrylic pieces).
Vector artwork, mm geometry, explicit print/reference/cut layers.
"""
from pathlib import Path
import sys, json, math, copy, zipfile, re
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from build_goods import runvc,svg_doc,path,ellipse,poly_path,layer

OUT=ROOT/'output/production_v2'
TMP=ROOT/'tmp/v2'
AS=OUT/'assets'
W,H=320,180
SOURCE_RATIO=135/356

def render(svg,png,scale=6):
    dest=TMP/(svg.stem+'.pdf')
    runvc(['convert',svg,dest])
    doc=fitz.open(dest);doc[0].get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=True).save(str(png))
    return dest

def new_snail():
    # The body lies behind the continuous orange shell. No grey patch, triangle,
    # duplicate diagonal line, or broken boundary between shell and body.
    k='#171717';orange='#f69c77'
    q=[]
    q.append(path('M894 830 L893 824 M920 825 L922 819','none',k,4))
    q.append(path('M888 919 C884 905 884 875 888 850 C891 834 901 826 912 827 C925 827 936 840 945 855 L961 880 C974 891 990 896 1001 894 C1013 891 1019 903 1011 913 C1005 924 981 925 958 925 L908 924 C898 924 891 923 888 919 Z','#ffffff',k,4.5))
    q.append(path('M933 832 C940 809 958 793 979 796 C1008 799 1031 824 1036 849 C1042 874 1027 891 1004 895 C986 899 968 892 961 882 C955 873 950 860 944 849 C940 842 937 837 933 832 Z',orange,k,4.5))
    q.append(path('M962 881 C956 873 959 859 967 850 C973 842 985 845 992 853 C1002 863 995 873 985 874','none',k,4.5))
    q.extend([ellipse(899,848,3.2,3.7,k),ellipse(920,846,3.2,3.7,k),ellipse(894,855,4.5,4,'#ffd3c2'),ellipse(928,853,4.5,4,'#ffd3c2')])
    q.append(path('M904 852 C908 850 913 851 916 852 C916 860 906 864 904 856 Z','#ae4a50',k,3))
    return {'w':164,'h':143,'inner':f'<g transform="translate(-880 -790)">{"".join(q)}</g>'}

def normalize(name,a,target_h):
    # Tight, measured alpha bounds keep the requested visible-art height exact.
    test=TMP/f'{name}_raw.svg';test.write_text(svg_doc(a['w'],a['h'],a['inner']),encoding='utf-8')
    rawpng=TMP/f'{name}_raw.png';render(test,rawpng,2 if a['h']>100 else 6)
    im=Image.open(rawpng).convert('RGBA');bb=im.getchannel('A').getbbox()
    x0,y0,x1,y1=bb
    x0=x0*a['w']/im.width;y0=y0*a['h']/im.height
    width=(x1-bb[0])*a['w']/im.width;height=(y1-bb[1])*a['h']/im.height
    s=target_h/height
    result={'w':width*s,'h':target_h,'inner':f'<g transform="scale({s:.10f}) translate({-x0:.10f} {-y0:.10f})">{a["inner"]}</g>'}
    svg=AS/f'{name}.svg';svg.write_text(svg_doc(result['w'],target_h,result['inner']),encoding='utf-8')
    render(svg,AS/f'{name}.png',8)
    return result

def artwork():
    old=json.loads((ROOT/'tmp/artwork.json').read_text(encoding='utf-8'))
    assets={
        'garam':normalize('garam',old['garam'],55),
        'danpaengi':normalize('danpaengi',new_snail(),55*SOURCE_RATIO),
        'mini_logo':normalize('mini_logo',old['logo_symbol'],18),
        'solo_logo':normalize('solo_logo',old['logo_symbol'],30),
    }
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
        body=carrier.buffer(3.6,quad_segs=24)
        if body.geom_type!='Polygon':body=concave_hull(body,ratio=.5)
        body=Polygon(body.exterior)
        cs=np.array(art.convex_hull.exterior.coords);top=cs[cs[:,1]<cs[:,1].min()+.2]
        hx=float(np.mean(top[:,0]));hy=float(art.bounds[1]-7.1)
        tab=Point(hx,hy).buffer(6.2,quad_segs=40)
        neck=box(hx-5.2,hy,hx+5.2,art.bounds[1]+1.5)
        outer=unary_union([body,tab,neck]).buffer(.7,quad_segs=12).buffer(-.7,quad_segs=12).simplify(.025,preserve_topology=True)
        assert outer.geom_type=='Polygon'
        outer=Polygon(outer.exterior)
        hole=Point(hx,hy).buffer(2,quad_segs=64)
        assert outer.contains(art) and outer.contains(hole)
        clearance=outer.boundary.distance(art)
        hole_art=hole.distance(art);hole_edge=outer.boundary.distance(hole)
        assert clearance>=3.5,(name,clearance)
        assert hole_art>=5,(name,hole_art)
        assert hole_edge>=4,(name,hole_edge)
        shapes[name]={'poly':outer,'hole':(hx,hy),'art':art,'clearance':clearance,'hole_art':hole_art,'hole_edge':hole_edge}
    return shapes

def at(name,x,y,shapes,ident):
    p=shapes[name]['poly'];bx,by,_,_=p.bounds
    tx=x-bx;ty=y-by
    return {'name':name,'tx':tx,'ty':ty,'poly':affinity.translate(p,tx,ty),'id':ident}

def place(shapes):
    items=[]
    for i in range(3):
        x=12+i*100
        items.extend([at('garam',x,13,shapes,f'set{i+1}_garam'),
                      at('mini_logo',x+63,13,shapes,f'set{i+1}_mini_logo'),
                      at('danpaengi',x+63,56,shapes,f'set{i+1}_danpaengi')])
    for i in range(3):items.append(at('solo_logo',32+i*100,115,shapes,f'solo_logo_{i+1}'))
    for p in items:assert box(9,9,W-9,H-9).contains(p['poly']),p['id']
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
        outlines.append(f'<g transform="{t}">{path(poly_path(s["poly"]),"none","#ff0000",sw)}</g>')
    # Match the guide's continuous blue rectangle. It encloses the common work
    # area; no per-character rectangle and no blue strokes in CUT_ONLY.
    x=4+shift[0];y=4+shift[1]
    reference=f'<rect x="{x}" y="{y}" width="{W-8}" height="{H-8}" fill="none" stroke="#0000ff" stroke-width="0.3"/>'
    return layer('3_ARTWORK',''.join(arts)),layer('2_CORNER_REFERENCE',reference),layer('1_LASER_CUT',''.join(holes+outlines))

def cut_pdf(items,shapes):
    c=canvas.Canvas(str(OUT/'04_CUT_ONLY.pdf'),pagesize=(W*mm,H*mm));c.setTitle('V2 Small batch - laser cut only 320 x 180 mm')
    c.transform(mm,0,0,-mm,0,H*mm);c.setStrokeColorRGB(1,0,0);c.setLineWidth(.001)
    for p in items:
        hx,hy=shapes[p['name']]['hole'];hx+=p['tx'];hy+=p['ty']
        d=c.beginPath();d.ellipse(hx-2,hy-2,4,4);d.close();c.drawPath(d,stroke=1,fill=0)
    for p in items:
        coords=list(p['poly'].exterior.coords);d=c.beginPath();d.moveTo(*coords[0])
        for pt in coords[1:-1]:d.lineTo(*pt)
        d.close();c.drawPath(d,stroke=1,fill=0)
    c.save()

def files(assets,shapes,items):
    ar,ref,cut=make_layers(assets,shapes,items,W,H)
    master=OUT/'02_MASTER.svg';master.write_text(svg_doc(W,H,ar+ref+cut,'V2 12 pieces - 320 x 180 mm'),encoding='utf-8')
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
    rv=OUT/'preview/board_layout.svg';rv.write_text(svg_doc(W,H,'<rect width="320" height="180" fill="white"/>'+ar+ref+cut),encoding='utf-8')
    render(rv,OUT/'preview/board_layout.png',1.7)
    # Optional full-sheet coordinates contain THE SAME twelve pieces only.
    ar,ref,cut=make_layers(assets,shapes,items,800,600,shift=(15,15))
    folder=OUT/'optional_800x600'
    for name,content in [('MASTER',ar+ref+cut),('PRINT',ar+ref),('CUT_ONLY',cut)]:
        (folder/f'800x600_SAME_12_{name}.svg').write_text(svg_doc(800,600,content),encoding='utf-8')
    runvc(['convert',folder/'800x600_SAME_12_MASTER.svg',folder/'800x600_SAME_12_MASTER.vectorcraft'])
    runvc(['convert',folder/'800x600_SAME_12_MASTER.svg',folder/'800x600_SAME_12_MASTER.ai'])
    commands=[{'command':'document.export','params':{'path':str(folder/'800x600_SAME_12_PRINT_300ppi.png'),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}}]
    cmd=TMP/'export-fullsheet.json';cmd.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',folder/'800x600_SAME_12_PRINT.svg','--commands',cmd])
    cut_pdf(items,shapes)

def single_keyring(name,assets,shapes):
    a=assets[name];s=shapes[name];p=s['poly'];x0,y0,x1,y1=p.bounds
    hx,hy=s['hole'];margin=2
    inner=f'<g transform="translate({margin-x0} {margin-y0})">'+a['inner']+path(poly_path(p),'none','#ff0000',.22)+f'<circle cx="{hx}" cy="{hy}" r="2" fill="none" stroke="#ff0000" stroke-width="0.22"/></g>'
    svg=OUT/f'preview/{name}_keyring.svg';svg.write_text(svg_doc(x1-x0+4,y1-y0+4,inner),encoding='utf-8')
    render(svg,OUT/f'preview/{name}_keyring.png',4)
    return x1-x0+4,y1-y0+4

def source_ratio_preview():
    im=Image.open(ROOT/'tmp/sources/mascot_01.png').convert('RGB')
    crop=im.crop((525,565,1055,945)).resize((1060,760))
    d=ImageDraw.Draw(crop);font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',24)
    for label,(x,y,w,h),color in [('가람 356px',(551,579,311,356),'#195aac'),('단팽이 135px',(884,794,155,135),'#ba4242')]:
        x=(x-525)*2;y=(y-565)*2;w*=2;h*=2
        d.rectangle((x,y,x+w,y+h),outline=color,width=3)
        d.text((x,y-25 if y>=25 else y+5),label,font=font,fill=color,stroke_width=1,stroke_fill='white')
    crop.save(OUT/'preview/source_ratio_evidence.png')

def label(c,x,y,s,size=10,bold=False,color='#252525'):
    c.setFillColor(color);c.setFont('MalgunB' if bold else 'Malgun',size);c.drawString(x*mm,y*mm,s)

def guides(assets,shapes,gap):
    pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
    pdfmetrics.registerFont(TTFont('MalgunB','C:/Windows/Fonts/malgunbd.ttf'))
    c=canvas.Canvas(str(OUT/'00_REVISION_GUIDE.pdf'),pagesize=(210*mm,297*mm));c.setTitle('단풍바람 키링 수정본 V2 - 소량 제작 12조각')
    def page(title,sub,n):
        c.setFillColor('#faf8f3');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
        label(c,17,279,'DANPUNGBARAM / REVISION 02',9,True,'#d46850')
        label(c,17,264,title,22,True);label(c,17,252,sub,9,color='#666666')
        c.setStrokeColor('#d7d1c7');c.line(17*mm,245*mm,193*mm,245*mm)
        label(c,17,10,'2026.11.17 수정 / 11.19 목요일 제작 / 실제 크기 100%',8,color='#666666');label(c,190,10,str(n),8)
    def section(y,title,rows):
        label(c,17,y,title,12,True);y-=10
        for row in rows:label(c,17,y,row,9.4);y-=6.2
        return y-9
    page('수량과 크기를 다시 잡았습니다','3세트 + 로고 단독 3개 = 총 12조각',1)
    y=section(231,'이번 제작 수량',[
        '한 세트: 가람 1개 + 작은 단팽이 1개 + 미니 로고 1개. 세 세트입니다.',
        '로고만 달 수 있는 단독 키링은 3개를 추가했습니다.',
        '작업영역 320 × 180 mm에만 모았습니다. 남은 아크릴판은 넓게 남깁니다.',
        '기본 파일과 optional_800x600 파일은 같은 12조각입니다. 둘 다 찍지 마세요.'
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
        '그림과 재단 외곽: 최소 3.5 mm. 이전 약 1.8 mm보다 넓혔습니다.',
        '구멍 지름: 4 mm. 그림 위로 별도의 둥근 고리 부분을 올렸습니다.',
        '구멍 가장자리와 그림: 최소 5 mm.',
        '구멍 가장자리와 아크릴 외곽: 최소 4 mm. 목 부분 폭은 약 10.4 mm입니다.',
        f'배치된 조각끼리 외곽 간격은 최소 {gap:.2f} mm입니다.',
        '완성 외곽: 가람 약 55.2 × 71.8 mm / 단팽이 약 31.6 × 37.7 mm.',
        '미니 로고 약 23.4 × 34.8 mm / 단독 로고 약 34.2 × 46.9 mm.'
    ])
    c.drawImage(str(OUT/'preview/board_layout.png'),55*mm,19*mm,width=100*mm,height=56.25*mm,mask='auto')
    # Overview sits in a reserved bottom area; the text layout is kept above it.
    c.showPage()
    page('모서리 기준선은 이렇게 씁니다','파란색 = 위치 기준 / 빨간색 = 레이저 재단 / 그림 = UV 인쇄',2)
    y=section(231,'설명서 예시대로 파란 사각형을 포함',[
        '설명서 1쪽의 파란 사각 모서리 기준선을 연속된 사각형으로 넣었습니다.',
        '기본 캔버스 320 × 180 mm, 기준 사각형은 (4, 4)에서 312 × 172 mm입니다.',
        '선 색 #0000FF, 두께 0.3 mm. 인쇄 PNG와 AI에서 좌표가 같습니다.',
        '인쇄와 커팅 위치·방향을 같은 원점에 맞추고, 크기 변형 여부를 확인하는 표식입니다.',
        '자동 인식용 마크라고 가정하면 안 됩니다. 실제 정합 방법은 현장 장비에 따릅니다.',
        '파란 사각형은 자르는 선이 아닙니다. 레이저 출력 대상에서 제외하세요.'
    ])
    y=section(y,'기본 파일 - 이 순서로 사용',[
        '01_PRINT_300ppi.png: 투명 PNG 3780 × 2126 px, 파란 기준선 + 그림.',
        '02_MASTER.ai / 03_MASTER.vectorcraft: 레이어 3개를 보존한 편집 원본.',
        '1_LASER_CUT = 빨간 절단선 / 2_CORNER_REFERENCE = 파란 기준선.',
        '3_ARTWORK = 그림. UV 인쇄할 때는 2 + 3만 켭니다.',
        '04_CUT_ONLY.svg 또는 PDF: 빨간 #FF0000, 0.001 mm, 채움 없음.',
        '24개 폐곡선: 외곽 12개 + 구멍 12개. 구멍부터, 외곽은 나중에 자릅니다.',
        '커팅 전용 파일에서는 파란 기준선을 제외했습니다. 원점과 캔버스 크기는 같습니다.'
    ])
    y=section(y,'판·색상·현장 설정',[
        '기본 작업영역은 설명서의 800 × 500 mm 제한 안에 들어갑니다.',
        '800 × 600 판 전체 좌표가 필요하면 optional_800x600 폴더를 사용하세요.',
        '그 파일은 같은 12조각을 좌상단에서 15 mm 이동해 배치한 대안입니다.',
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
    report={'revision':2,'quantity':12,'set_count':3,'standalone_logos':3,'canvas_mm':[W,H],
        'source_measurement':{'garam_bbox_px':[551,579,311,356],'danpaengi_bbox_px':[884,794,155,135],'height_ratio':SOURCE_RATIO},
        'min_piece_gap_mm':gap,'hole_diameter_mm':4,'assets':{}}
    for name,a in assets.items():
        s=shapes[name];x0,y0,x1,y1=s['poly'].bounds
        report['assets'][name]={'art_mm':[a['w'],a['h']],'acrylic_mm':[x1-x0,y1-y0],'art_to_cut_mm':s['clearance'],'hole_to_art_mm':s['hole_art'],'hole_to_edge_mm':s['hole_edge']}
    assert abs(assets['danpaengi']['h']/assets['garam']['h']-SOURCE_RATIO)<1e-8
    assert '#e5e5e5' not in assets['danpaengi']['inner']
    png=Image.open(OUT/'01_PRINT_300ppi.png');assert png.mode=='RGBA' and png.size==(3780,2126)
    assert abs(png.info['dpi'][0]-300)<.1
    arr=np.array(png);blue=(arr[:,:,2]>240)&(arr[:,:,0]<20)&(arr[:,:,1]<20)&(arr[:,:,3]>150)
    # Check the middle of each side, away from any artwork.
    ratio=300/25.4
    for x,y in [(160,4),(160,176),(4,90),(316,90)]:
        xx=round(x*ratio);yy=round(y*ratio);assert blue[yy-3:yy+4,xx-3:xx+4].any(),(x,y)
    reader=PdfReader(OUT/'02_MASTER.ai');names=[r.get_object()['/Name'] for r in reader.trailer['/Root']['/OCProperties']['/OCGs']]
    assert names==['3_ARTWORK','2_CORNER_REFERENCE','1_LASER_CUT']
    dims=[float(reader.pages[0].mediabox.width)*25.4/72,float(reader.pages[0].mediabox.height)*25.4/72]
    assert max(abs(dims[0]-W),abs(dims[1]-H))<.01
    cut=PdfReader(OUT/'04_CUT_ONLY.pdf');ops=cut.pages[0].get_contents().operations
    assert sum(o==b'h' for _,o in ops)==24
    doc=fitz.open(OUT/'04_CUT_ONLY.pdf');paths=doc[0].get_drawings();assert len(paths)==24
    assert all(p['color']==(1,0,0) and p['fill'] is None and abs(p['width']-.001*72/25.4)<1e-5 for p in paths)
    report['checks']={'quantity':12,'closed_cut_paths':24,'ai_layers':names,'png_pixels':list(png.size),'png_ppi':png.info['dpi'],'blue_reference_four_sides':True,'physical_print_cut_test':False}
    (OUT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def package(report):
    readme='''단풍바람 아크릴 수정본 V2 / 2026-11-17

확정 수량: 3세트 + 로고 단독 3개 = 총 12조각.
세트 1개 = 가람 1 + 단팽이 1 + 미니 로고 1.

먼저 00_REVISION_GUIDE.pdf, preview/board_layout.png를 확인하세요.
기본 작업영역은 320x180mm입니다. 안내문의 800x500mm 제한 이내입니다.
큰 아크릴판의 일부만 사용하고 나머지 판은 보존할 수 있습니다.

UV 인쇄: 01_PRINT_300ppi.png (파란 사각 기준선 포함, 빨간 커팅선 제외)
편집: 02_MASTER.ai 또는 03_MASTER.vectorcraft (레이어 3개)
커팅: 04_CUT_ONLY.svg 또는 PDF (빨강 #FF0000, 0.001mm, 24개 폐곡선)
인쇄와 커팅 모두 실제 크기 100%, 같은 원점, 자동 맞춤 해제.

optional_800x600은 같은 12조각을 800x600mm 좌표에 배치한 대안입니다.
기본 파일과 추가 파일을 둘 다 출력하지 마세요. 큰 판 사용 가능 장비인지 확인하세요.

그림 높이: 가람55mm / 단팽이20.86mm / 미니로고18mm / 단독로고30mm.
구멍4mm, 구멍-그림5mm 이상, 구멍-외곽4mm 이상, 그림-재단선3.5mm 이상.
마스코트는 원본 카드뉴스 참고 벡터 재구성본, 로고는 원본AI 심볼입니다.
티셔츠 파일 수정 요청은 없어서 이번 ZIP은 수정된 아크릴 파일만 담았습니다.
'''
    (OUT/'00_START_HERE.txt').write_text(readme,encoding='utf-8-sig')
    sources='''Sources
Maker-space guide: user-supplied 2026-11-16_scan_QuickScanApp.com.pdf, page 1.
Notion: https://ark1st.notion.site/4199cd9d18388078b431c5573819102d
Ratio measurement: original mascot_01.png card, not separate profile thumbnails.
Garam dark outline bbox 311x356px; Danpaengi dark outline bbox 155x135px.
Pixel outlines are approximate visual measurements, not original character model-sheet dimensions.
User supplied keyring sketch: 2026-11-17, used for the smaller secondary-logo relationship.
Logo: DBPR_LOGO/1. logo/단바로고배포용.ai, 7 original symbol paths.
VectorCraft export: genuine PDF-compatible AI, native VectorCraft, RGB PNG.
'''
    (OUT/'SOURCES.txt').write_text(sources,encoding='utf-8')
    zpath=ROOT/'output/Danpungbaram_V2_SMALL_BATCH_12pcs.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,Path('Danpungbaram_V2')/p.relative_to(OUT))
    with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
    print('ZIP',zpath,zpath.stat().st_size,flush=True)

if __name__=='__main__':
    assets=artwork();shapes=geometry(assets);items,gap=place(shapes)
    print('geometry',json.dumps({k:{'size':v['poly'].bounds,'art_cut':v['clearance'],'hole_art':v['hole_art'],'hole_edge':v['hole_edge']} for k,v in shapes.items()}),flush=True)
    files(assets,shapes,items);source_ratio_preview();guides(assets,shapes,gap);assembly_preview(assets,shapes)
    report=validate(assets,shapes,items,gap)
    (TMP/'placements.json').write_text(json.dumps([{k:v for k,v in p.items() if k!='poly'} for p in items]),encoding='utf-8')
    doc=fitz.open(OUT/'00_REVISION_GUIDE.pdf')
    for i,p in enumerate(doc):p.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(str(TMP/f'guide-{i+1}.png'))
    package(report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
