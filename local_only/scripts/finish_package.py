from pathlib import Path
import sys, json, math, zipfile, shutil, io, hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader
from shapely.geometry import box
sys.path.insert(0,str(ROOT/'scripts'))
from build_goods import shape_assets, affinity, ASSETS
OUT=ROOT/'output/production'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunB','C:/Windows/Fonts/malgunbd.ttf'))
INK='#252525';ACC='#e46c56';MUT='#6b6963'

def text(c,x,y,s,size=10,bold=False,color=INK):
    c.setFillColor(color);c.setFont('MalgunB' if bold else 'Malgun',size);c.drawString(x*mm,y*mm,s)

def lines(c,x,y,items,size=10,leading=6):
    for s in items:text(c,x,y,s,size);y-=leading
    return y

def heading(c,title,sub,page):
    c.setFillColor('#faf7f1');c.rect(0,0,210*mm,297*mm,fill=1,stroke=0)
    text(c,17,279,'DANPUNGBARAM / PRODUCTION KIT',9,True,ACC)
    text(c,17,264,title,23,True)
    text(c,17,253,sub,9,False,MUT)
    c.setStrokeColor('#d5cfc5');c.line(17*mm,246*mm,193*mm,246*mm)
    text(c,17,10,'2026.11.19 목요일 제작 / 실제 크기 100% / 자동 맞춤 해제',8,False,MUT)
    text(c,188,10,str(page),8,False,MUT)

def section(c,y,title,content):
    text(c,17,y,title,13,True);return lines(c,17,y-10,content,9.2,6)-9

