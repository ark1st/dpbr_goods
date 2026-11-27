"""Validate A3 artifacts against source contours after rigid placement."""
from pathlib import Path
import sys,json,zipfile,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon
from build_a3_release import polygon_of,extract_layers,MM,CONFIG
from verify_laser_paths import contours,native_pdf
from artifact_hash import artifact_sha256

def compare_geometry(file,spec):
    if file.name=='03_CUT_ONLY.pdf':doc=fitz.open(file)
    else:doc=extract_layers(file,['LASER_CUT'])
    assert len(doc)==1 and abs(doc[0].rect.width/MM-420)<.01 and abs(doc[0].rect.height/MM-297)<.01,file
    actual=[polygon_of(s).buffer(0) for d in doc[0].get_drawings() for s in contours(d)]
    expected=[Polygon(q) for p in spec['parts'] for q in p['expected_paths']]
    assert len(actual)==len(expected),(file,len(actual),len(expected))
    remaining=set(range(len(actual)));maximum=0
    for e in expected:
        choices=[i for i in remaining if all(abs(x-y)<.01 for x,y in zip(e.bounds,actual[i].bounds))]
        assert choices,(file,'missing original path',e.bounds)
        delta,i=min((e.boundary.hausdorff_distance(actual[i].boundary),i) for i in choices)
        assert delta<=.002,(file,'changed mechanical geometry',delta)
        remaining.remove(i);maximum=max(maximum,delta)
    return maximum

def len_slot_counts(file,thickness):
    """Count nominal vs kerf-compensated Len slots among the actual cut paths."""
    import numpy as np
    from build_a3_release import len_slot_fit
    doc=fitz.open(file);nominal=(18.8,float(thickness.removesuffix('T')));drawn=len_slot_fit(thickness)
    counts={'nominal':0,'compensated':0}
    for d in doc[0].get_drawings():
        for s in contours(d):
            c=np.array(polygon_of(s).buffer(0).minimum_rotated_rectangle.exterior.coords)
            size=sorted([math.hypot(*(c[1]-c[0])),math.hypot(*(c[2]-c[1]))],reverse=True)
            for key,ref in [('nominal',nominal),('compensated',drawn)]:
                if all(abs(a-b)<.005 for a,b in zip(size,ref)):counts[key]+=1
    return counts

