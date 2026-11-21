"""Large DTG fronts. Preserve Changseop source pixels; no generative restoration."""
from pathlib import Path
import sys,json,base64,math,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
from PIL import Image,ImageFilter,ImageDraw,ImageFont
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import pymupdf as fitz
from guide_fonts import register_guide_fonts,GUIDE_FONT,GUIDE_BOLD

OUT=ROOT/'output/tshirt_fronts'
AS=ROOT/'assets/tshirt'
DPI=300
CANVAS=(4200,4800) # exactly 14 x 16 inch, maker-space DTG guide
MM=(355.6,406.4)
def px(v):return round(v*DPI/25.4)

def changseop():
    original=Image.open(AS/'changseop_source_1080.jpg').convert('RGB')
    # Keep tone, all facial geometry and expression unchanged. A very mild
    # deterministic unsharp mask only removes some interpolation softness.
    softened=original.filter(ImageFilter.UnsharpMask(radius=.45,percent=18,threshold=4))
    edge=Image.new('L',original.size,0);d=ImageDraw.Draw(edge)
    # Broad feathered subject boundary: retain head, neck, shirt and white halo;
    # exclude the gray rectangular backdrop for a white/light DTG garment.
    n=original.width
    d.polygon([(int(x*n),int(y*n)) for x,y in [
      (.38,0),(.62,0),(.76,.12),(.79,.35),(.83,.49),(.78,.64),
      (.86,.74),(1,.80),(1,1),(0,1),(0,.80),(.19,.73),(.25,.64),(.22,.41),(.24,.16)]],fill=255)
    edge=edge.filter(ImageFilter.GaussianBlur(24))
    a=np.asarray(softened,dtype=np.float32)/255
    # White-to-alpha color separation composites to the same RGB on white.
    alpha=1-a.min(axis=2)
    rgb=np.where(alpha[:,:,None]>1e-6,(a-1+alpha[:,:,None])/np.maximum(alpha[:,:,None],1e-6),0)
    matte=np.asarray(edge,dtype=np.float32)/255
    # Feather only the last 2% at the bottom/side crop so no hard photo box prints.
    yy,xx=np.mgrid[:n,:n]
    edgefade=np.minimum(1,(n-1-yy)/(.02*n))
    edgefade=np.clip(edgefade,0,1)
    alpha*=matte*edgefade
    rgba=np.dstack([np.clip(rgb,0,1),alpha])
    art=Image.fromarray(np.round(rgba*255).astype('uint8'),'RGBA')
    size=(px(330),px(330))
    art=art.resize(size,Image.Resampling.LANCZOS)
    return art,{'art_mm':[330,330],'source_pixels':[1080,1080],
        'source_sampling_ppi_at_330mm':1080/(330/25.4),'generative_edit':False,
        'operation':'LANCZOS; mild USM radius0.45/18%/threshold4; transparent white-light separation and boundary feather',
        'recovered_new_detail':False}

def aing():
    im=Image.open(AS/'aing_approved.png').convert('RGBA')
    crop=im.getchannel('A').point(lambda a:255 if a>32 else 0).getbbox()
    assert crop
    im=im.crop(crop);w=px(320);h=round(w*im.height/im.width)
    art=im.resize((w,h),Image.Resampling.NEAREST)
    return art,{'art_mm':[320,h*25.4/DPI],'source_pixels':list(im.size),
                'approved_imagegen_version':True,'resampling':'NEAREST, preserve square pixel blocks'}

def mockup(name,art,spec):
    # Scaled garment diagram: illustrative adult front 500mm wide, 700mm long.
    w,h=1000,1100;img=Image.new('RGB',(w,h),'#eee9e1');d=ImageDraw.Draw(img)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
    bold=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',30)
    body=[(330,90),(405,70),(595,70),(670,90),(885,225),(800,390),(735,350),(750,1020),(250,1020),(265,350),(200,390),(115,225)]
    d.polygon([(x+9,y+12) for x,y in body],fill='#d4cec6')
    d.polygon(body,fill='white',outline='#bcb8b1',width=2)
    d.arc((405,20,595,180),0,180,fill='#d2d0cb',width=12)
    d.arc((410,20,590,170),0,180,fill='#f3f1ec',width=8)
    # 1 pixel per millimeter: 500mm torso width and centered actual-size print.
    aw,ah=spec['art_mm'];preview=art.resize((round(aw),round(ah)),Image.Resampling.LANCZOS)
    x=round(500-aw/2);y=230
    img.paste(preview,(x,y),preview)
    label='아잉 얼굴' if name=='aing' else '신창섭 · 원본 분위기 유지'
    d.text((50,34),label,font=bold,fill='#4d493f')
    d.text((50,1060),f'그림 {aw:.0f} × {ah:.1f} mm / 밝은색 티셔츠 앞면 시안',font=font,fill='#625e56')
    img.save(OUT/name/'preview_tshirt.png')

