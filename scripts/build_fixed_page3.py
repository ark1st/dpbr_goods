"""Append reviewed additions to the user's immutable third-plate artwork."""
import json, shutil
from pathlib import Path
import pymupdf as fitz
from build_a3_release import (ROOT, MM, TMP, CONFIG, extract_layers, write_page,
    reviewed_layout, polygon_of, draw_path, transformed_cut_path)
from fixed_page3_assets import additions
from fixed_page3_checks import verify_frozen_pages, verify_fixed_source, check_page_geometry
from verify_laser_paths import contours, native_pdf
from pdf_layers import mark_pdf_layers
from vector_utils import runvc, svg_doc, layer


def main():
    cfg=CONFIG['fixed_source_page3'];verify_frozen_pages(ROOT,cfg)
    source=ROOT/cfg['source_file'];geometry=json.loads((ROOT/cfg['geometry_file']).read_text())
    plan=json.loads((ROOT/'configs/fixed_page3_additions.json').read_text())
    scratch=ROOT/'tmp/fixed_page3_build';scratch.mkdir(parents=True,exist_ok=True)
    added=additions();placements=reviewed_layout('11_ascent_remaining/3T',added,plan['placements'])[0]['placements']
    write_page(scratch/'additions',placements)
    addition_spec=json.loads((scratch/'additions/validation.json').read_text())
    for row,placed in zip(addition_spec['parts'],placements,strict=True):
        row['canonical_id']=placed['piece'].get('canonical_id',row['id'])
    fixed=[]
    for part in geometry['parts']:
        b=part['bounds_mm'];entries=[part['source_outer'],*part['source_holes']]
        fixed.append(dict(id=part['id'],source='fixed_page3',source_bounds_mm=b,
            placed_bounds_mm=b,rotated_origin_mm=[0,0],rotation_degrees=0,scale=1,
            path_count=len(entries),protected_original=True,fixed_reference=True,
            max_source_curve_deviation_mm=0,
            expected_paths=[list(polygon_of(e['path']).exterior.coords) for e in entries],
            design_metadata={'source_sha256':geometry['sha256']}))
    parts=fixed+addition_spec['parts']
    exceptions=check_page_geometry(parts)
    # Keep the original printable vectors/bitmaps as full-page PDF forms. Do not
    # reclip, rasterize or rebuild existing artwork through per-piece exports.
    base={n:extract_layers(source,[n]) for n in ['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT']}
    more={n:extract_layers(scratch/'additions/02_MASTER.pdf',[n]) for n in ['PRINT_ARTWORK','LASER_CUT','WHITE_INK_MASK']}
    master=fitz.open();mp=master.new_page(width=420*MM,height=297*MM)
    names=['PRINT_ARTWORK','CORNER_REFERENCE','LASER_CUT','WHITE_INK_MASK']
    oc={n:master.add_ocg(n,on=n!='WHITE_INK_MASK') for n in names};streams={v:[] for v in oc.values()}
    for name in names:
        for doc in [base.get(name),more.get(name)]:
            if doc is not None and doc[0].get_contents():
                mp.show_pdf_page(mp.rect,doc,0)
                streams[oc[name]].append(master.xref_stream(mp.get_contents()[-1]))
    mark_pdf_layers(mp,streams)
    master.set_layer(-1,basestate='OFF',on=[oc[n] for n in names if n!='WHITE_INK_MASK'],off=[oc['WHITE_INK_MASK']])
    draft=scratch/'combined.pdf';master.save(draft,garbage=4,deflate=True)
    for n,stem in [('PRINT_ARTWORK','01_PRINT'),('LASER_CUT','03_CUT_ONLY'),('WHITE_INK_MASK','04_WHITE_INK_MASK')]:
        selected=[n,'CORNER_REFERENCE'] if n=='PRINT_ARTWORK' else [n]
        doc=extract_layers(draft,selected);doc.save(scratch/(stem+'.pdf'),garbage=4,deflate=True)
        if n!='LASER_CUT':doc[0].get_pixmap(dpi=300,alpha=True).save(scratch/(stem+'_300ppi.png'))
    cut=fitz.open(scratch/'03_CUT_ONLY.pdf');paths=[p for d in cut[0].get_drawings() for p in contours(d)]
    assert len(paths)==sum(p['path_count'] for p in parts)
    # Source widths are copied; only newly drawn paths use the project .001mm.
    svg=[]
    for part in geometry['parts']:
        for e in [part['source_outer'],*part['source_holes']]:
            svg.append(f'<path d="{e["path"]}" fill="none" stroke="#ff0000" stroke-width="{e["stroke_mm"]}"/>')
    # Keep source precision here: a second PDF coordinate quantization can
    # introduce a sub-micron backtrack where the copied insert meets the body.
    for place in placements:
        for entry in place['piece']['paths']:
            path=transformed_cut_path(entry['path'],place)
            svg.append(f'<path d="{path}" fill="none" stroke="#ff0000" stroke-width="0.001"/>')
    (scratch/'03_CUT_ONLY.svg').write_text(svg_doc(420,297,layer('LASER_CUT',''.join(svg))),encoding='utf-8')
    info=json.loads(runvc(['run','--in',draft,'--cmd','document.inspect']).splitlines()[-1])['result']
    layers={g['name']:g['id'] for g in info['layers']};assert set(layers)==set(names)
    job=[{'command':'layer.setProps','params':{'ids':[layers['LASER_CUT']],'visible':True,'printable':False}},
         {'command':'layer.setProps','params':{'ids':[layers['WHITE_INK_MASK']],'visible':False,'printable':False}},
         {'command':'document.save','params':{'path':str(scratch/'02_MASTER.vectorcraft'),'format':'vectorcraft','compress':False}}]
    jf=scratch/'native.json';jf.write_text(json.dumps(job));runvc(['run','--in',draft,'--commands',jf])
    from native_cut_preservation import preserve_native_cut_layer
    native_proof=preserve_native_cut_layer(scratch/'02_MASTER.vectorcraft',scratch/'03_CUT_ONLY.svg',scratch/'precise.vectorcraft')
    native_proof['path']='02_MASTER.vectorcraft'
    shutil.copyfile(scratch/'precise.vectorcraft',scratch/'02_MASTER.vectorcraft')
    shutil.copyfile(draft,scratch/'02_MASTER.pdf');shutil.copyfile(draft,scratch/'02_MASTER.ai')
    printdoc=fitz.open(scratch/'01_PRINT.pdf');review=fitz.open();rp=review.new_page(width=420*MM,height=297*MM)
    rp.show_pdf_page(rp.rect,printdoc,0)
    for p in paths:draw_path(rp,p,width=.13)
    review.save(scratch/'PREVIEW_NOT_FOR_CUT.pdf',garbage=4,deflate=True)
    rp.get_pixmap(dpi=100,alpha=False).save(scratch/'preview.png')
    # A direct enlarged view of both a fixed and a newly created cut.
    clip=fitz.Rect(*[v*MM for v in addition_spec['parts'][0]['placed_bounds_mm']])+(-5,-5,5,5)
    rp.get_pixmap(matrix=fitz.Matrix(4,4),clip=clip,alpha=False).save(scratch/'cut_detail.png')
    bounds=[min(p['placed_bounds_mm'][0] for p in parts),min(p['placed_bounds_mm'][1] for p in parts),
            max(p['placed_bounds_mm'][2] for p in parts),max(p['placed_bounds_mm'][3] for p in parts)]
    spec=dict(canvas_mm=[420,297],pieces=len(parts),closed_contours=len(paths),
        minimum_gap_mm=geometry['min_existing_gap_mm'],occupied_bounds_mm=bounds,
        occupied_rectangle_area_mm2=(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),
        layout_method='fixed-user-reference-plus-reviewed-scrap-only',minimum_page_margin_mm=8,
        artwork_scale=1,max_rigid_export_deviation_mm=0,physical_cut_test=False,
        white_ink_policy='Original source has no white plate. RIP alpha underbase required for those images.',
        ai_format='PDF-compatible layered master; original image pixels and cutting vectors retained',
        native_artwork_ppi='Original embedded image pixels retained',
        fixed_reference_sha256=geometry['sha256'],fixed_parts=26,parts=parts,
        baseline_geometry_exceptions=exceptions,new_part_count=len(added))
    spec['native_cut_preservation']=native_proof
    from verify_a3_release import compare_geometry
    spec['max_rigid_export_deviation_mm']=compare_geometry(scratch/'03_CUT_ONLY.pdf',spec)
    verify_fixed_source(ROOT,cfg,spec)
    check_page_geometry(parts,paths)
    (scratch/'validation.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    (scratch/'README.md').write_text('# 3페이지 · 사용자 고정 원본 + 자투리 추가\n\n![배치](preview.png)\n\n기존26조각/73폐곡선과 그림·파란 기준선은 원본 좌표 그대로입니다. 렘샤·적매화검·마가다락방 제로 합본은 스탠드와 일반 키링이 각각 하나씩 들어갑니다. 무한이는 스탠드 세 세트와 일반 키링 네 개입니다. 일반 키링에는 위쪽에 지름 2.5mm 구멍이 하나씩 있습니다.\n\n인쇄소에는 [3페이지 인쇄 PNG와 칼선 AI](../../../../print_delivery/page03)를 함께 전달하세요. 100% 배율로 파란 외곽선을 맞추고 빨간 레이어만 재단합니다. 이 폴더에는 편집 원본이 있습니다. 백색이 없는 그림은 RIP에서 백색 설정이 필요합니다.\n\n원본에 있던3쌍의3mm 미만 간격 및8개의8mm 미만 여백은 변경하지 않았고 validation.json에 따로 기록했습니다. 추가 도안의 간격은3mm 이상, 여백은8mm 이상입니다. 별받침·고리·돌기는 원본 벡터복제, 새 캐릭터 외곽은 실측 여백과 곡선 형태를 재현했습니다. 원본 제작프로그램의 작업 이력을 복원한 것은 아닙니다. 실제 가공·끼움은 미검증입니다.\n',encoding='utf-8')
    folder=ROOT/'output'/cfg['folder'];folder.mkdir(parents=True,exist_ok=True)
    from verify_repository import PAGE_FILES
    for name in PAGE_FILES:shutil.copyfile(scratch/name,folder/name)
    manifest=json.loads((ROOT/'output/a3_release/manifest.json').read_text());manifest['groups']['11_ascent_remaining/3T']=[{'folder':cfg['folder'],'pieces':len(parts),'contours':len(paths)}]
    manifest['revision']=CONFIG['revision'];(ROOT/'output/a3_release/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    verify_frozen_pages(ROOT,cfg)
    print(json.dumps({'fixed_parts':26,'new_parts':len(added),'total_parts':len(parts),'closed_contours':len(paths),'folder':str(folder)},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
