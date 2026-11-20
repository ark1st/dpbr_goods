"""Add five Yun parts, preserving artwork size with thickness-specific interfaces."""
from pathlib import Path
from io import BytesIO
import sys,json,subprocess,hashlib,math,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
import numpy as np,cv2
from PIL import Image
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ContentStream,NameObject
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union,nearest_points
from shapely import concave_hull
from vector_utils import runvc
from laser_paths import draw_cut_pdf
from build_extra_sheet import mark_pdf_layers
MM=72/25.4
OUT_ROOT=ROOT/'output/extra_sheet'
OUT=OUT_ROOT
TMP=ROOT/'tmp/extra38'
BASE_COMMIT='e417eaf70d398bc740532314120c039ecb2ff516'
W,H=527,204

def extracted(reader,keys):
    writer=PdfWriter();p=writer.add_page(reader.pages[0])
    c=ContentStream(None,writer);c.operations=[]
    for key in keys:c.operations.extend([([],b'q'),([NameObject(key)],b'Do'),([],b'Q')])
    p.replace_contents(c)
    p['/Resources'].pop(NameObject('/Properties'),None)
    # Prune unused forms so source files stay compact.
    forms=p['/Resources']['/XObject']
    for k in list(forms):
        if k not in keys:del forms[k]
    writer.compress_identical_objects(remove_unreferenced=True)
    b=BytesIO();writer.write(b)
    return fitz.open(stream=b.getvalue(),filetype='pdf')

def polygon(d):
    pts=[]
    for item in d['items']:
        if item[0]=='l':
            pts.extend([(item[1].x/MM,item[1].y/MM),(item[2].x/MM,item[2].y/MM)])
        elif item[0]=='c':
            a,b,c,e=item[1:]
            for t in np.linspace(0,1,65):
                q=a*(1-t)**3+b*3*(1-t)**2*t+c*3*(1-t)*t*t+e*t**3
                pts.append((q.x/MM,q.y/MM))
        elif item[0]=='re':
            r=item[1];pts.extend([(r.x0/MM,r.y0/MM),(r.x1/MM,r.y0/MM),(r.x1/MM,r.y1/MM),(r.x0/MM,r.y1/MM)])
        elif item[0]=='qu':
            q=item[1];pts.extend([(p.x/MM,p.y/MM) for p in [q.ul,q.ur,q.lr,q.ll]])
        else:raise ValueError(item[0])
    p=Polygon(pts).buffer(0)
    # Geometry here is only for occupied-region distance checks. Original
    # external PDF operators are reused untouched, including compound paths.
    assert p.is_valid and p.area>0,(d['rect'],p.geom_type,p.area)
    return p

def draw_poly(page,p,color=(1,0,0),width=.001):
    draw_cut_pdf(page,p,color,width)


def normalize_cut(source,indexes=None):
    out=fitz.open();p=out.new_page(width=source[0].rect.width,height=source[0].rect.height)
    for i,d in enumerate(source[0].get_drawings()):
        if indexes is not None and i not in indexes:continue
        s=p.new_shape()
        for v in d['items']:
            if v[0]=='l':s.draw_line(v[1],v[2])
            elif v[0]=='c':s.draw_bezier(*v[1:])
            elif v[0]=='re':s.draw_rect(v[1])
            elif v[0]=='qu':s.draw_quad(v[1])
            else:raise ValueError(v[0])
        s.finish(color=(1,0,0),width=.001*MM,closePath=True);s.commit()
    return out