def write_guides(stats,assets):
    s500=stats['boards']['500'];s600=stats['boards']['600'];artw=stats['shirt']['art_mm'][0]
    c=canvas.Canvas(str(OUT/'00_PRINT_GUIDE_KO.pdf'),pagesize=(210*mm,297*mm))
    c.setTitle('단풍바람 티셔츠·아크릴 키링 제작 안내')
    heading(c,'이 파일부터 확인하세요','흰색·밝은 티셔츠 / 로고만 / 가람·단팽이·로고 키링',1)
    y=section(c,232,'01  티셔츠 - 70 mm',[
        '01_tshirt / tshirt_logo_70mm_300ppi.png 사용',
        f'투명 PNG 827 × 827 px, 300ppi. 캔버스 70 × 70 mm.',
        f'인쇄되는 심볼은 약 {artw:.1f} × 70.0 mm. 이름 없이 원본 비율을 유지했습니다.',
        '착용자 왼쪽 가슴에 배치합니다. 정면에서 보면 보는 사람의 오른쪽입니다.',
        '위치는 몸판 중앙에서 왼쪽 약 80-100 mm, 목둘레 앞 중앙 아래 약 70-90 mm를',
        '시작점으로 삼고, 실제 티셔츠에 실측 시안을 대어 M/L/XL 모두 확인하세요.',
        '600ppi PNG와 벡터 SVG·AI·PDF도 함께 들어 있습니다. 거울 반전하지 않습니다.'
    ])
    y=section(c,y,'02  아크릴 - 사용할 판 규격 선택',[
        f'02_acrylic_800x500 : 안내문 우선안, 총 {s500["total"]}개',
        f'03_acrylic_800x600 : 요청한 판 전체 배치, 총 {s600["total"]}개',
        '두 폴더는 대안입니다. 같은 판에 둘 다 출력하지 않습니다.',
        '안내문 첫 장은 800 × 500 mm 이내입니다. 레이저 교육 자료는',
        'Speedy 360: 800 × 500 mm / Speedy 400: 1000 × 600 mm로 기재합니다.',
        '800 × 600 판은 해당 장비·지그·클램프 여유를 현장에서 확인한 뒤 사용하세요.',
        '확인이 안 되면 800 × 500 도안을 사용하고 판의 실제 크기도 작업대에 맞춥니다.'
    ])
    y=section(c,y,'03  가져갈 준비물',[
        'USB에 이 폴더 전체를 복사: PNG, 레이어 AI, 커팅 SVG/PDF, 이 안내서.',
        '면 소재의 흰색·밝은 티셔츠와 테스트용 여분 원단, 깨끗하고 평평한 아크릴판.',
        '키링 부자재: 지름 3 mm 구멍에 맞는 연결고리. 실제 재료 두께·고리를 확인합니다.',
        '안내문의 권장 재료 두께는 5 mm 이내입니다. 최종 재료·출력 조건은 담당자 확인.',
        'DTG 전처리·건조·인쇄·후처리는 교육 순서대로 진행하며, 먼저 1개를 시험합니다.'
    ])
    c.showPage()
    heading(c,'UV 인쇄와 커팅을 분리','레이어·색상·실제 크기 확인 순서',2)
    y=section(c,232,'UV 인쇄용',[
        '*_UV_300ppi.png : 300ppi, 투명 배경, 이미지 + 파란 모서리 기준선만 포함.',
        '800 × 500 = 9449 × 5906 px / 800 × 600 = 9449 × 7087 px.',
        '빨간 커팅선은 이 PNG에 없습니다. 기준선은 제품 바깥 여백에만 있습니다.',
        '투명 아크릴 위 백색 잉크는 RIP에서 PNG 알파 기준으로 설정합니다.',
        '가람의 몸처럼 이미지 안의 흰색은 불투명입니다. 백색 잉크 설정을 확인하세요.',
        '기본은 전면 정방향 단면 인쇄입니다. 배면 인쇄나 거울 반전 파일이 아닙니다.'
    ])
    y=section(c,y,'CMYK에 관하여',[
        '안내문은 CMYK PNG를 적고 있지만 PNG는 CMYK 모드를 지원하지 않습니다.',
        '기본 PNG는 sRGB이며 RIP에서 장비 프로파일로 변환합니다.',
        '*_UV_CMYK_300ppi.tif는 ICC 포함 CMYK 대체본입니다. 배경은 불투명 흰색입니다.',
        'TIFF 전체 흰 배경을 백색 잉크 영역으로 자동 지정하면 안 됩니다.',
        'TIFF를 쓸 때에도 백색판은 PNG의 알파에서 만들고 색상 시험 후 사용하세요.',
        '동봉 ICC는 범용 변환용입니다. 장비 전용 ICC가 제공된 것은 아닙니다.'
    ])
    y=section(c,y,'레이저 커팅용',[
        '*_CUT_ONLY.svg 또는 *_CUT_ONLY.pdf : 빨강 #FF0000, 선 두께 0.001 mm.',
        '채움 없음. 제품 1개당 바깥 폐곡선 1개 + 지름 3 mm 구멍 1개입니다.',
        '로고의 점과 떨어진 획은 하나의 투명 아크릴 외곽 안에 연결됩니다.',
        '중앙의 빈 공간은 커팅하지 않습니다. 구멍부터, 외곽선은 나중에 커팅하세요.',
        '절단 폭 보정은 미적용입니다. 재료에 맞는 출력·속도·주파수는 담당자가 설정합니다.',
        '기준선 레이어를 커팅 대상으로 지정하지 마세요. 커팅 전에는 중복 출력도 확인합니다.'
    ])
    y=section(c,y,'편집할 때',[
        '*_MASTER.vectorcraft를 설치된 VectorCraft에서 열면 전체 배치가 나옵니다.',
        '*_MASTER.ai는 VectorCraft에서 실제로 내보낸 PDF 호환 Illustrator 파일입니다.',
        '1_LASER_CUT = 절단선 / 2_REFERENCE = 모서리 기준선 / 3_ARTWORK = 이미지.',
        '3개 레이어를 보존했습니다. 인쇄는 3 + 2, 커팅은 1만 사용합니다.',
        '인쇄와 커팅 파일의 크기·원점·회전을 동일하게 유지하세요. 자동 맞춤은 끕니다.'
    ])
    c.showPage()
    heading(c,'배치·원본·검증 정보','완성 크기와 현장 확인 사항',3)
    text(c,17,231,'캐릭터별 제작 크기',13,True)
    y=219
    shapes=shape_assets(assets)
    labels={'garam':'가람','logo_symbol':'로고','danpaengi':'단팽이'}
    for k in ['garam','logo_symbol','danpaengi']:
        p=shapes[k]['poly'];x0,y0,x1,y1=p.bounds
        text(c,17,y,f'{labels[k]}  그림 높이 {assets[k]["h"]:.0f} mm / 아크릴 외곽 약 {x1-x0:.1f} × {y1-y0:.1f} mm',10)
        y-=8
    y=section(c,189,'판별 수량과 간격',[
        f'800 × 500 : 가람 {s500["counts"]["garam"]} / 로고 {s500["counts"]["logo_symbol"]} / 단팽이 {s500["counts"]["danpaengi"]} = {s500["total"]}개',
        f'800 × 600 : 가람 {s600["counts"]["garam"]} / 로고 {s600["counts"]["logo_symbol"]} / 단팽이 {s600["counts"]["danpaengi"]} = {s600["total"]}개',
        f'외곽 간 최소 간격: {s500["min_gap_mm"]:.2f} mm / {s600["min_gap_mm"]:.2f} mm. 그림 밖 투명 여백 약 1.8 mm.',
        '판 가장자리 8 mm를 예약하고 모서리 기준선은 3 mm 위치에 뒀습니다.',
        f'제품 외곽 면적 기준 판 사용률: {s500["material_utilization"]*100:.1f}% / {s600["material_utilization"]*100:.1f}%.',
        '불규칙 외곽을 회전해 촘촘히 배치한 결과이며, 수학적인 최적 배치를 보장하지 않습니다.'
    ])
    y=section(c,y,'원본과 재구성 범위',[
        '로고: DBPR_LOGO 안의 배포용 AI에서 이름 없는 7개 벡터 경로를 추출했습니다.',
        '마스코트: 제공된 노션의 카드뉴스 첫 장을 참고해 가람·단팽이를 수작업 벡터화했습니다.',
        '마스코트 원본 벡터가 제공된 것은 아닙니다. 미세한 선·색·표정은 차이가 있습니다.',
        '카드 배경·문구와 가람 왼쪽의 작은 동작선은 제외했습니다.',
        '인쇄 전에 05_preview의 캐릭터 비교 그림과 배치 시안을 확인하세요.',
        '원본 노션 주소 및 출처는 SOURCES.txt에, 검증 결과는 validation_report.json에 있습니다.'
    ])
    y=section(c,y,'파일 검증',[
        'AI 재열기 경고 없음, 레이어 3개 보존, 외부 연결 이미지·글꼴 의존 없음.',
        '판 크기, 인쇄 PNG 픽셀·ppi·알파, CMYK TIFF 모드·ICC, 커팅 폐곡선 수를 검사했습니다.',
        '각 외곽과 구멍의 교차·중복·판 밖 배치 및 제품 사이 실제 벡터 간격을 검사했습니다.',
        '실제 인쇄·실제 장비 커팅 시험은 아직 하지 않았습니다. 시험 출력 후 전체 제작하세요.'
    ])
    c.save()
    # Printable 1:1 placement reference.
    c=canvas.Canvas(str(OUT/'01_tshirt/tshirt_70mm_A4_ACTUAL_SIZE.pdf'),pagesize=(210*mm,297*mm))
    text(c,18,277,'왼쪽 가슴 로고 - 실측 확인용',20,True)
    lines(c,18,264,['A4 용지에 실제 크기 100%로 출력하세요. 페이지에 맞춤은 끕니다.',
                      '회색 사각형을 잘라 티셔츠에 대어 보고 위치를 정합니다.',
                      '이 안내 용지를 티셔츠 인쇄용으로 사용하지 마세요.'],10,7)
    c.setStrokeColor('#aaa8a2');c.setDash(2,2);c.rect(70*mm,137*mm,70*mm,70*mm,fill=0,stroke=1);c.setDash()
    c.drawImage(str(OUT/'01_tshirt/tshirt_logo_70mm_600ppi.png'),70*mm,137*mm,width=70*mm,height=70*mm,mask='auto')
    text(c,73,127,'70 × 70 mm / 원본 비율 유지',10,True)
    text(c,18,103,'100 mm 확인자: 아래 선을 자로 재세요.',10,True)
    c.setStrokeColor(INK);c.line(25*mm,90*mm,125*mm,90*mm)
    for i in range(11):
        x=25+i*10;c.line(x*mm,90*mm,x*mm,(94 if i%5==0 else 92)*mm)
        text(c,x-1,83,str(i*10),7)
    lines(c,18,63,['착용자 왼쪽 = 정면으로 볼 때 오른쪽 가슴.',
                     '몸판 중앙에서 왼쪽 약 80-100 mm, 앞 목둘레 아래 약 70-90 mm를',
                     '출발점으로 잡고 티셔츠 실물·체형·사이즈에 맞춰 조정합니다.'],10,7)
    c.save()

