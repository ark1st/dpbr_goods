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

def verify_cut_variant(folder, name, variant, validation):
    """Require the same drawing operations and order as the parent cutter, minus whole pieces."""
    from shapely.geometry import Polygon
    removed=set(variant['excluded_outer_ids'])
    parts={part['id']:part for part in validation['parts']}
    assert len(removed)==len(variant['excluded_outer_ids']) and removed<=parts.keys()
    excluded=[Polygon(max(parts[key]['expected_paths'],key=lambda coords:Polygon(coords).area)) for key in removed]
    order=validation['cut_order_source_indices']
    with fitz.open(folder/'03_CUT_ONLY.ai') as parent, fitz.open(folder/name) as variant_doc:
        assert len(parent)==len(variant_doc)==1
        page,child=parent[0],variant_doc[0]
        assert (child.mediabox,child.cropbox,child.rotation)==(page.mediabox,page.cropbox,page.rotation)
        assert [(g['name'],g['on']) for g in variant_doc.get_ocgs().values()]==[('LASER_CUT',True)]
        assert not child.get_images() and not child.get_text().strip()
        selected=[]
        for drawing,index in zip(page.get_drawings(),order,strict=True):
            source=validation['source_paths'][index]
            assert index==source['source_index']
            # Confirm the recovered cutter's actual draw order against the source index.
            path,=contours(drawing)
            actual=polygon_of(path)
            assert actual.boundary.hausdorff_distance(polygon_of(source['path']).boundary)<.002
            if f'original_{index:03}' in removed or (source['is_hole'] and
                    any(poly.contains(actual.representative_point()) for poly in excluded)):
                continue
            selected.append(drawing)
        result=child.get_drawings()
        assert len(result)==len(selected)==variant['contours']
        for original,new in zip(selected,result,strict=True):
            assert {k:v for k,v in original.items() if k!='seqno'}=={k:v for k,v in new.items() if k!='seqno'}, (name,'Changed drawing')
        assert len(parts)-len(removed)==variant['pieces']
        assert len(child.get_bboxlog())==len(result) and all(op=='stroke-path' for op,_ in child.get_bboxlog())
    return {'file':(folder/name).relative_to(ROOT/'output').as_posix(),'sha256':artifact_sha256(folder/name),
            'pieces':variant['pieces'],'contours':len(selected),'excluded_outer_ids':sorted(removed),
            'max_parent_format_deviation_mm':0.0}

def tab_footprints(old_path, new_shape):
    """Extend a 1 mm slice of each actual parent tip and compare the full resulting outline."""
    from shapely import affinity
    from shapely.geometry import Point,Polygon
    from svgpathtools import Line,parse_path
    old=polygon_of(old_path);expected=old;centers=[]
    for seg in parse_path(old_path):
        if not isinstance(seg,Line) or abs(seg.length()-17.2)>.002:
            continue
        tangent=(seg.end-seg.start)/seg.length()
        center=(seg.start+seg.end)/2;normal=tangent*1j
        inside=center+normal*.1
        if old.contains(Point(inside.real,inside.imag)):
            normal=-normal
        def rectangle(width,low,high):
            corners=[center+tangent*x+normal*y for x,y in
                     [(-width/2,low),(width/2,low),(width/2,high),(-width/2,high)]]
            return Polygon([(p.real,p.imag) for p in corners])
        assert abs(old.intersection(rectangle(19,-4.55,-4.05)).area-18*.5)<.002
        cap=old.intersection(rectangle(18.01,-1,.001))
        expected=expected.union(affinity.translate(cap,.5*normal.real,.5*normal.imag))
        centers.append(center)
    assert centers and expected.boundary.hausdorff_distance(new_shape.boundary)<.002
    assert expected.symmetric_difference(new_shape).area<.01
    return centers


def check_clear_stock(art, region):
    """Look for original artwork in the material gained/lost at each corrected mount."""
    import numpy as np
    from shapely import contains_xy
    # Sample in registration at 300ppi on the original artwork layer.
    scale=300/25.4
    clip=fitz.Rect(*(v*MM for v in region.bounds))
    pix=art[0].get_pixmap(dpi=300,clip=clip,alpha=True)
    xx,yy=np.meshgrid((np.arange(pix.width)+pix.x+.5)/scale,(np.arange(pix.height)+pix.y+.5)/scale)
    mask=contains_xy(region,xx,yy)
    assert mask.any()
    alpha=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,pix.n)[:,:,-1]
    return int(np.count_nonzero(alpha[mask]))


