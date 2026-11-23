"""Cut-only recovery for an already printed plate. Never repack or rescale it."""
from pathlib import Path
import json,hashlib,zipfile
from build_a3_release import ROOT,MM,extract_layers,polygon_of,draw_path
from verify_laser_paths import contours
from laser_paths import audit_path
from vector_utils import svg_doc,layer,runvc
from artifact_hash import artifact_sha256
from pdf_layers import mark_pdf_layers
import pymupdf as fitz

def load_recovery():
    cfg=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))
    spec=cfg['recut_recoveries'][0];source=ROOT/spec['source_file']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==spec['source_sha256']
    fixed=json.loads((ROOT/spec['paths_file']).read_text(encoding='utf-8'))
    assert fixed['source_sha256']==spec['source_sha256']
    return spec,source,fixed

def originals(source):
    doc=extract_layers(source,['1_LASER_CUT'])
    paths=[p for d in doc[0].get_drawings() for p in contours(d)]
    return doc,paths

def exact_bounds(path):
    from svgpathtools import parse_path
    x0,x1,y0,y1=parse_path(path).bbox()
    return (x0,y0,x1,y1)

def main():
    from svgpathtools import parse_path
    spec,source,fixed=load_recovery();src=fitz.open(source)
    assert len(src)==1 and src[0].rotation==0
    cut,original=originals(source)
    assert len(original)==spec['contours']==len(fixed['paths'])
    holes=set(fixed['hole_indices']);rows=[];polys=[]
    for i,(before,row) in enumerate(zip(original,fixed['paths'])):
        assert row['source_index']==i
        old=polygon_of(before);stats,new=audit_path(row['path'])
        delta=old.boundary.hausdorff_distance(new.boundary);assert delta<=.035
        bbox=max(abs(a-b) for a,b in zip(old.bounds,new.bounds))
        if i in holes:
            bbox=max(abs(a-b) for a,b in zip(exact_bounds(before),exact_bounds(row['path'])))
            assert bbox<.001,('Original hole dimensions/center changed',i,bbox)
        rows.append({**row,'max_deviation_mm':delta,'bbox_deviation_mm':bbox,
                     'is_hole':i in holes,'source_segments':len(parse_path(before))})
        polys.append(new)
    # Every original loop survives once; inner contours precede external cuts.
    order=sorted(range(len(rows)),key=lambda i:(i not in holes,polys[i].centroid.y,polys[i].centroid.x))
    folder=ROOT/'output'/spec['folder'];folder.mkdir(parents=True,exist_ok=True)
    doc=fitz.open();page=doc.new_page(width=src[0].rect.width,height=src[0].rect.height)
    for i in order:draw_path(page,rows[i]['path'])
    doc.save(folder/'03_CUT_ONLY.pdf',garbage=4,deflate=True)
    (folder/'03_CUT_ONLY.svg').write_text(svg_doc(*spec['canvas_mm'],layer('LASER_CUT',''.join(
        f'<path d="{rows[i]["path"]}" fill="none" stroke="#ff0000" stroke-width="0.001"/>' for i in order))),encoding='utf-8',newline='\n')
    native=fitz.open();np=native.new_page(width=page.rect.width,height=page.rect.height)
    oc=native.add_ocg('LASER_CUT',on=True);np.show_pdf_page(np.rect,doc,0)
    mark_pdf_layers(np,{oc:[native.xref_stream(np.get_contents()[-1])]})
    tmp=ROOT/'tmp/recut_recovery';tmp.mkdir(parents=True,exist_ok=True)
    native_file=tmp/'native.pdf';native.save(native_file,garbage=4,deflate=True)
    commands=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
        {'command':'document.export','params':{'path':str(folder/'03_CUT_ONLY.ai'),'format':'pdf','createLayers':True,'preserveEditing':False}},
        {'command':'document.save','params':{'path':str(folder/'03_CUT_ONLY.vectorcraft'),'format':'vectorcraft','compress':False}}]
    info=json.loads(runvc(['run','--in',native_file,'--cmd','document.inspect']).splitlines()[-1])['result']
    assert [g['name'] for g in info['layers']]==['LASER_CUT']
    job=tmp/'export.json';job.write_text(json.dumps(commands),encoding='utf-8');runvc(['run','--in',native_file,'--commands',job])
    review=extract_layers(source,['3_ARTWORK','2_CORNER_REFERENCE'])
    for i in order:draw_path(review[0],rows[i]['path'],width=.13)
    review[0].get_pixmap(dpi=60,alpha=False).save(folder/'preview_alignment.png')
    detail=fitz.open();dp=detail.new_page(width=page.rect.width,height=page.rect.height)
    for i in order:draw_path(dp,rows[i]['path'],width=.1)
    # A non-circular complex outline, from the ACTUAL generated cut paths.
    focus=max(fixed['outer_indices'],key=lambda i:rows[i]['segments'])
    rect=fitz.Rect(*[v*MM for v in polys[focus].bounds])+(-2*MM,-2*MM,2*MM,2*MM)
    factor=min(7,1600/max(rect.width,rect.height))
    dp.get_pixmap(matrix=fitz.Matrix(factor,factor),clip=rect,alpha=False).save(folder/'cut_detail.png')
    parts=[]
    for outer in fixed['outer_indices']:
        indices=[i for i in range(len(rows)) if i==outer or (i in holes and polys[outer].contains(polys[i]))]
        parts.append({'id':f'original_{outer:03}','protected_original':False,
                      'expected_paths':[list(polys[i].exterior.coords) for i in indices]})
    assert sum(len(p['expected_paths']) for p in parts)==len(rows)
    result={'canvas_mm':spec['canvas_mm'],'source_sha256':spec['source_sha256'],
        'source_media_box_points':list(src[0].mediabox),'source_crop_box_points':list(src[0].cropbox),
        'scale':1,'translation_mm':[0,0],'rotation_degrees':0,
        'pieces':spec['pieces'],'closed_contours':len(rows),'parts':parts,
        'original_command_count':sum(r['source_segments'] for r in rows),'new_command_count':sum(r['segments'] for r in rows),
        'max_source_deviation_mm':max(r['max_deviation_mm'] for r in rows),
        'curve_evaluation_flattening_error_mm':.001,
        'conservative_source_deviation_upper_bound_mm':max(r['max_deviation_mm'] for r in rows)+.001,
        'max_hole_bbox_deviation_mm':max(r['bbox_deviation_mm'] for r in rows if r['is_hole']),
        'source_paths':rows,'cut_order_source_indices':order,'existing_print_only':True,'print_pages_added':0,
        'physical_cut_test':False,'already_cut_sections':'Unknown: no machine execution history was supplied.',
        'protected_external_30_present':False,
        'limitations':['This recovers the explicitly supplied already-printed layout, including its existing trial designs; no new test pieces or print layout are generated.',
            'Machine alignment, kerf and the previously completed cut sections cannot be validated from the file alone.']}
    (folder/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    text=f'''# 500×800mm 이미 인쇄된 판 · 재커팅 전용

**A3가 아닙니다. 새 인쇄 없이 기존 판을 다시 자르는 복구 파일입니다.**
원본 대지 {spec['canvas_mm'][0]:.6f}×{spec['canvas_mm'][1]:.6f}mm, 배율100%, 이동0, 회전0을 유지했습니다.

- `03_CUT_ONLY.ai` / PDF / SVG / VectorCraft: 같은 위치의 재단 전용 벡터. 빨강0.001mm.
- 원본77조각·294폐곡선을 모두 유지하고 내부 구멍을 먼저 배치했습니다.
- 이동 명령 {result['original_command_count']:,} → {result['new_command_count']:,}. 최대 원본 경로 차이 {result['max_source_deviation_mm']:.6f}mm.
- 구멍 외곽 치수의 최대 차이 {result['max_hole_bbox_deviation_mm']:.6f}mm. 실제 커팅 속도·끼움은 실물 미검증입니다.

**장비에서도100%·같은 대지 원점으로 사용하세요. 자동 맞춤·개별 조각 재배치는 하지 않습니다.**
중지 전에 이미 잘린 구간은 파일만으로 알 수 없습니다. 작업자가 완료·분리된 조각을 확인해 재커팅 대상을 선택해야 합니다.
기존에 인쇄된 시험 디자인도 원본 그대로 복구하며 새 시험편·인쇄용 대지는 추가하지 않습니다.

![기존 인쇄 위치와 새 칼선 대조 · 검토용](preview_alignment.png)

![실제 새 칼선 확대](cut_detail.png)

[전체 검증 기록](validation.json) · [A3 출력 목록](../../a3_release)
'''
    (folder/'README.md').write_text(text,encoding='utf-8',newline='\n')
    with zipfile.ZipFile(folder/'RECUT_ONLY.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in spec['files']:
            if name!='RECUT_ONLY.zip':z.write(folder/name,name)
    print(json.dumps({k:result[k] for k in ['pieces','closed_contours','original_command_count','new_command_count','max_source_deviation_mm','max_hole_bbox_deviation_mm','print_pages_added']}),flush=True)
    return result

if __name__=='__main__':main()
