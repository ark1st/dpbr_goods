"""Measure the supplied Ascent geometry without rescaling or changing interfaces."""
from pathlib import Path
import json,math
from build_a3_release import ROOT,MM,CONFIG,ascent_parts,clip_art,draw_path
from shapely.geometry import LineString
import pymupdf as fitz
from PIL import Image,ImageDraw,ImageFont

def measure(parts):
    selected=set(CONFIG['ascent_remaining']['part_ids']);rows=[];findings=[]
    for p in parts:
        if p['id'] not in selected:continue
        b=p['bounds'];w,h=b[2]-b[0],b[3]-b[1];base=len(p['paths'])==9
        assert abs(w-104)<.001 and abs(h-(30 if base else 62.80699))<.001
        row={'id':p['id'],'type':'base' if base else 'printed_panel','outer_size_mm':[w,h]}
        if base:
            slots=sorted([e['poly'] for e in p['paths'][:-1]],key=lambda q:q.centroid.y)
            dims=[[q.bounds[2]-q.bounds[0],q.bounds[3]-q.bounds[1]] for q in slots]
            assert all(abs(a-20.2)<.001 and abs(b-3.2)<.001 for a,b in dims)
            pairs=[sorted(slots[i:i+2],key=lambda q:q.centroid.x) for i in range(0,8,2)]
            stagger=[abs(a.centroid.y-b.centroid.y) for a,b in pairs]
            pitch=[abs(a.centroid.x-b.centroid.x) for a,b in pairs]
            assert all(abs(v-40)<.001 for v in pitch)
            row.update(slots_mm=dims,paired_slot_center_pitch_mm=pitch,paired_slot_depth_stagger_mm=stagger)
            if max(stagger)>.01:
                findings.append({'id':p['id'],'status':'original_preserved_physical_fit_unverified',
                    'max_slot_depth_stagger_mm':max(stagger),
                    'note':'Paired slots are slightly staggered in the base plane; assembly may yaw. No automatic alignment or nominal-thickness fit guarantee.'})
        else:
            shoulder=b[3]-3
            section=p['poly'].intersection(LineString([(b[0]-1,shoulder+1),(b[2]+1,shoulder+1)]))
            spans=list(section.geoms) if hasattr(section,'geoms') else [section]
            widths=sorted(q.length for q in spans)
            assert len(widths)==2 and all(abs(v-20)<.001 for v in widths)
            row.update(tab_widths_mm=widths,tab_depth_mm=3,nominal_visible_height_above_base_mm=h-3)
        rows.append(row)
    assert len(rows)==25 and sum(r['type']=='base' for r in rows)==4
    return {'scale':1,'unit':'mm','parts':rows,'geometry_size_errors':[],
        'source_part_count':31,'excluded_cadena':CONFIG['cadena_source_part_ids'],
        'excluded_blank_panel':'ascent_31','included_parts':25,'printed_panels':21,'bases':4,
        'findings':findings,'physical_cut_or_fit_test':False,
        'status':'digital_dimensions_verified_original_interfaces_preserved',
        'limitations':['Nominal3T is not a measurement of the supplied acrylic.',
          'Software confirms source dimensions and unchanged vector geometry, not physical fit, kerf or cutting quality.',
          'No fit-test pieces or additional bases were generated.']}

def main():
    folder=ROOT/'output/a3_release/11_ascent_remaining';folder.mkdir(parents=True,exist_ok=True)
    parts=ascent_parts();report=measure(parts)
    selected={p['id']:p for p in parts if p['id'] in CONFIG['ascent_remaining']['part_ids']}
    pxmm=7;W,H=1800,1400;im=Image.new('RGB',(W,H),'#f7f4ed');dr=ImageDraw.Draw(im)
    font=lambda n,b=False:ImageFont.truetype('C:/Windows/Fonts/'+('malgunbd.ttf' if b else 'malgun.ttf'),n)
    dr.text((65,45),'어센트 · 원본 크기 검증',font=font(48,True),fill='#3e463f')
    dr.text((68,115),'카데나 제외 / 인쇄 판21 + 받침4 / 아크릴3T / 아래 두 그림은 같은 축척',font=font(27),fill='#75786f')
    def paste_piece(p,x,y):
        b=p['bounds'];art=clip_art(p['art'],p);doc=fitz.open();pg=doc.new_page(width=(b[2]-b[0]+2)*MM,height=(b[3]-b[1]+2)*MM)
        if art[0].get_contents():pg.show_pdf_page(fitz.Rect(MM,MM,(b[2]-b[0]+1)*MM,(b[3]-b[1]+1)*MM),art,0,clip=fitz.Rect(*[q*MM for q in b]))
        from build_a3_release import transformed_cut_path
        for e in p['paths']:draw_path(pg,transformed_cut_path(e['path'],{'piece':p,'x':1,'y':1,'rotation':0}),color=(.55,.64,.61),width=.16)
        pix=pg.get_pixmap(matrix=fitz.Matrix(pxmm/MM,pxmm/MM),alpha=False)
        artim=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);im.paste(artim,(x,y))
    paste_piece(selected['ascent_17'],80,240)
    paste_piece(selected['ascent_02'],970,240)
    dr.text((90,745),'인쇄 판: 104 × 62.807mm (돌기3mm 포함)',font=font(27,True),fill='#3e463f')
    dr.text((985,500),'받침: 104 × 30mm',font=font(27,True),fill='#3e463f')
    dr.text((985,555),'홈8개: 약20.2 × 3.2mm',font=font(26),fill='#5d665b')
    dr.text((985,605),'돌기2개: 폭20mm · 삽입깊이3mm',font=font(25),fill='#5d665b')
    # This is a digital measurement reference, not an acrylic coupon or cut path.
    x0,y0=95,925;dr.line((x0,y0,x0+100*pxmm,y0),fill='#526052',width=3)
    for i in range(0,101,10):
        x=x0+i*pxmm;dr.line((x,y0-10,x,y0+12),fill='#526052',width=2);dr.text((x-9,y0+22),str(i),font=font(20),fill='#526052')
    dr.text((x0,y0+65),'100mm 기준자 · 화면 표시 크기는 실제 크기와 다릅니다.',font=font(24),fill='#73786d')
    dr.text((75,1110),'치수 확인 결과: 원본 배율100% 유지. A3 출력도 자동 맞춤 없이100%.',font=font(28,True),fill='#3e463f')
    dr.text((75,1170),'원본 받침의 좌우 홈에 약0.195mm 앞뒤 위치 차이가 있습니다. 수정하지 않고 기록했습니다.',font=font(26),fill='#8b5e3d')
    dr.text((75,1230),'실제 재료 두께·커프·끼움은 미검증입니다. 이 이미지는 검토용이며 재단 파일이 아닙니다.',font=font(25),fill='#75786f')
    im.save(folder/'size_check.png')
    (folder/'SIZE_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'ascent_size_checked':len(report['parts']),'base_findings':len(report['findings']),'physical_fit_test':False}),flush=True)
    return report

if __name__=='__main__':main()