def verify_five_t_mount(folder,name,variant,parent_variant,validation,source):
    from itertools import combinations
    from shapely.geometry import box
    old_order=validation['cut_order_source_indices']
    parts={p['id']:p for p in validation['parts']}
    dropped={int(ident.split('_')[1]) for ident in parent_variant['excluded_outer_ids']}
    # Deterministic seven groups of 42 from the original printing plate.
    for i in dropped:
        assert i%42 in (37,38,39,40)
    keep=[i for i in old_order if i not in dropped and i%42 not in range(5,13)]
    assert len(keep)==variant['contours']==210
    fit=variant['mount_fit']
    assert fit=={'stock_mm':5.0,'kerf_mm':.2,'tab_depth_mm':5.1,'tab_width_mm':18.,'slot_mm':[17.8,4.85]}
    outer_shapes=[];slots={};tips={};changed=0;ink=0
    with fitz.open(folder/variant['parent_variant']) as baseline, fitz.open(folder/name) as corrected, extract_layers(source,['3_ARTWORK']) as art:
        page=corrected[0];before=baseline[0]
        assert len(corrected)==1 and page.mediabox==before.mediabox and page.cropbox==before.cropbox and page.rotation==before.rotation
        assert [(g['name'],g['on']) for g in corrected.get_ocgs().values()]==[('LASER_CUT',True)]
        assert not page.get_images() and len(page.get_bboxlog())==len(keep) and all(op=='stroke-path' for op,_ in page.get_bboxlog())
        for idx,a,b in zip(keep,before.get_drawings(),page.get_drawings(),strict=True):
            role=idx%42
            for k in a.keys()-{'seqno','rect','items','closePath'}:
                assert a[k]==b[k],(idx,k)
            a_path,=contours(a);b_path,=contours(b)
            old=polygon_of(a_path);new=polygon_of(b_path)
            if role<=3:
                x,y,r,t=old.bounds;cx,cy=(x+r)/2,(y+t)/2
                horizontal=r-x>t-y
                length,width=(17.8,4.85) if horizontal else (4.85,17.8)
                expected=box(cx-length/2,cy-width/2,cx+length/2,cy+width/2)
                assert new.boundary.hausdorff_distance(expected.boundary)<.002
                w,h=(17.8,5.) if horizontal else (5.,17.8)
                post=box(cx-w/2,cy-h/2,cx+w/2,cy+h/2)
                assert new.buffer(.1).covers(post) and new.buffer(.1).boundary.distance(post)>.024
                slots[idx]=new.centroid
            elif role in (31,32,33):
                centers=tab_footprints(a_path,new)
                assert len(centers)==(2 if role==33 else 1)
                tips[idx]=centers
            else:
                assert a['items']==b['items'] and a['closePath']==b['closePath'],(idx,'unexpected path change')
            if role<=3 or role in (31,32,33):
                changed+=1
                ink+=check_clear_stock(art,old.symmetric_difference(new))
            if f'original_{idx:03}' in parts:
                outer_shapes.append(new)
    assert changed==49 and len(slots)==28 and sum(map(len,tips.values()))==28
    for k in range(7):
        i=k*42
        assert abs(abs(tips[i+33][0]-tips[i+33][1])-84)<.002
        a,b=slots[i+2],slots[i+3]
        assert abs(a.distance(b)-84)<.002 and min(abs(a.x-b.x),abs(a.y-b.y))<.002
    assert ink==0,('registered artwork in changed mount material',ink)
    assert len(outer_shapes)==variant['pieces']==49
    minimum_gap=min(a.distance(b) for a,b in combinations(outer_shapes,2))
    assert minimum_gap>=2.62
    return {'file':(folder/name).relative_to(ROOT/'output').as_posix(),'sha256':artifact_sha256(folder/name),
            'contours':len(keep),'pieces':len(outer_shapes),'minimum_piece_gap_mm':minimum_gap,
            'changed_contours':changed,'slots':len(slots),'tabs':sum(map(len,tips.values())),
            'mount_fit':fit,'changed_material_ink_pixels_at_300ppi':ink,'physical_fit_test':False}


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
    for name,variant in spec.get('cut_variants',{}).items():
        if 'mount_fit' in variant:
            checks.append(verify_five_t_mount(folder,name,variant,spec['cut_variants'][variant['parent_variant']],validation,source))
        else:
            checks.append(verify_cut_variant(folder,name,variant,validation))
        with fitz.open(folder/name) as doc:
            doc[0].get_pixmap(dpi=50).save(temp/(Path(name).stem+'_ai.png'))
        rendered.append(name)
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
