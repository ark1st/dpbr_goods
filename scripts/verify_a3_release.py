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

def main(check_zips=True,check_native=True):
    out=ROOT/'output';base=out/'a3_release';manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    wanted=CONFIG['current_groups']
    reviewed=json.loads((ROOT/'configs/a3_placements.json').read_text(encoding='utf-8'))['groups']
    assert set(manifest['groups'])==set(wanted),'Incomplete A3 release'
    assert set(reviewed)==set(wanted),'Incomplete reviewed layout inventory'
    assert CONFIG['include_test_pieces'] is False and manifest['test_pieces_included'] is False
    from ascent_size_audit import measure
    fixed=json.loads((ROOT/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts'];sized=[]
    for ident in CONFIG['ascent_remaining']['part_ids']:
        row=fixed[ident];paths=[{'poly':polygon_of(p)} for p in row['paths']]
        sized.append({'id':ident,'bounds':row['source_bounds_mm'],'paths':paths,'poly':max((p['poly'] for p in paths),key=lambda p:p.area)})
    source_size_check=measure(sized)
    saved_size=json.loads((base/'11_ascent_remaining/SIZE_VERIFICATION.json').read_text(encoding='utf-8'))
    assert not saved_size['geometry_size_errors'] and not saved_size['physical_cut_or_fit_test']
    assert [p['id'] for p in saved_size['parts']]==[p['id'] for p in source_size_check['parts']]
    records=[];selected_parts=[];selected_by_group={}
    for group,pages in manifest['groups'].items():
        assert sum(p['pieces'] for p in pages)==wanted[group]
        assert len(pages)==CONFIG.get('pages_per_group',{}).get(group,1)
        protected_count=0;ids=[]
        for page_index,page in enumerate(pages):
            folder=out/page['folder'];spec=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
            assert spec['canvas_mm']==[420,297] and spec['artwork_scale']==1
            assert spec['pieces']==page['pieces'] and spec['closed_contours']==page['contours']
            assert spec['minimum_gap_mm'] is None or spec['minimum_gap_mm']>=2.998
            group_rows=reviewed[group]
            if group_rows and isinstance(group_rows[0],list):group_rows=group_rows[page_index]
            planned={r['id']:r for r in group_rows}
            assert set(planned)=={p['id'] for p in spec['parts']}
            for p in spec['parts']:
                r=planned[p['id']]
                assert p['rotation_degrees']==r['rotation_degrees'],(group,p['id'],'Changed reviewed rotation')
                assert max(abs(a-b) for a,b in zip(p['placed_bounds_mm'][:2],[r['x'],r['y']]))<.0001
                assert max(abs(a-b) for a,b in zip(p['source_bounds_mm'],r['source_bounds_mm']))<.0001
            if group.startswith(('05_len/','06_len_pad/')):
                assert spec['layout_method']=='15-degree contour nesting'
                assert all(p['rotation_degrees']%15==0 and p.get('rotated_origin_mm') is not None for p in spec['parts'])
            protected_count+=sum(p['protected_original'] for p in spec['parts'])
            ids.extend(p['id'] for p in spec['parts'])
            if group in CONFIG['selected_primary_groups']:
                selected_parts.extend(spec['parts']);selected_by_group.setdefault(group,[]).extend(spec['parts'])
            for p in spec['parts']:
                if p['id'].startswith('len_dot_'):
                    meta=p['design_metadata'];t=float(group.split('/')[-1].removesuffix('T'))
                    assert meta['art_height_mm']==50 and meta['tab_width_mm']==18
                    assert abs(meta['tab_depth_mm']-(t-.4))<.0001
                    assert meta['common_base_slot_mm']==[18.8,t]
            changes={name:compare_geometry(folder/name,spec) for name in ['03_CUT_ONLY.pdf','02_MASTER.pdf','02_MASTER.ai']}
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
        if group.startswith('05_len/'):
            t=group.split('/')[-1]
            assert sum(x.startswith(f'len_{t}_') for x in ids)==7
            assert sum(x.startswith(f'len_dot_{t}_') for x in ids)==1
            assert set(CONFIG['linked_allocation']['05_len']).issubset(ids)
        # Exactly four assigned keyrings on each page, never duplicates or extra designs.
        keyids=sum(CONFIG['linked_allocation'].values(),[])
        expected_keys=CONFIG['linked_allocation'].get(group.split('/')[0],[])
        assert sorted(x for x in ids if x in keyids)==sorted(expected_keys)
        expected_ascent=CONFIG['ascent_remaining']['part_ids'] if group=='11_ascent_remaining/3T' else CONFIG['cross_sheet_cadena_allocation'].get(group,[])
        assert sorted(x for x in ids if x.startswith('ascent_'))==sorted(expected_ascent)
        if group=='11_ascent_remaining/3T':
            assert set(ids)==set(expected_ascent) and not set(ids)&set(CONFIG['cadena_source_part_ids'])
            assert 'ascent_31' not in ids
    selected_ids=[p['id'] for p in selected_parts]
    assert sorted(selected_ids)==CONFIG['primary_inventory'] and len(set(selected_ids))==CONFIG['selected_primary_parts']
    from optional_sheet_policy import assess
    fill=assess(ROOT)
    saved_fill=json.loads((base/'OPTIONAL_FILL_ASSESSMENT.json').read_text(encoding='utf-8'))
    assert saved_fill['allocation']==fill['allocation'] and saved_fill['deferred']==fill['deferred'],'Stale optional-fill decision'
    for old,new in [(saved_fill['candidate_sets'][k],v) for k,v in fill['candidate_sets'].items()]+[(saved_fill['ascent_with_PAD']['capacity_bound'],fill['ascent_with_PAD']['capacity_bound'])]:
        assert old['impossible_proven']==new['impossible_proven'] and old['parts']==new['parts']
        for key in ['expanded_piece_area_lower_mm2','expanded_container_area_upper_mm2','excess_area_mm2']:
            assert abs(old[key]-new[key])<.001,('Stale optional capacity bound',key)
    assert saved_fill['ascent_with_PAD']['feasible_two_page_layout_found'] is False
    assert saved_fill['ascent_with_PAD']['mathematical_impossibility_proven'] is False
    assert len(manifest['groups']['02_extra_sheet/3T'])+len(manifest['groups']['05_len/3T'])==2
    selected_yanggum=sorted(x for x in selected_ids if x.startswith('yanggum_'))
    assert selected_yanggum==sorted(CONFIG['optional_fill_policy']['candidate_sets']['yanggum_3T'])
    assert not any(x.startswith('len_pad_') for x in selected_ids),'Deferred PAD must not enter the print job'
    for group,ids in CONFIG['optional_fill_allocation'].items():
        assert sorted(p['id'] for p in selected_by_group[group] if p['id'].startswith('yanggum_'))==sorted(ids)
    assert sorted(x for x in selected_ids if x.startswith('ascent_'))==sorted(CONFIG['cadena_source_part_ids']+CONFIG['ascent_remaining']['part_ids'])
    # Subtract through-holes: this is physical material area, not bounding boxes.
    material_area=0
    for p in selected_parts:
        areas=[Polygon(q).area for q in p['expected_paths']]
        material_area+=2*max(areas)-sum(areas)
    batches=[]
    for name,groups in CONFIG['separate_print_batches'].items():
        batch_parts=[p for g in groups for p in selected_by_group[g]]
        net=sum(2*max(areas)-sum(areas) for p in batch_parts for areas in [[Polygon(q).area for q in p['expected_paths']]])
        feasible=sum(len(manifest['groups'][g]) for g in groups);lower=math.ceil(net/(420*297))
        assert feasible==lower,(name,'Sheet count not proven minimal')
        batches.append({'name':name,'parts':len(batch_parts),'net_material_area_mm2':net,'area_lower_bound_sheets':lower,'feasible_sheets':feasible})
    lower_bound=sum(b['area_lower_bound_sheets'] for b in batches)
    minimum_proof={'net_material_area_mm2':material_area,'single_A3_area_mm2':420*297,
        'area_lower_bound_sheets':lower_bound,'feasible_sheets':CONFIG['selected_primary_pages'],'optimal_sheet_count_proven':True,'separate_batches':batches,
        'scope':f"{CONFIG['selected_primary_parts']} selected 3T pieces. Yanggeum is included in the existing mixed pair, PAD deferred. Ascent remaining stays separate; minimum proved within that separation. 5T and standalone reference layouts excluded."}
    packages=[]
    if check_zips:
        for group in sorted(wanted):
            file=base/(group.replace('/','_')+'_A3.zip')
            with zipfile.ZipFile(file) as z:
                assert z.testzip() is None
                included={'01_PRINT_300ppi.png','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK_300ppi.png','preview.png','cut_detail.png','README.md','validation.json'}
                expected={'a3_release/README.md','a3_release/'+group.split('/')[0]+'/README.md'}
                expected.update(rel for rel in CONFIG.get('support_files',[]) if rel.startswith('a3_release/'+group.split('/')[0]+'/') or rel=='a3_release/OPTIONAL_FILL_ASSESSMENT.json')
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
            'ascent_source_size_verification':source_size_check,
            'selected_primary_pages':CONFIG['selected_primary_pages'],'selected_thickness':'3T','optional_fill_assessment':fill,'PAD_print_pages':0,
            'minimum_sheet_proof':minimum_proof,
            'source_artwork_scale':1,'physical_cut_test':False,'test_pieces_included':False,
            'limitations':['Software checks do not validate physical kerf, material thickness or printer registration.',
                           'All requested Ascent pieces included; original blank panel31 excluded by the user. Size verified digitally at1:1, not physically cut-tested.',
                           'Ascent paired slots have original ~0.195mm vertical stagger; not silently aligned.',
                           'Native editing state is in .vectorcraft. Compact .ai retains PDF-compatible vector layers.']}
    (base/'A3_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'a3_pages_checked':len(records),'a3_packages':len(packages),'errors':0}),flush=True)
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--skip-native',action='store_true')
    main(check_native=not parser.parse_args().skip_native)