def export(name,art,spec):
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    page=Image.new('RGBA',CANVAS,(0,0,0,0))
    x=(CANVAS[0]-art.width)//2;y=px(30 if name=='changseop' else 48)
    assert y+art.height<=CANVAS[1]
    page.alpha_composite(art,(x,y))
    page.save(folder/'01_DTG_14x16in_300ppi.png',dpi=(DPI,DPI),compress_level=6)
    art.save(folder/'02_ARTWORK_300ppi.png',dpi=(DPI,DPI))
    # PDF retains the exact physical placement for reviewing size.
    c=canvas.Canvas(str(folder/'03_ACTUAL_SIZE.pdf'),pagesize=(MM[0]*mm,MM[1]*mm))
    c.drawImage(str(folder/'01_DTG_14x16in_300ppi.png'),0,0,width=MM[0]*mm,height=MM[1]*mm,mask='auto')
    c.save()
    # Image is embedded, never linked to a local temp path.
    uri=base64.b64encode((folder/'01_DTG_14x16in_300ppi.png').read_bytes()).decode()
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="355.6mm" height="406.4mm" viewBox="0 0 355.6 406.4"><image x="0" y="0" width="355.6" height="406.4" xlink:href="data:image/png;base64,{uri}"/></svg>'
    (folder/'04_PLACEMENT.svg').write_text(svg,encoding='utf-8')
    spec.update({'canvas_mm':MM,'pixels':CANVAS,'ppi':300,'origin_mm':[x*25.4/DPI,y*25.4/DPI],'shirt':'white or light color'})
    (folder/'parameters.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    mockup(name,art,spec)
    # White-composited artwork review at a readable resolution, no additional editing.
    white=Image.new('RGBA',art.size,'white');white.alpha_composite(art)
    white.convert('RGB').resize((900,round(900*art.height/art.width)),Image.Resampling.LANCZOS).save(folder/'preview_artwork.jpg',quality=95)
    im=Image.open(folder/'01_DTG_14x16in_300ppi.png')
    assert im.mode=='RGBA' and im.size==CANVAS and abs(im.info['dpi'][0]-300)<.1
    assert im.getpixel((0,0))[3]==0
    assert all(abs(v*25.4/72-e)<.001 for v,e in zip(fitz.open(folder/'03_ACTUAL_SIZE.pdf')[0].rect[2:],MM))
    (folder/'README.md').write_text(readme(name,spec),encoding='utf-8')
    return spec

def readme(name,spec):
    title='아잉 얼굴 티셔츠' if name=='aing' else '신창섭 티셔츠'
    extra=('사용자가 확인한 아잉 시안으로 제작했습니다. 네모난 픽셀 모양과 투명 배경을 유지했습니다.\n'
           if name=='aing' else
           '**생성형 AI로 만든 신창섭 이미지는 사용하지 않았습니다.**\n'
           '같은 사진의1080×1080 파일을 내려받아 LANCZOS 확대와 아주 약한 선명도 처리만 했습니다.\n'
           '얼굴 형태·표정·색조·원래 역광을 유지했고, 밝은 옷에 사각 배경이 찍히지 않도록 배경과 가장자리를 투명 처리했습니다.\n'
           '300ppi는 출력 캔버스 해상도입니다. 흐린 원본에 없는 얼굴 세부를 새로 복원하지 않았으므로 원래의 부드러운 느낌이 남습니다.\n'
           '[다운로드 출처](https://soundcloud.com/pp3arbjmwn0p)\n')
    return f"""# {title}

![티셔츠 앞면 시안](preview_tshirt.png)

![실제 인쇄 그림](preview_artwork.jpg)

**내일은 01_DTG_14x16in_300ppi.png를 가져가세요.**
흰색·밝은색 티셔츠 앞면에 크게 넣는 파일입니다. 시안의 티셔츠 크기는 예시이며 실제 옷에 맞춰 위치를 잡습니다.

| 파일 | 용도 |
|---|---|
| 01_DTG_14x16in_300ppi.png | 안내문 규격 그대로:355.6×406.4mm,4200×4800px,투명 PNG |
| 02_ARTWORK_300ppi.png | 여백 없는 그림 단독 파일 |
| 03_ACTUAL_SIZE.pdf | 배치·실제 크기 확인용 |
| 04_PLACEMENT.svg | PNG를 내장한 편집용 배치 |
| preview_tshirt.png | 옷에 올린 설명용 시안, 이 파일을 인쇄하지 않음 |

그림 크기 **{spec['art_mm'][0]:.0f}×{spec['art_mm'][1]:.1f}mm**.
원 안내문의 DTG 최대 출력355.6×406.4mm 이내입니다.
인쇄는100% 실제 크기, 정방향으로 합니다. DTG 직접 인쇄이므로 거울 반전하지 않습니다.
티셔츠 앞뒤·소매 전체를 감싸는 올오버 방식이 아니라 앞면의 넓은 인쇄 영역을 사용하는 파일입니다.
PNG는sRGB입니다. RIP에서 장비 프로파일과 밝은색 원단 설정을 적용합니다.

{extra}
"""
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records={}
    for name,func in [('aing',aing),('changseop',changseop)]:
        art,spec=func();records[name]=export(name,art,spec)
    (OUT/'README.md').write_text("""# 큰 앞면 티셔츠 2종

두 디자인은 서로 다른 티셔츠에 인쇄합니다. 안내문 기준14×16인치 DTG 파일입니다.

| 아잉 얼굴 | 신창섭 |
|---|---|
| [인쇄 파일과 안내](aing/README.md) | [인쇄 파일과 안내](changseop/README.md) |
| ![아잉 티셔츠](aing/preview_tshirt.png) | ![신창섭 티셔츠](changseop/preview_tshirt.png) |

각 폴더의 **01_DTG_14x16in_300ppi.png**가 인쇄 파일입니다.
신창섭은 생성형 보정 없이 원본을 확대했고, 아잉은 확인받은 시안을 사용했습니다.
흰색 또는 밝은색 옷용, 실제 크기100%, 좌우 반전 없음.
그림 소스와 아잉 생성 프롬프트는 main 브랜치의 assets/tshirt에 기록되어 있습니다.
""",encoding='utf-8')
    (OUT/'validation_report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(OUT.parent/'Tshirt_Fronts_Aing_Changseop_14x16in.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,Path('tshirt_fronts')/p.relative_to(OUT))
    print(json.dumps(records,ensure_ascii=False))
if __name__=='__main__':main()
