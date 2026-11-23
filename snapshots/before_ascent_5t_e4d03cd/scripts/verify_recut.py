"""Full existing-print recovery audit: all curves, original alignment and ZIP."""
import json,hashlib,zipfile
from pathlib import Path
from build_a3_release import ROOT,MM,polygon_of,extract_layers
from repair_printed_plate import load_recovery,originals,exact_bounds
from verify_laser_paths import contours,native_pdf,inspect_pdf
from vector_utils import runvc
from artifact_hash import artifact_sha256
import pymupdf as fitz

def compare_contours(actual,expected,source,actual_bounds=None,source_bounds=None):
    assert len(actual)==len(expected),'Missing/extra recovery contours'
    remaining=set(range(len(actual)));worst=0;original_worst=0;hole_worst=0
    for row in expected:
        wanted=polygon_of(row['path']);choices=[i for i in remaining if all(abs(a-b)<.01 for a,b in zip(actual[i].bounds,wanted.bounds))]
        assert choices,('Recovery path shifted or resized',row['source_index'])
        delta,index=min((actual[i].boundary.hausdorff_distance(wanted.boundary),i) for i in choices)
        assert delta<.002,('Recovery format differs from reviewed curves',delta)
        original=source[row['source_index']];deviation=original.boundary.hausdorff_distance(actual[index].boundary)
        assert deviation<=.035,('Original printed alignment changed',deviation)
        if row['is_hole']:
            oldbox=source_bounds[row['source_index']] if source_bounds else original.bounds
            newbox=actual_bounds[index] if actual_bounds else actual[index].bounds
            hd=max(abs(a-b) for a,b in zip(oldbox,newbox))
            assert hd<.001,('Original hole dimensions/center changed',hd)
            hole_worst=max(hole_worst,hd)
        remaining.remove(index);worst=max(worst,delta);original_worst=max(original_worst,deviation)
    return {'max_format_deviation_mm':worst,'max_printed_source_deviation_mm':original_worst,'max_hole_bounds_deviation_mm':hole_worst}

def main(check_native=True,check_svg=True):
    spec,source,fixed=load_recovery();folder=ROOT/'output'/spec['folder']
    validation=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
    assert validation['source_sha256']==spec['source_sha256'] and validation['existing_print_only']
    assert validation['scale']==1 and validation['translation_mm']==[0,0] and validation['rotation_degrees']==0
    assert validation['print_pages_added']==0 and not validation['physical_cut_test']
    _,oldpaths=originals(source);source_polys=[polygon_of(path) for path in oldpaths];source_boxes=[exact_bounds(path) for path in oldpaths]
    expected=validation['source_paths'];assert len(expected)==spec['contours']==294
    assert len(set(validation['cut_order_source_indices']))==294
    holes=set(fixed['hole_indices']);assert set(validation['cut_order_source_indices'][:len(holes)])==holes
    checks=[];rendered=[];temp=ROOT/'tmp/recut_validation';temp.mkdir(parents=True,exist_ok=True)
    names=['03_CUT_ONLY.pdf','03_CUT_ONLY.ai']
    if check_svg:names.append('03_CUT_ONLY.svg')
    if check_native:names.append('03_CUT_ONLY.vectorcraft')
    for name in names:
        path=folder/name;target=path
        if path.suffix=='.svg':target=temp/'svg.pdf';runvc(['convert',path,target])
        elif path.suffix=='.vectorcraft':target=temp/'native.pdf';assert native_pdf(path,target)
        with fitz.open(target) as doc:
            assert len(doc)==1
            assert max(abs(a-b) for a,b in zip([doc[0].rect.width/MM,doc[0].rect.height/MM],spec['canvas_mm']))<.002
            actual_paths=[p for d in doc[0].get_drawings() for p in contours(d)]
            actual=[polygon_of(p) for p in actual_paths]
            change=compare_contours(actual,expected,source_polys,[exact_bounds(p) for p in actual_paths],source_boxes)
            pix=doc[0].get_pixmap(dpi=50,alpha=False);pix.save(temp/(path.stem+path.suffix.replace('.','_')+'.png'));rendered.append(name)
        quality=inspect_pdf(target);assert quality is not None and not quality['errors'],(name,quality)
        assert quality['outer_contours']==77 and quality['contours']==294
        checks.append({'file':spec['folder']+'/'+name,'sha256':artifact_sha256(path),**change,'contours':294,'pieces':77})
    # CI has no VectorCraft CLI; the all-format local audit includes both native
    # exports. CI uses the PDF/AI path checks in verify_laser_paths --pdf-only.
    file=folder/'RECUT_ONLY.zip'
    with zipfile.ZipFile(file) as archive:
        wanted=set(spec['files'])-{'RECUT_ONLY.zip'}
        assert len(archive.namelist())==len(wanted) and set(archive.namelist())==wanted and archive.testzip() is None
        for name in wanted:assert artifact_sha256(folder/name,archive.read(name))==artifact_sha256(folder/name)
    report={'mode':'all-formats' if check_native and check_svg else 'pdf-ai-only','source_sha256':spec['source_sha256'],'records':checks,'packages':[{'file':file.relative_to(ROOT/'output').as_posix(),'sha256':artifact_sha256(file)}],
        'rendered_formats':rendered,'pieces':77,'contours':294,'print_pages_added':0,'existing_print_only':True,
        'errors':[],'physical_cut_test':False,'limitations':validation['limitations']}
    (ROOT/'output/recut_only/VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'recovery_cut_formats_checked':len(checks),'source_loops_preserved':294,'print_pages_added':0,'errors':0}),flush=True)
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--pdf-only',action='store_true');args=parser.parse_args()
    main(check_native=not args.pdf_only,check_svg=not args.pdf_only)