def source_comparison():
    # Contact sheet is a QA artifact; no edited raster is used as artwork.
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
    im=Image.new('RGB',(1400,680),'#faf7f1');d=ImageDraw.Draw(im)
    src=Image.open(ROOT/'tmp/sources/mascot_01.png')
    refs=[src.crop((545,575,866,938)),src.crop((880,790,1042,932))]
    names=['garam','danpaengi']
    for i in range(2):
        ref=refs[i];ref.thumbnail((290,480));x=25+i*700;y=90
        im.paste(ref,(x,y));d.text((x,25),'카드뉴스 원본',font=font,fill=INK)
        art=Image.open(ASSETS/f'{names[i]}_preview.png').convert('RGBA');art.thumbnail((290,480))
        im.paste(art,(x+340,y),art);d.text((x+340,25),'제작용 벡터 재구성',font=font,fill=INK)
    d.text((25,615),'원본 AI가 없는 마스코트는 수작업 벡터 재구성본입니다. 제작 전 외형을 확인하세요.',font=font,fill=INK)
    im.save(OUT/'05_preview/mascot_source_comparison.png')

def validate(stats,assets):
    report={'checks':[],'warnings':['Mascots are manually reconstructed vectors; not original mascot AI.','800x600 requires confirmation of machine/table/fixture capacity.','CMYK TIFF is opaque; use PNG alpha for white underbase.','Physical print/cut test not performed.']}
    shapes=shape_assets(assets)
    for H,f in [(500,'02_acrylic_800x500'),(600,'03_acrylic_800x600')]:
        folder=OUT/f;stem=f'acrylic_800x{H}';s=stats['boards'][str(H)]
        r=PdfReader(folder/f'{stem}_MASTER.ai');page=r.pages[0]
        dims=[float(page.mediabox.width)*25.4/72,float(page.mediabox.height)*25.4/72]
        assert abs(dims[0]-800)<.01 and abs(dims[1]-H)<.01
        oc=r.trailer['/Root']['/OCProperties'];names=[x.get_object()['/Name'] for x in oc['/OCGs']]
        assert names==['3_ARTWORK','2_REFERENCE','1_LASER_CUT']
        png=Image.open(folder/f'{stem}_UV_300ppi.png');assert png.mode=='RGBA'
        assert png.size==(9449,5906 if H==500 else 7087)
        assert abs(png.info.get('dpi',(0,))[0]-300)<.1
        assert png.getchannel('A').getextrema()==(0,255)
        tif=Image.open(folder/f'{stem}_UV_CMYK_300ppi.tif');assert tif.mode=='CMYK' and tif.info.get('icc_profile')
        cut=fitz.open(folder/f'{stem}_CUT_ONLY.pdf');paths=cut[0].get_drawings()
        assert len(paths)==s['total']*2,(len(paths),s['total'])
        assert all(p['fill'] is None and abs(p['width']-0.001*72/25.4)<.0001 for p in paths)
        # MuPDF normalizes closepath into an explicit closing segment here.
        # Check both the underlying PDF operator and the resulting endpoints.
        cut_reader=PdfReader(folder/f'{stem}_CUT_ONLY.pdf')
        ops=cut_reader.pages[0].get_contents().operations
        assert sum(op==b'h' for _,op in ops)==len(paths)
        assert all(p['color']==(1.,0.,0.) and abs(p['items'][0][1]-p['items'][-1][-1])<.0001 for p in paths)
        data=json.loads((folder/'layout_manifest.json').read_text());polys=[]
        for p in data['placements']:
            sh=shapes[p['name']];poly=affinity.translate(affinity.rotate(sh['poly'],p['angle'],origin=(0,0)),p['tx'],p['ty'])
            assert box(0,0,800,H).contains(poly)
            assert sh['poly'].is_valid
            polys.append(poly)
        dist=min(a.distance(b) for i,a in enumerate(polys) for b in polys[:i]);assert dist>=3
        report['checks'].append({'board_mm':dims,'layers':names,'piece_count':s['total'],'closed_cut_paths':len(paths),'min_gap_mm':dist,'png_px':png.size,'png_dpi':png.info['dpi'],'png_has_transparency':True,'cmyk_tiff_icc':True})
    shirt=Image.open(OUT/'01_tshirt/tshirt_logo_70mm_300ppi.png');assert shirt.size==(827,827) and shirt.mode=='RGBA'
    report['checks'].append({'shirt_png_px':shirt.size,'shirt_dpi':shirt.info['dpi'],'shirt_alpha':shirt.getchannel('A').getextrema()})
    (OUT/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    stats=json.loads((OUT/'production_summary.json').read_text(encoding='utf-8'))
    assets=json.loads((ROOT/'tmp/artwork.json').read_text(encoding='utf-8'))
    write_guides(stats,assets);source_comparison();report=validate(stats,assets)
    for p in [OUT/'00_PRINT_GUIDE_KO.pdf',OUT/'01_tshirt/tshirt_70mm_A4_ACTUAL_SIZE.pdf']:
        doc=fitz.open(p)
        for i,page in enumerate(doc):page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(str(ROOT/f'tmp/pdfs/{p.stem}-{i+1}.png'))
    sources='''Sources and preparation notes\n\nUser supplied guide: E:/OneDrive - gc.gachon.ac.kr/문서/카카오톡 받은 파일/2026-11-16_scan_QuickScanApp.com.pdf\nLogo: DBPR_LOGO/1. logo/단바로고배포용.ai (7 original symbol paths, wordmark excluded)\nMascots: https://ark1st.notion.site/4199cd9d18388078b431c5573819102d\nCard: image block 4199cd9d-1838-804c-92f8-e348452f533b (1080x1080)\nGaram and Danpaengi artwork is a manual vector reconstruction from the card, not original mascot AI.\nVectorCraft installed version 0.24.1 used for real .ai/.vectorcraft exports and 300ppi raster exports.\nOfficial docs: https://github.com/storytold/vectorcraft/blob/main/docs/mcp.md\nProduction date: 2026-11-19 (Thursday), Asia/Seoul.\nNo white-ink spot plate is encoded. Generate from the transparent PRINT PNG alpha in the equipment RIP.\nCMYK TIFF includes a generic ICC and has an opaque white background; it is an optional color-conversion fallback.\n'''
    (OUT/'SOURCES.txt').write_text(sources,encoding='utf-8-sig')
    readme=f'''단풍바람 제작 파일 / 2026-11-19 목요일\n\n먼저 00_PRINT_GUIDE_KO.pdf를 확인하세요.\n\n티셔츠: 01_tshirt/tshirt_logo_70mm_300ppi.png (70x70mm, 투명 PNG)\n아크릴 기본: 02_acrylic_800x500 (총 {stats['boards']['500']['total']}개)\n아크릴 큰 판: 03_acrylic_800x600 (총 {stats['boards']['600']['total']}개, 장비 확인 후 사용)\n\nUV 인쇄: *_UV_300ppi.png (기준선 포함, 커팅선 제외)\n커팅: *_CUT_ONLY.svg 또는 PDF (빨강 #FF0000 / 0.001mm)\n편집: *_MASTER.vectorcraft 또는 *_MASTER.ai (레이어 3개)\n\n인쇄/커팅 크기와 원점 동일, 실제 크기 100%, 자동 맞춤 해제.\nPNG는 sRGB. CMYK TIFF는 불투명 배경이므로 백색판은 PNG 알파에서 생성.\n마스코트는 원본 카드뉴스를 참고한 수작업 벡터 재구성본입니다.\n05_preview에서 외형과 배치를 확인하고 1개 시험 후 전체 제작하세요.\n'''
    (OUT/'00_START_HERE.txt').write_text(readme,encoding='utf-8-sig')
    print(json.dumps(report,ensure_ascii=False,indent=2))
