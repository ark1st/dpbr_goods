"""Preflight current publishable artifacts: geometry, layers, resolution, renders."""
from pathlib import Path
import sys,json,subprocess,zipfile,math
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image,ImageDraw
import numpy as np
OUT=ROOT/'output'
QA=ROOT/'tmp/release_qa'
MM=72/25.4

def closed_contours(drawings):
    count=0
    for drawing in drawings:
        start=end=None
        for item in drawing['items']:
            if item[0] in ('re','qu'):
                if start is not None:
                    assert abs(start-end)<.001
                    count+=1;start=end=None
                count+=1
                continue
            a,b=item[1],item[-1]
            if start is None:start=a
            elif abs(a-end)>.001:
                assert abs(start-end)<.001
                count+=1;start=a
            end=b
        if start is not None:
            assert abs(start-end)<.001 or drawing['closePath']
            count+=1
    return count

def visible_layer(doc,name):
    groups=doc.get_ocgs()
    selected=[i for i,g in groups.items() if g['name']==name]
    assert len(selected)==1,(name,groups)
    doc.set_layer(-1,basestate='OFF',on=selected,off=[i for i in groups if i not in selected])
    return fitz.open(stream=doc.tobytes(),filetype='pdf')

def check_ai(path,dimensions,cut_count,layer='1_LASER_CUT'):
    with fitz.open(path) as original:
        names=[g['name'] for g in original.get_ocgs().values()]
        assert layer in names,(path,names)
        w,h=original[0].rect.width/MM,original[0].rect.height/MM
        assert abs(w-dimensions[0])<.01 and abs(h-dimensions[1])<.01
        with visible_layer(original,layer) as cuts:
            ds=cuts[0].get_drawings()
            assert len(ds)==cut_count,(path,len(ds),cut_count)
            assert all(p['fill'] is None and p['color']==(1,0,0) and abs(p['width']/MM-.001)<.00001 for p in ds),path
            contours=closed_contours(ds)
            assert contours==(95 if layer=='LASER_CUT' else cut_count),(path,contours)
    return {'file':str(path.relative_to(ROOT)),'size_mm':[w,h],'path_objects':cut_count,'closed_contours':contours,'layers':names}

def check_png(path,dim,rounding='round'):
    im=Image.open(path)
    expected=tuple((math.ceil if rounding=='ceil' else round)(x*300/25.4) for x in dim)
    assert im.mode=='RGBA' and im.size==expected,(path,im.mode,im.size,expected)
    assert all(abs(p-300)<.1 for p in im.info['dpi'])
    assert im.getpixel((0,0))[3]==0
    return {'file':str(path.relative_to(ROOT)),'pixels':im.size,'ppi':im.info['dpi']}

