"""Generate the approved 70 mm logo-only left-chest print assets."""
from pathlib import Path
import sys, json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from vector_utils import runvc,svg_doc,layer

OUT=ROOT/'output/tshirt'
TMP=ROOT/'tmp/tshirt'


def main():
    OUT.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
    a=json.loads((ROOT/'assets/artwork.json').read_text(encoding='utf-8'))['solo_logo']
    scale=70/a['h'];width=a['w']*scale
    art=f'<g transform="translate({(70-width)/2:.8f} 0) scale({scale:.8f})">{a["inner"]}</g>'
    svg=OUT/'tshirt_logo_70mm.svg'
    svg.write_text(svg_doc(70,70,layer('LOGO_ONLY',art),'Left-chest logo - 70 mm'),encoding='utf-8')
    runvc(['convert',svg,OUT/'tshirt_logo_70mm.ai'])
    runvc(['convert',svg,OUT/'tshirt_logo_70mm.pdf'])
    commands=[{'command':'document.export','params':{
        'path':str(OUT/f'tshirt_logo_70mm_{ppi}ppi.png'),'format':'png','ppi':ppi,
        'background':'transparent','includeArtboardFill':False}} for ppi in [300,600]]
    cmd=TMP/'export.json';cmd.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',svg,'--commands',cmd])

    pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
    pdfmetrics.registerFont(TTFont('MalgunB','C:/Windows/Fonts/malgunbd.ttf'))
    c=canvas.Canvas(str(OUT/'tshirt_70mm_A4_ACTUAL_SIZE.pdf'),pagesize=(210*mm,297*mm))
    c.setTitle('단풍바람 티셔츠 로고 - A4 실물 크기 확인')
    def text(x,y,s,size=10,bold=False):
        c.setFont('MalgunB' if bold else 'Malgun',size);c.drawString(x*mm,y*mm,s)
    text(20,272,'단풍바람 / 왼쪽 가슴 로고',20,True)
    text(20,256,'흰색 또는 밝은 티셔츠용 · 이름 없는 로고 · 높이 70 mm')
    text(20,246,'A4 용지에 실제 크기 100%로 출력한 뒤 가슴에 대어 위치를 확인하세요.')
    c.drawImage(str(OUT/'tshirt_logo_70mm_600ppi.png'),70*mm,150*mm,width=70*mm,height=70*mm,mask='auto')
    c.setStrokeColorRGB(.7,.7,.7);c.setDash(2,3);c.rect(70*mm,150*mm,70*mm,70*mm)
    c.setDash();c.setStrokeColorRGB(0,0,0)
    text(63,138,f'캔버스 70 × 70 mm / 그림 약 {width:.1f} × 70 mm',9)
    text(20,112,'전사용 파일: tshirt_logo_70mm_300ppi.png 또는 AI/PDF',10,True)
    text(20,101,'이 A4 시안의 글자·점선·확인자는 티셔츠에 인쇄하지 않습니다.',9)
    text(20,92,'전사 장비의 반전 여부는 현장 작업 방식에 맞게 설정합니다.',9)
    c.line(30*mm,65*mm,130*mm,65*mm)
    for i in range(11):
        x=30+i*10;c.line(x*mm,65*mm,x*mm,(70 if i%5==0 else 68)*mm)
        text(x-1,58,str(i*10),7)
    text(30,46,'100 mm 확인자 — 실제 자로 길이를 확인하세요.',9)
    c.save()

    for ppi,expected in [(300,(827,827)),(600,(1654,1654))]:
        im=Image.open(OUT/f'tshirt_logo_70mm_{ppi}ppi.png')
        assert im.size==expected and im.mode=='RGBA'
        assert abs(im.info['dpi'][0]-ppi)<.1
        assert im.getpixel((0,0))[3]==0
    page=PdfReader(OUT/'tshirt_logo_70mm.pdf').pages[0]
    assert all(abs(float(v)*25.4/72-70)<.01 for v in [page.mediabox.width,page.mediabox.height])
    (OUT/'README.txt').write_text('흰색/밝은색 티셔츠의 왼쪽 가슴용 로고입니다. 이름 없음.\n'
        '캔버스 70×70mm, 로고 높이 70mm. PNG는 투명 배경, 실제 크기 100%.\n'
        'A4_ACTUAL_SIZE.pdf는 위치와 크기 확인용입니다.\n',encoding='utf-8-sig')
    print('T-shirt assets verified:',OUT,flush=True)


if __name__=='__main__':
    main()