def main(check_zips=True,check_native=True):
    out=ROOT/'output';base=out/'a3_release';manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    wanted=CONFIG['current_groups']
    reviewed=json.loads((ROOT/'configs/a3_placements.json').read_text(encoding='utf-8'))['groups']
    assert set(manifest['groups'])==set(wanted),'Incomplete A3 release'
    assert set(reviewed)==set(wanted),'Incomplete reviewed layout inventory'
    assert CONFIG['include_test_pieces'] is False and manifest['test_pieces_included'] is False
    records=[];selected_parts=[]
    for group,pages in manifest['groups'].items():
        assert sum(p['pieces'] for p in pages)==wanted[group]
        assert len(pages)==1
        protected_count=0;ids=[]
        for page in pages:
            folder=out/page['folder'];spec=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
            assert spec['canvas_mm']==[420,297] and spec['artwork_scale']==1
            assert spec['pieces']==page['pieces'] and spec['closed_contours']==page['contours']
            assert spec['minimum_gap_mm']>=2.998
            planned={r['id']:r for r in reviewed[group]}
            assert set(planned)=={p['id'] for p in spec['parts']}
            for p in spec['parts']:
                r=planned[p['id']]
                assert p['rotation_degrees']==r['rotation_degrees'],(group,p['id'],'Changed reviewed rotation')
                assert max(abs(a-b) for a,b in zip(p['placed_bounds_mm'][:2],[r['x'],r['y']]))<.0001
                assert max(abs(a-b) for a,b in zip(p['source_bounds_mm'],r['source_bounds_mm']))<.0001
            if group.startswith(('05_len/','06_len_pad/','07_len_origin/')):
                assert spec['layout_method']=='15-degree contour nesting'
                assert all(p['rotation_degrees']%15==0 and p.get('rotated_origin_mm') is not None for p in spec['parts'])
            protected_count+=sum(p['protected_original'] for p in spec['parts'])
            ids.extend(p['id'] for p in spec['parts'])
            if group in CONFIG['selected_primary_groups']:selected_parts.extend(spec['parts'])
            for p in spec['parts']:
                if p['id'].startswith('len_dot_'):
                    meta=p['design_metadata'];t=float(group.split('/')[-1].removesuffix('T'))
                    assert meta['art_height_mm']==50 and meta['tab_width_mm']==18
                    assert abs(meta['tab_depth_mm']-(t-.4))<.0001
                    assert meta['common_base_slot_mm']==[18.8,t]
                    from build_a3_release import len_slot_fit
                    assert meta['compensated_base_slot_mm']==list(len_slot_fit(group.split('/')[-1]))
            changes={name:compare_geometry(folder/name,spec) for name in ['03_CUT_ONLY.pdf','02_MASTER.pdf','02_MASTER.ai']}
            if group.startswith(('05_len/','06_len_pad/','07_len_origin/')):
                slots=len_slot_counts(folder/'03_CUT_ONLY.pdf',group.split('/')[-1])
                expected_slots=9 if group.startswith('07_len_origin/') else 8
                assert slots=={'nominal':0,'compensated':expected_slots},(group,'Len slot fit compensation',slots)
            if check_native:
                native=folder/'02_MASTER.vectorcraft'
                rel=native.relative_to(out).as_posix()
                cached=ROOT/'tmp/laser_preflight'/(hashlib.sha256(rel.encode()).hexdigest()[:16]+'.pdf')
                if not cached.exists() or cached.stat().st_mtime<native.stat().st_mtime:
                    cached.parent.mkdir(parents=True,exist_ok=True)
                    assert native_pdf(native,cached)
                changes['02_MASTER.vectorcraft']=compare_geometry(cached,spec)
            images=[]
            for name in ['01_PRINT_300ppi.png','04_WHITE_INK_MASK_300ppi.png']:
                p=folder/name
                with Image.open(p) as im:
                    assert im.size==tuple(math.ceil(x*300/25.4) for x in [420,297]),(p,im.size)
                    assert im.mode=='RGBA' and all(abs(x-300)<.1 for x in im.info['dpi'])
                    images.append({'file':str(p.relative_to(out)),'pixels':im.size})
            # Pixel geometry of the authoritative print PDF and previewed master.
            a=extract_layers(folder/'02_MASTER.pdf',['PRINT_ARTWORK','CORNER_REFERENCE'])
            b=fitz.open(folder/'01_PRINT.pdf')
            ap=a[0].get_pixmap(matrix=fitz.Matrix(1,1),alpha=True)
            bp=b[0].get_pixmap(matrix=fitz.Matrix(1,1),alpha=True)
            assert ap.samples==bp.samples,(folder,'master print content differs')
            files=[p for p in folder.iterdir() if p.is_file()]
            assert all(p.stat().st_size<100*1024*1024 for p in files),(folder,'oversize artifact')
            records.append({'folder':page['folder'],'pieces':spec['pieces'],'contours':spec['closed_contours'],
                            'max_export_deviation_mm':changes,'png':images,
                            'sha256':{p.name:artifact_sha256(p) for p in files}})
        assert len(ids)==len(set(ids)),group
        assert not any('fit' in x.lower() or 'test' in x.lower() for x in ids),(group,'Test pieces are prohibited')
        if 'extra' in group:
            assert protected_count==30
            assert set(CONFIG['linked_allocation']['02_extra_sheet']).issubset(ids)
            assert not set(ids)&set(CONFIG['excluded_brand_parts'][group.split('/')[-1]])
        if group=='04_ascent_cadena':assert set(ids)==set(CONFIG['cadena_source_part_ids'])
        if group.startswith('06_len_pad/'):
            t=group.split('/')[-1]
            assert set(ids)=={f'len_pad_{t}_{i:02}' for i in range(1,8)}
            assert sum(p['contours'] for p in pages)==15
        if group.startswith('07_len_origin/'):
            t=group.split('/')[-1]
            assert set(ids)=={f'len_origin_{t}_{i:02}' for i in range(1,9)}
            assert sum(p['contours'] for p in pages)==17
            assert sum(p['pieces'] for p in pages)==8 and len(ids)==8
        if group.startswith('05_len/'):
            t=group.split('/')[-1]
            assert sum(x.startswith(f'len_{t}_') for x in ids)==7
            assert sum(x.startswith(f'len_dot_{t}_') for x in ids)==1
            assert set(CONFIG['linked_allocation']['05_len']).issubset(ids)
        # Exactly four assigned keyrings on each page, never duplicates or extra designs.
        keyids=sum(CONFIG['linked_allocation'].values(),[])
        expected_keys=CONFIG['linked_allocation'].get(group.split('/')[0],[])
        assert sorted(x for x in ids if x in keyids)==sorted(expected_keys)
        assert sorted(x for x in ids if x.startswith('ascent_'))==sorted(CONFIG['cross_sheet_cadena_allocation'].get(group,[]))
    selected_ids=[p['id'] for p in selected_parts]
    assert sorted(selected_ids)==CONFIG['primary_inventory'] and len(set(selected_ids))==56
    assert sorted(x for x in selected_ids if x.startswith('ascent_'))==sorted(CONFIG['cadena_source_part_ids'])
    # Subtract through-holes: this is physical material area, not bounding boxes.
    material_area=0
    for p in selected_parts:
        areas=[Polygon(q).area for q in p['expected_paths']]
        material_area+=2*max(areas)-sum(areas)
    lower_bound=math.ceil(material_area/(420*297))
    assert lower_bound==2 and len(CONFIG['selected_primary_groups'])==lower_bound
    minimum_proof={'net_material_area_mm2':material_area,'single_A3_area_mm2':420*297,
        'area_lower_bound_sheets':lower_bound,'feasible_sheets':2,'optimal_sheet_count_proven':True,
        'scope':'56 selected 3T pieces; optional PAD and 5T alternatives excluded; no scale reduction except approved DOT redesign.'}
    packages=[]
    if check_zips:
        for group in sorted(wanted):
            file=base/(group.replace('/','_')+'_A3.zip')
            with zipfile.ZipFile(file) as z:
                assert z.testzip() is None
                included={'01_PRINT_300ppi.png','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK_300ppi.png','preview.png','cut_detail.png','README.md','validation.json'}
                expected={'a3_release/README.md','a3_release/'+group.split('/')[0]+'/README.md'}
                expected.update(p['folder']+'/'+n for p in manifest['groups'][group] for n in included)
                assert len(z.namelist())==len(expected) and set(z.namelist())==expected,(file,'Missing, duplicate or extra ZIP members')
                for name in z.namelist():
                    if name.endswith('/'):continue
                    current=out/name
                    assert current.is_file(),(file,name)
                    assert artifact_sha256(current,z.read(name))==artifact_sha256(current),(file,name,'stale ZIP entry')
            assert file.stat().st_size<100*1024*1024,file
            packages.append({'file':file.relative_to(out).as_posix(),'bytes':file.stat().st_size,'sha256':artifact_sha256(file)})
        assert len(packages)==len(wanted),len(packages)
    result={'checked_pages':len(records),'native_geometry_checked':check_native,'records':records,'packages':packages,'errors':[],
            'selected_primary_pages':2,'selected_thickness':'3T','optional_PAD_pages_per_thickness':1,
            'minimum_sheet_proof':minimum_proof,
            'source_artwork_scale':1,'physical_cut_test':False,'test_pieces_included':False,
            'limitations':['Software checks do not validate physical kerf, material thickness or printer registration.',
                           'Only Cadena first-row four panels and one original base are selected; other Ascent pieces are retired from this print run.',
                           'Ascent paired slots have original ~0.195mm vertical stagger; not silently aligned.',
                           'Native editing state is in .vectorcraft. Compact .ai retains PDF-compatible vector layers.']}
    (base/'A3_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'a3_pages_checked':len(records),'a3_packages':len(packages),'errors':0}),flush=True)
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--skip-native',action='store_true')
    main(check_native=not parser.parse_args().skip_native)