def render_pdf(path,slug):
    prefix=QA/slug
    subprocess.run(['pdftoppm','-r','85','-png',str(path),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    pages=sorted(QA.glob(slug+'-*.png'))
    with fitz.open(path) as doc:
        assert len(pages)==len(doc)
        for p in doc:
            for block in p.get_text('dict')['blocks']:
                if 'lines' in block:assert p.rect.contains(fitz.Rect(block['bbox'])),(path,block['bbox'])
    return pages

def main():
    QA.mkdir(parents=True,exist_ok=True);report={'ai':[],'png':[],'zip':[]}
    cases=[('production_v4/02_MASTER.ai',(300,160),32),
           ('carabiner_trials_v1/02_MASTER.ai',(308,72),31)]
    combined_dim=tuple(json.loads((ROOT/'configs/combined_layout.json').read_text(encoding='utf-8'))['board_mm'])
    linked_names=['tuiing','golden','burnt','unfried']
    cases.extend((f'linked_tuiing_v1/{name}/02_MASTER.ai',(55,75),3) for name in linked_names)
    for t in ['3T','5T']:
        cases.extend([
          (f'diorama_v3/{t}/02_MASTER.ai',(200,110),5),
          (f'logo_diorama_v3/{t}/02_MASTER.ai',(220,155),4),
          (f'combined_diorama_v3/{t}/02_COMBINED_MASTER.ai',combined_dim,42)])
    for t in ['3T','5T']:
        cases.append((f'len_diorama_v1/{t}/02_MASTER.ai',(320,370),15))
        cases.append((f'len_diorama_dot_v1/{t}/02_MASTER.ai',(320,370),15))
    for rel,dim,count in cases:
        if 'logo_diorama' in rel:
            with fitz.open(OUT/rel) as d:dim=(d[0].rect.width/MM,d[0].rect.height/MM)
        report['ai'].append(check_ai(OUT/rel,dim,count))
    for t in ['3T','5T']:
        report['ai'].append(check_ai(OUT/f'extra_sheet/{t}/05_MASTER.ai',(527,204),49,'LASER_CUT'))
        report['png'].append(check_png(OUT/f'extra_sheet/{t}/02_PRINT_300ppi.png',(527,204),'ceil'))
        with fitz.open(OUT/f'extra_sheet/{t}/03_CUT_ONLY.pdf') as d:
            assert len(d[0].get_drawings())==49
        rep=json.loads((OUT/f'extra_sheet/{t}/validation_report.json').read_text(encoding='utf-8'))
        assert rep['pieces']==38 and rep['min_gap_mm']>=6
        assert rep['external_30_cut_geometry_unchanged'] and rep['existing_print_pixels_unchanged']
    for rel,dim in [('production_v4/01_PRINT_300ppi.png',(300,160)),
                    ('combined_diorama_v3/3T/01_PRINT_300ppi.png',combined_dim),
                    ('combined_diorama_v3/5T/01_PRINT_300ppi.png',combined_dim),
                    ('tshirt_fronts/aing/01_DTG_14x16in_300ppi.png',(355.6,406.4)),
                    ('tshirt_fronts/changseop/01_DTG_14x16in_300ppi.png',(355.6,406.4))]:
        report['png'].append(check_png(OUT/rel,dim))
    for name in linked_names:
        report['png'].append(check_png(OUT/f'linked_tuiing_v1/{name}/01_PRINT_300ppi.png',(55,75)))
        rep=json.loads((OUT/f'linked_tuiing_v1/{name}/validation_report.json').read_text(encoding='utf-8'))
        assert rep['quantity']==1 and rep['holes']==2 and rep['closed_cut_paths']==3
        assert rep['source']['pixel_run_roundtrip_exact'] and rep['source_aspect_ratio_preserved']
    for prod in ['len_diorama_v1','len_diorama_dot_v1']:
        for t in ['3T','5T']:
            rel=f'{prod}/{t}'
            report['png'].append(check_png(OUT/f'{rel}/01_PRINT_300ppi.png',(320,370)))
            rep=json.loads((OUT/rel/'validation_report.json').read_text(encoding='utf-8'))
            assert rep['pieces']==7 and rep['cut_closed_paths']==15 and rep['slot_count']==8
            assert rep['base_mm']==[275,60] and rep['slot_ink_clearance_checked_mm']==1.5
            assert rep['same_row_standing_clearance_mm']>=2
            assert rep['art_overhang_beyond_base_mm'].get('serpent',0)<=12
            assert all(v['redrawn'] is False for v in rep['assets'].values())
            assert len(rep['assets'])==6 and all(v['sha256'] for v in rep['assets'].values())
            if prod.endswith('_dot_v1'):
                assert rep['assets']['character']['resample'].startswith('NEAREST')
    # Review render sheets, including every modified PDF guide page.
    for stale in list(QA.glob('len-guide-*.png'))+list(QA.glob('len-dot-guide-*.png')):stale.unlink()
    pages=[]
    for rel,slug in [('production_v4/00_REVISION_GUIDE.pdf','keyring-guide'),
                     ('diorama_v3/00_ASSEMBLY_GUIDE.pdf','mascot-guide'),
                     ('logo_diorama_v3/00_ASSEMBLY_GUIDE.pdf','logo-guide'),
                     ('len_diorama_v1/00_ASSEMBLY_GUIDE.pdf','len-guide'),
                     ('len_diorama_dot_v1/00_ASSEMBLY_GUIDE.pdf','len-dot-guide'),
                     ('extra_sheet/3T/01_COMBINED_SHEET.pdf','extra-3t'),
                     ('extra_sheet/5T/01_COMBINED_SHEET.pdf','extra-5t'),
                     ('tshirt_fronts/aing/03_ACTUAL_SIZE.pdf','aing'),
                     ('tshirt_fronts/changseop/03_ACTUAL_SIZE.pdf','changseop')]:
        pp=render_pdf(OUT/rel,slug);pages.extend(pp)
    cells=[]
    for p in pages:
        im=Image.open(p).convert('RGB');im.thumbnail((420,540))
        tile=Image.new('RGB',(450,575),'#e7e7e7');tile.paste(im,((450-im.width)//2,25))
        ImageDraw.Draw(tile).text((10,555),p.name,fill='black');cells.append(tile)
    contact=Image.new('RGB',(450*4,575*math.ceil(len(cells)/4)),'white')
    for i,c in enumerate(cells):contact.paste(c,((i%4)*450,(i//4)*575))
    contact.save(QA/'all-pages.png')
    for filename in ['Danpungbaram_V4_SMALL_BATCH_16pcs.zip','Danpungbaram_Diorama_V3_3T_5T.zip',
                     'Danpungbaram_Logo_Diorama_V3_MAIN_3T_5T.zip','Danpungbaram_Combined_Diorama_V3_TRIALS_11pcs.zip',
                     'Extra_Sheet_38pcs_3T.zip','Extra_Sheet_38pcs_5T.zip','Tshirt_Fronts_Aing_Changseop_14x16in.zip',
                     'Tuiing_Linked_4_Separate_Plates.zip','Danpungbaram_Len_Diorama_V1_MAIN_7pcs_3T_5T.zip',
                     'Danpungbaram_Len_Diorama_DOT_V1_MAIN_7pcs_3T_5T.zip']:
        p=OUT/filename
        with zipfile.ZipFile(p) as z:assert z.testzip() is None
        assert p.stat().st_size<100*1024*1024,(filename,p.stat().st_size)
        report['zip'].append({'file':filename,'bytes':p.stat().st_size})
    report['rendered_pages']=len(pages)
    (QA/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ai_checked':len(report['ai']),'png_checked':len(report['png']),'pages':len(pages),'zip_checked':len(report['zip'])}))
if __name__=='__main__':main()