def update_owned_cuts(art_doc,old_doc):
    ds=old_doc[0].get_drawings();assert len(ds)==6
    out=fitz.open();p=out.new_page(width=421*MM,height=204*MM);report=[];polys=[]
    for n in range(3):
        hole_d,outer_d=ds[n*2:n*2+2];old=polygon(outer_d)
        clip=fitz.Rect(outer_d['rect'])
        pix=art_doc[0].get_pixmap(matrix=fitz.Matrix(8,8),clip=clip,alpha=True)
        alpha=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,4)[:,:,3]
        contours,_=cv2.findContours((alpha>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        shapes=[]
        for c in contours:
            if cv2.contourArea(c)>6:
                pts=(c[:,0,:]+[pix.x,pix.y])/8/MM
                shapes.append(Polygon(pts).buffer(0))
        art=unary_union(shapes);carrier=art if n==0 else concave_hull(art,ratio=.45)
        body=carrier.buffer(2.5,quad_segs=64)
        if body.geom_type!='Polygon':body=concave_hull(body,ratio=.5)
        body=Polygon(body.exterior)
        hr=hole_d['rect'];cx,cy=(hr.x0+hr.x1)/2/MM,(hr.y0+hr.y1)/2/MM
        hole=Point(cx,cy).buffer(2,quad_segs=128)
        near=nearest_points(Point(cx,cy),art)[1]
        bridge=LineString([(cx,cy),near.coords[0]]).buffer(3.5,quad_segs=64)
        outer=unary_union([body,Point(cx,cy).buffer(4.5,quad_segs=128),bridge])
        outer=Polygon(outer.exterior)
        assert outer.is_valid and outer.contains(art) and outer.contains(hole)
        assert outer.difference(old.buffer(.10)).area<.04,(n,outer.difference(old.buffer(.10)).area)
        edge=outer.boundary.distance(hole);border=outer.boundary.distance(art)
        assert 2.49<edge<2.51 and 2.49<border<2.51,(edge,border)
        draw_poly(p,hole);draw_poly(p,outer);polys.append(outer)
        report.append({'piece':['danpaengi','mini_logo_1','mini_logo_2'][n],'art_border_mm':border,'hole_edge_mm':edge,'hole_center_unchanged':True})
    return out,report,polys

def adapt_yun(cut_doc,art_doc,thickness):
    """Keep native artwork size; add flat clear shoulders and thickness tabs."""
    ds=cut_doc[0].get_drawings()
    new=fitz.open();page=new.new_page(width=cut_doc[0].rect.width,height=cut_doc[0].rect.height)
    reports=[];placement_bounds=[]
    for i,d in enumerate(ds):
        poly=polygon(d)
        if i<2:
            r=d['rect'];pix=art_doc[0].get_pixmap(matrix=fitz.Matrix(8,8),clip=r,alpha=True)
            alpha=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,4)[:,:,3]
            contours,_=cv2.findContours((alpha>8).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            arts=[Polygon((c[:,0,:]+[pix.x,pix.y])/8/MM).buffer(0) for c in contours if cv2.contourArea(c)>6]
            art=unary_union(arts)
            bottom=poly.bounds[3]
            bottom_pts=[q for q in poly.exterior.coords if abs(q[1]-bottom)<.002]
            xl=min(q[0] for q in bottom_pts);xr=max(q[0] for q in bottom_pts)
            assert abs(xr-xl-20)<.01
            shoulder=art.bounds[3]+2.5
            upper=poly.intersection(box(-100,-100,900,shoulder))
            bridge=box(xl-2,bottom-9,xr+2,shoulder)
            tab=box(xl,shoulder,xr,shoulder+thickness-.4)
            poly=unary_union([upper,bridge,tab])
            assert poly.geom_type=='Polygon' and poly.is_valid and poly.contains(art)
            assert poly.boundary.distance(art)>1.0
            reports.append({'name':f'yun_stand_{i+1}','tab_width_mm':xr-xl,'tab_depth_mm':thickness-.4,
                            'art_scale':1,'flat_shoulder_y_mm':shoulder,'min_art_clearance_mm':poly.boundary.distance(art)})
        elif i in [3,5,7,8]:
            x0,y0,x1,y1=poly.bounds;cy=(y0+y1)/2
            poly=box(x0,cy-(thickness+.2)/2,x1,cy+(thickness+.2)/2)
        # Keep the original print origin even if fitting moves a curve extremum.
        placement_bounds.append([float(np.float32(v*MM)) for v in poly.bounds])
        draw_poly(page,poly)
    return new,reports,placement_bounds

def build(thickness):
    global OUT
    OUT=OUT_ROOT/f"{thickness}T"
    TMP.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    baseline=subprocess.check_output(['git','show',f'{BASE_COMMIT}:output/extra_sheet/{thickness}T/01_COMBINED_SHEET.pdf'],cwd=ROOT)
    (TMP/'baseline33.pdf').write_bytes(baseline)
    reader=PdfReader(BytesIO(baseline))
    # The selected published master has three separately placed source groups.
    print_doc=extracted(reader,['/fzFrm0','/fzFrm2','/fzFrm5'])
    ext_cut=extracted(reader,['/fzFrm1','/fzFrm3'])
    owned_art=extracted(reader,['/fzFrm5']);old_owned_cut=extracted(reader,['/fzFrm6'])
    old_white=extracted(reader,['/fzFrm4','/fzFrm7'])
    owned_cut,owned_report,owned_polys=update_owned_cuts(owned_art,old_owned_cut)
    assert len(ext_cut[0].get_drawings())==34
    source=ROOT/'assets/external/yun_image_sd_stand.ai'
    yr=PdfReader(source)
    yc=extracted(yr,['/x1']);yw=extracted(yr,['/x2']);yk=normalize_cut(extracted(yr,['/x3']))
    yk,fit_report,placement_bounds=adapt_yun(yk,yc,thickness)
    yd=yk[0].get_drawings();assert len(yd)==9
    # Group original cut contours: 2 figures, 2 single bases, 1 double base.
    specs=[('yun_stand_1',[0],(427,8)),('yun_stand_2',[1],(477,8)),
           ('yun_base_1',[2,3],(432,82)),('yun_base_2',[4,5],(432,119)),('yun_double_base',[6,7,8],(432,156))]
    master=fitz.open();mp=master.new_page(width=W*MM,height=H*MM)
    cut=fitz.open();cp=cut.new_page(width=W*MM,height=H*MM)
    white=fitz.open();wp=white.new_page(width=W*MM,height=H*MM)
    oc={name:master.add_ocg(name,on=name in ['PRINT_ARTWORK','CORNER_REFERENCE']) for name in ['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT','WHITE_INK_MASK']}
    streams={v:[] for v in oc.values()}
    def add(doc,clip,dest,name,target=None):
        mp.show_pdf_page(dest,doc,0,clip=clip)
        streams[oc[name]].append(master.xref_stream(mp.get_contents()[-1]))
        if target:target.show_pdf_page(dest,doc,0,clip=clip)
    original=fitz.Rect(0,0,421*MM,204*MM)
    add(print_doc,original,original,'PRINT_ARTWORK')
    add(ext_cut,original,original,'LASER_CUT',cp)
    add(owned_cut,original,original,'LASER_CUT',cp)
    add(old_white,original,original,'WHITE_INK_MASK',wp)
    all_polys=[polygon(d) for d in ext_cut[0].get_drawings()]+owned_polys
    # Only outer contours for distance verification.
    old_outers=[p for i,p in enumerate(all_polys) if not any(q.contains(p) for j,q in enumerate(all_polys) if i!=j)]
    assert len(old_outers)==33,len(old_outers)
    placed=[];new_polys=[]
    for name,indexes,(x,y) in specs:
        outer=polygon(yd[indexes[0]]);r=fitz.Rect(placement_bounds[indexes[0]])
        # 0.2 mm clip bleed preserves the red hairline, no neighbor enters this clip.
        clip=fitz.Rect(r.x0-.2*MM,r.y0-.2*MM,r.x1+.2*MM,r.y1+.2*MM)
        tx=x*MM-r.x0;ty=y*MM-r.y0
        dest=fitz.Rect(clip.x0+tx,clip.y0+ty,clip.x1+tx,clip.y1+ty)
        assert abs(dest.width-clip.width)<1e-8 and abs(dest.height-clip.height)<1e-8
        # Empty bases intentionally have no color or white ink.
        if name.startswith('yun_stand'):
            add(yc,clip,dest,'PRINT_ARTWORK');add(yw,clip,dest,'WHITE_INK_MASK',wp)
        piece_cut=normalize_cut(yk,indexes)
        add(piece_cut,clip,dest,'LASER_CUT',cp)
        from shapely import affinity
        shifted=affinity.translate(outer,tx/MM,ty/MM);new_polys.append(shifted)
        placed.append({'name':name,'outer_mm':[r.width/MM,r.height/MM],'top_left_mm':[x,y],'scale':1,'source_cut_paths':len(indexes)})
    s=mp.new_shape();s.draw_rect(fitz.Rect(4*MM,4*MM,(W-4)*MM,(H-4)*MM));s.finish(color=(0,0,1),width=.3*MM);s.commit()
    streams[oc['CORNER_REFERENCE']].append(master.xref_stream(mp.get_contents()[-1]))
    mark_pdf_layers(mp,streams)
    master.set_layer(-1,basestate='OFF',on=[oc['PRINT_ARTWORK'],oc['CORNER_REFERENCE']],off=[oc['LASER_CUT'],oc['WHITE_INK_MASK']])
    master.save(OUT/'01_COMBINED_SHEET.pdf',garbage=4,deflate=True)
    cut.save(OUT/'03_CUT_ONLY.pdf',garbage=4,deflate=True)
    white.save(OUT/'04_WHITE_INK_MASK.pdf',garbage=4,deflate=True)
    for page,name in [(mp,'02_PRINT_300ppi.png'),(wp,'04_WHITE_INK_MASK_300ppi.png')]:
        page.get_pixmap(dpi=300,alpha=True).save(OUT/name)
    # Same scene rendered with the cut plate visible for review only.
    master.set_layer(-1,basestate='ON',on=list(oc.values())[:3],off=[oc['WHITE_INK_MASK']])
    master.save(TMP/'review.pdf',garbage=4,deflate=True)
    with fitz.open(TMP/'review.pdf') as review:review[0].get_pixmap(dpi=100,alpha=False).save(OUT/'preview.png')
    master.set_layer(-1,basestate='ON',on=list(oc.values()),off=[])
    master.save(TMP/'all_layers.pdf',garbage=4,deflate=True)
    info=json.loads(runvc(['run','--in',TMP/'all_layers.pdf','--cmd','document.inspect']).splitlines()[-1])['result']
    layers={v['name']:v for v in info['layers']}
    assert set(layers)==set(oc)
    commands=[
      {'command':'document.setUnits','params':{'units':'Millimeters'}},
      {'command':'layer.setProps','params':{'ids':[layers[n]['id'] for n in ['LASER_CUT','WHITE_INK_MASK']],'visible':False,'printable':False}},
      {'command':'document.save','params':{'path':str(OUT/'05_MASTER.vectorcraft'),'format':'vectorcraft','compress':False}},
      {'command':'layer.setProps','params':{'ids':[layers[n]['id'] for n in ['LASER_CUT','WHITE_INK_MASK']],'visible':True,'printable':True}},
      {'command':'document.export','params':{'path':str(OUT/'05_MASTER.ai'),'format':'ai','createLayers':True,'preserveEditing':True}}]
    job=TMP/'export.json';job.write_text(json.dumps(commands),encoding='utf-8');runvc(['run','--in',TMP/'all_layers.pdf','--commands',job])
    # VectorCraft omits hidden geometry when exporting AI. Export every plate
    # first, then only change the PDF-compatible AI's initial layer visibility.
    with fitz.open(OUT/'05_MASTER.ai') as ai:
        ai_groups=ai.get_ocgs()
        on=[k for k,v in ai_groups.items() if v['name'] in ['PRINT_ARTWORK','CORNER_REFERENCE']]
        ai.set_layer(-1,basestate='OFF',on=on,off=[k for k in ai_groups if k not in on])
        ai.save(TMP/'final_master.ai',garbage=4,deflate=True)
    shutil.copy2(TMP/'final_master.ai',OUT/'05_MASTER.ai')
    ds=cp.get_drawings();assert len(ds)==49,len(ds)
    from verify_release import closed_contours
    assert closed_contours(ds)==95
    assert all(d['color']==(1,0,0) and d['fill'] is None and abs(d['width']-.001*MM)<1e-6 for d in ds)
    polys=old_outers+new_polys
    gap=min(a.distance(b) for i,a in enumerate(polys) for b in polys[:i]);assert gap>=6,gap
    assert all(box(4,4,W-4,H-4).contains(p) for p in polys)
    # Verify every old external cut coordinate is unchanged, by isolating its
    # first imported group and comparing vector drawing tuples.
    old_sig=[(d['rect'],d['items']) for d in ext_cut[0].get_drawings()]
    new_sig=[(d['rect'],d['items']) for d in ds[:34]]
    assert old_sig==new_sig
    with fitz.open(OUT/'01_COMBINED_SHEET.pdf') as result:
        # Original print area remains byte-for-byte identical after rasterizing.
        a=print_doc[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=True)
        result.set_layer(-1,basestate='OFF',on=[oc['PRINT_ARTWORK']],off=[oc['CORNER_REFERENCE'],oc['LASER_CUT'],oc['WHITE_INK_MASK']])
        # Reopen extraction by the newly generated first print form to avoid UI layer caching.
        nr=PdfReader(OUT/'01_COMBINED_SHEET.pdf')
        first=next(args[0] for args,op in nr.pages[0].get_contents().operations if op==b'Do')
        retained=extracted(nr,[str(first)])
        b=retained[0].get_pixmap(matrix=fitz.Matrix(2,2),clip=original,alpha=True)
        assert a.samples==b.samples
    report={'canvas_mm':[W,H],'pieces':38,'existing_pieces':33,'added_pieces':5,
      'cut_path_objects':49,'closed_contours':95,'outer_contours':38,'inner_contours':57,
      'external_30_cut_geometry_unchanged':True,'existing_print_pixels_unchanged':True,
      'owned_cut_updates':owned_report,'new_parts':placed,'min_gap_mm':gap,'scale':1,
      'thickness_mm':thickness,'yun_tab_adaptation':fit_report,'new_base_slots_mm':[[20.2,thickness+.2]]*4,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'baseline_commit':BASE_COMMIT,'physical_fit_test':False,'ai_layers':list(layers)}
    (OUT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text(f'# 엑스트라38조각 · {thickness}T\n\n![제작 배치](preview.png)\n\n[전체 안내](../README.md)\n\n이 폴더는 캐릭터와 받침 모두{thickness}mm인 경우입니다. 슬롯20.2×{thickness+.2:.1f}mm, 돌기{thickness-.4:.1f}mm.\n인쇄·백색·재단 모두 이 폴더의 같은 버전을 사용합니다.\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

README="""# 엑스트라 시트 (김윤양지수) - yun 스탠드 추가38조각

**기존33조각 + 새yun 캐릭터2·받침3 = 총38조각. 527×204mm.**

| 판 두께 | 제작 파일 | 받침 홈 | 돌기 깊이 |
|---|---|---|---|
| 3T | [3T 폴더](3T) | 20.2×3.2mm | 2.6mm |
| 5T | [5T 폴더](5T) | 20.2×5.2mm | 4.6mm |

캐릭터와 받침이 같은 두께인 경우입니다. 실제 판에 맞는 한 폴더를 선택하세요.
최상단 파일은3T 파일의 사본입니다.5T는 반드시5T 폴더를 사용합니다.
**인쇄·백색·재단을 서로 다른 두께 폴더에서 섞어 사용하지 마세요.**

![38조각 전체 시안](3T/preview.png)

- 01_COMBINED_SHEET.pdf: 그림·파란 기준선이 기본으로 표시되는 합본.
- 02_PRINT_300ppi.png: UV 인쇄용 투명300ppi PNG.
- 03_CUT_ONLY.pdf: 빨강 #FF0000 /0.001mm 재단 전용.
- 04_WHITE_INK_MASK_300ppi.png 또는 PDF: 검정 영역을 백색 잉크로 지정하는 분판.
- 05_MASTER.ai / vectorcraft: 색상·기준선·칼선·백색 레이어를 분리한 편집 원본.

새yun 그림은 크기를 바꾸지 않고 오른쪽에 배치했습니다. 받침은각80×30mm.
받침3개는1인용2개와2인용1개로, 원본에 있는 선택용 받침을 모두 넣었습니다.
원본의 약8mm 긴 돌기는 판 아래로 돌출될 수 있어 **투명 수평 어깨와20mm 돌기**로 정리했습니다.
3T/5T용 돌기 깊이는각2.6/4.6mm, 홈은각3.2/5.2mm입니다. 그림·백색 크기는 바꾸지 않았습니다.
수정하지 않은 원본AI는main의assets/external에 보관합니다.

기존30개 외부 도안은 저장소에 새로 올라온각3T/5T 버전을 그대로 보존했습니다.
외부 캐릭터의 일반 외곽 여백은 변경하지 않았습니다.
단풍바람3개(단팽이1·미니 로고2)만 그림-칼선과 구멍-외곽을2.5mm로 줄였습니다.
기존33개 인쇄 그림은각두께 원본과 픽셀 비교로 보존을 확인했습니다.

폐곡선95개 = 외곽38개 +구멍·홈57개. PDF에서는49개 복합/단일 경로 객체입니다.
장비에서 내부 경로 우선 가공을 지정합니다.
최소 조각 간격6mm 이상, 실제 크기100%, 같은 원점, 자동 맞춤 해제.
파란 위치 사각형은 재단 대상이 아닙니다.
백색은 원본에서 제공된 부분만 보존했으며 나머지 그림은 기존처럼RIP에서 설정을 확인합니다.
홈과 돌기는 커프 보정 전 치수입니다. 같은 재료·장비로 끼움 시험 후 본 제작을 진행합니다.
실물 인쇄 정합·끼움 시험을 마쳤다는 의미가 아닙니다.
"""

if __name__=='__main__':
    build(3)
    build(5)
    for p in (OUT_ROOT/'3T').iterdir():
        if p.is_file() and p.name!='README.md':shutil.copy2(p,OUT_ROOT/p.name)
    (OUT_ROOT/'README.md').write_text(README,encoding='utf-8')
    for t in ['3T','5T']:
        with zipfile.ZipFile(OUT_ROOT.parent/f'Extra_Sheet_38pcs_{t}.zip','w',zipfile.ZIP_DEFLATED) as z:
            z.write(OUT_ROOT/'README.md',Path('extra_sheet')/'README.md')
            for p in sorted((OUT_ROOT/t).rglob('*')):
                if p.is_file():z.write(p,Path('extra_sheet')/p.relative_to(OUT_ROOT))
