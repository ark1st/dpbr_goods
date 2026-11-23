"""Validate A3 artifacts against source contours after rigid placement."""
from collections import Counter
from pathlib import Path
import sys,json,zipfile,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Point, Polygon
from build_a3_release import polygon_of,extract_layers,shifted_poly,MM,CONFIG
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

def verify_chain_holes(part):
    """Verify the metadata against both transformed 4 mm cutting circles."""
    meta=part['design_metadata'];ident=part['id']
    centers=meta['hole_centers_mm'];art=meta['art_rect_mm']
    assert len(centers)==2 and all(len(center)==2 for center in centers),(ident,'Missing top/bottom hole centers')
    assert meta['hole_diameter_mm']==4,(ident,'Unexpected connector hole diameter')
    source_top,source_bottom=sorted(centers,key=lambda center:center[1])
    assert source_top[1]<art[1]<art[3]<source_bottom[1],(ident,'Holes must be above and below the artwork')
    assert part['path_count']==len(part['expected_paths'])==3,(ident,'Expected one outer and two hole contours')
    paths=sorted((Polygon(p) for p in part['expected_paths']),key=lambda p:p.area,reverse=True)
    outer,*holes=paths
    assert all(outer.contains(hole) for hole in holes) and holes[0].disjoint(holes[1]),(ident,'Uncontained or overlapping connector holes')
    place={'piece':{'bounds':part['source_bounds_mm']},'rotation':part['rotation_degrees'],
           'x':part['placed_bounds_mm'][0],'y':part['placed_bounds_mm'][1],
           'rotated_origin':part.get('rotated_origin_mm')}
    predicted=[shifted_poly(Point(*center),place).buffer(2,quad_segs=64) for center in centers]
    for expected in predicted:
        distance,index=min((hole.boundary.hausdorff_distance(expected.boundary),i) for i,hole in enumerate(holes))
        assert distance<.025,(ident,'Moved or resized connector hole',distance)
        holes.pop(index)

def verify_personal_inventory(config,selected_by_group):
    allocation=config.get('personal_fill_allocation',{})
    if not allocation:return
    selected=[p['id'] for parts in selected_by_group.values() for p in parts]
    policy=config['personal_fill_policy']
    expected_personal=policy['stand_pieces']+policy['keyring_pieces']
    pad_ids={ident for ids in config.get('pad_fill_allocation',{}).values() for ident in ids}
    logo_ids={ident for ids in config.get('logo_fill_allocation',{}).values() for ident in ids}
    assert set(allocation)<=set(selected_by_group),'Personal pieces must be on selected primary sheets'
    personal=[ident for ids in allocation.values() for ident in ids]
    assert len(personal)==len(set(personal))==expected_personal,'Changed personal allocation'
    assert set(personal)==set(policy['new_part_ids']),'Unexpected personal piece IDs'
    baseline=policy['baseline_ids']
    personal_ids=set(personal);baseline_ids=set(baseline)
    assert len(baseline)==len(baseline_ids)==84,'Changed baseline inventory'
    assert sum(map(len,[personal_ids,pad_ids,baseline_ids,logo_ids]))==len(personal_ids|pad_ids|baseline_ids|logo_ids),'Overlapping production inventories'
    assert len(selected)==len(set(selected))==config['selected_primary_parts']==84+expected_personal+len(pad_ids)+len(logo_ids),'Changed primary inventory'
    assert set(selected)-personal_ids-pad_ids-logo_ids==baseline_ids,'Changed baseline inventory'
    counts=Counter();stand_pairs=Counter()
    for group,parts in selected_by_group.items():
        actual=[p for p in parts if p['id'] in personal_ids]
        assert {p['id'] for p in actual}==set(allocation.get(group,[])),(group,'Changed personal allocation')
        for p in actual:
            meta=p['design_metadata'];kind=meta['part']
            counts[kind]+=1
            if kind=='keyring':
                assert p['source'].endswith('_keyring'),(p['id'],'Unexpected keyring source')
                verify_chain_holes(p)
            else:
                assert kind in ('character','base') and p['source'].endswith('_stand'),(p['id'],'Unexpected stand role or source')
                assert p['path_count']==len(p['expected_paths'])=={'character':1,'base':2}[kind],(p['id'],'Changed stand contours')
                verify_stand_support(p)
                stand_pairs[(p['source'],meta['nickname'],meta['mode'],kind)]+=1
    stand_sets=policy['stand_pieces']//2
    assert counts=={'keyring':policy['keyring_pieces'],'character':stand_sets,'base':stand_sets},counts
    for (source,nickname,mode,kind),count in stand_pairs.items():
        assert count==1 and stand_pairs[(source,nickname,mode,{'character':'base','base':'character'}[kind])]==1,(source,nickname,mode,'Unmatched stand pair')
    paired=[p for parts in selected_by_group.values() for p in parts if p['id'] in personal_ids
            and p['design_metadata']['part']=='character' and len(p['design_metadata'].get('components',[]))==2]
    assert {p['design_metadata']['nickname'] for p in paired}==set(policy['combined_zero_stands']),'Changed Zero pair inventory'

def verify_logo_inventory(config,selected_by_group,canonical):
    allocation=config.get('logo_fill_allocation',{})
    aliases=[ident for ids in allocation.values() for ident in ids]
    assert len(aliases)==len(set(aliases)) and all(i.startswith('danba_logo_fill_') for i in aliases)
    if not aliases:return
    source=canonical['danba_logo_smooth']
    assert len(source['paths'])==2
    for group,parts in selected_by_group.items():
        actual=[p for p in parts if p['id'] in aliases]
        assert Counter(p['id'] for p in actual)==Counter(allocation.get(group,[])),(group,'Changed logo allocation')
        for p in actual:
            assert p['scale']==1 and p['path_count']==len(p['expected_paths'])==2
            assert max(abs(a-b) for a,b in zip(p['source_bounds_mm'],source['source_bounds_mm']))<.0001
            place={'piece':{'bounds':p['source_bounds_mm']},'rotation':p['rotation_degrees'],
                   'x':p['placed_bounds_mm'][0],'y':p['placed_bounds_mm'][1],
                   'rotated_origin':p.get('rotated_origin_mm')}
            for path,actual_path in zip(source['paths'],p['expected_paths'],strict=True):
                expected_path=shifted_poly(polygon_of(path),place)
                assert expected_path.boundary.hausdorff_distance(Polygon(actual_path).boundary)<.002,(p['id'],'Changed logo contour or hole')
    assert set(allocation)<=set(selected_by_group)

def verify_pad_inventory(config,selected_by_group,canonical=None):
    """Keep a single full-size 3T PAD kit in its reviewed production groups."""
    allocation=config.get('pad_fill_allocation',{})
    observed=[]
    for group,parts in selected_by_group.items():
        actual=[p for p in parts if p['id'].startswith('len_pad_')]
        assert Counter(p['id'] for p in actual)==Counter(allocation.get(group,[])),(group,'Changed PAD allocation (missing, duplicate or wrong sheet)')
        observed.extend(actual)
    if not allocation:return
    expected={f'len_pad_3T_{i:02}' for i in range(1,8)}
    variants=config.get('pad_variant_sources',{})
    assert all(alias==source+'_safe' and source in expected for alias,source in variants.items()),'Invalid PAD production variant mapping'
    assert len(set(variants.values()))==len(variants),'Multiple variants of the same PAD piece'
    allocated=[ident for ids in allocation.values() for ident in ids]
    assert set(variants)<=set(allocated),'Unallocated PAD production variant'
    policy=config['optional_fill_policy']['candidate_sets']['len_pad_3T']
    assert len(policy)==7 and set(policy)==expected,'PAD policy must identify the seven original 3T pieces'
    assert all(group in selected_by_group and group.endswith('/3T') and not group.startswith('06_len_pad/')
               for group in allocation),'PAD fillers must appear on selected mixed 3T sheets'
    assert Counter(variants.get(p['id'],p['id']) for p in observed)==Counter(expected),'Print the full 3T PAD kit exactly once'
    assert all(p['scale']==1 and p['path_count']==len(p['expected_paths']) for p in observed),'PAD scale or contour count changed'
    assert sum(p['path_count'] for p in observed)==15,'Expected 15 original PAD cut contours'
    if canonical is None:return
    for p in observed:
        source=canonical[p['id']]
        if p['id'] in variants:
            assert variants[p['id']] in canonical,(p['id'],'Missing independent PAD original')
            assert (p.get('design_metadata') or {}).get('redesign_source_id')==variants[p['id']],(p['id'],'Changed PAD source identity')
            original=canonical[variants[p['id']]]
            assert len(source['paths'])==len(original['paths']),(p['id'],'Changed PAD source contour count')
            for approved,prior in zip(source['paths'][:-1],original['paths'][:-1],strict=True):
                assert polygon_of(approved).boundary.hausdorff_distance(polygon_of(prior).boundary)<.002,(p['id'],'Changed PAD original hole or slot')
            assert polygon_of(source['paths'][-1]).buffer(.002).covers(polygon_of(original['paths'][-1])),(p['id'],'PAD redesigned exterior excludes original area')
        assert max(abs(a-b) for a,b in zip(p['source_bounds_mm'],source['source_bounds_mm']))<.0001,(p['id'],'Changed PAD source dimensions')
        place={'piece':{'bounds':p['source_bounds_mm']},'rotation':p['rotation_degrees'],
               'x':p['placed_bounds_mm'][0],'y':p['placed_bounds_mm'][1],
               'rotated_origin':p.get('rotated_origin_mm')}
        for path,actual in zip(source['paths'],p['expected_paths'],strict=True):
            expected_path=shifted_poly(polygon_of(path),place)
            assert expected_path.boundary.hausdorff_distance(Polygon(actual).boundary)<.002,(p['id'],'Changed original PAD geometry')

def verify_stand_support(part):
    """Measure the exported load path and mechanical interfaces in source axes."""
    from shapely import affinity
    from chain_keyring_parts import stand_axis_width
    meta=part['design_metadata'];ident=part['id']
    x0,y0,_,_=part['source_bounds_mm'];rx,ry=part['rotated_origin_mm']
    px,py=part['placed_bounds_mm'][:2]
    paths=[affinity.translate(affinity.rotate(affinity.translate(Polygon(q),-px+rx,-py+ry),
            part['rotation_degrees'],origin=(0,0)),x0,y0) for q in part['expected_paths']]
    paths.sort(key=lambda p:p.area,reverse=True);outer=paths[0]
    if meta['part']=='base':
        assert len(paths)==2 and meta['size_mm']==[72,28] and meta['slot_mm']==[18.8,3],(ident,'Changed base interface')
        slot=paths[1];sx,sy=meta['slot_center_mm']
        assert abs(slot.centroid.x-sx)<.002 and abs(slot.centroid.y-sy)<.002,(ident,'Moved stand slot')
        assert max(abs(a-b) for a,b in zip([slot.bounds[2]-slot.bounds[0],slot.bounds[3]-slot.bounds[1]],[18.8,3]))<.005,(ident,'Resized stand slot')
        return
    assert len(paths)==1 and meta['tab_width_mm']==18 and abs(meta['tab_depth_mm']-2.6)<.0001,(ident,'Changed stand tab')
    components=meta['components']
    assert len(components) in (1,2) and all(c['art_height_mm']==60 for c in components),(ident,'Changed original image height')
    if len(components)==2:
        assert {c['mode'].split(' ')[0] for c in components}=={'알파','베타'},(ident,'Missing Zero mode')
        assert components[1]['art_rect_mm'][0]-components[0]['art_rect_mm'][2]>=3.99,(ident,'Overlapping Zero artwork')
    web=meta['support_web'];cx,shoulder=meta['tab_center_mm'];anchor=web['anchor_y_mm']
    assert web['width_per_body_mm']>=26 and min(web['body_contact_mm2'])>=26,(ident,'Insufficient body connection')
    samples=max(1,math.ceil((shoulder-anchor)/.25))
    widths=[stand_axis_width(outer,cx,anchor+.02+(shoulder-anchor-.02)*i/samples) for i in range(samples+1)]
    assert min(widths)>=17.97,(ident,'Narrow support load path',min(widths))
    for y in [shoulder+.2,shoulder+2.0]:
        assert abs(stand_axis_width(outer,cx,y)-18)<.005,(ident,'Resized insertion tab')

def verify_fixed_placements(config,reviewed,redesigns=None,canonical=None,original_canonical=None):
    if not config.get('personal_fill_allocation'):return
    policy=config['personal_fill_policy']
    fixed=policy['fixed_existing_placements']
    assert len(fixed)==len(policy['baseline_ids']) and {row['id'] for row in fixed}==set(policy['baseline_ids'])
    if redesigns is None:
        file=ROOT/'configs/contour_redesigns.json'
        redesigns=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
        if 'parts' in redesigns:redesigns=redesigns['parts']
    fixed_redesigns={row['id'] for row in fixed}&set(redesigns)
    if fixed_redesigns:
        import subprocess
        if canonical is None:canonical=json.loads((ROOT/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts']
        if original_canonical is None:
            raw=subprocess.check_output(['git','show',policy['baseline_commit']+':configs/individual_contours.json'],cwd=ROOT)
            original_canonical=json.loads(raw)['parts']
    indexed={}
    for group in config['selected_primary_groups']:
        rows=reviewed[group]
        pages=rows if rows and isinstance(rows[0],list) else [rows]
        for index,page in enumerate(pages):
            indexed.update({(group,index,row['id']):row for row in page})
    for expected in fixed:
        key=(expected['group'],expected['sheet_index'],expected['id'])
        actual=indexed.get(key)
        assert actual is not None,(key,'Changed fixed baseline placement')
        ident=expected['id']
        if ident not in fixed_redesigns:
            assert all(actual[k]==expected[k] for k in ('x','y','rotation_degrees','source_bounds_mm')),(key,'Changed fixed baseline placement')
            continue
        # Verify the source-image affine transform, since a larger outline
        # changes its bounding origin and therefore its placement coordinates.
        from nest_contours import rotated
        old=original_canonical[ident];new=canonical[ident];design=redesigns[ident]
        assert old['paths']==design['original_paths'],(key,'Changed independent original contours')
        assert max(abs(a-b) for a,b in zip(old['source_bounds_mm'],expected['source_bounds_mm']))<.0001,(key,'Changed original source bounds')
        assert max(abs(a-b) for a,b in zip(actual['source_bounds_mm'],new['source_bounds_mm']))<.0001,(key,'Changed redesigned source bounds')
        assert actual['rotation_degrees']==expected['rotation_degrees'],(key,'Changed fixed baseline placement rotation')
        def translation(row,source):
            poly=max((polygon_of(path) for path in source['paths']),key=lambda q:q.area)
            _,origin=rotated({'bounds':source['source_bounds_mm'],'poly':poly},row['rotation_degrees'])
            x,y=source['source_bounds_mm'][:2]
            a=math.radians(row['rotation_degrees']);c,s=math.cos(a),math.sin(a)
            return row['x']-origin[0]-c*x-s*y,row['y']-origin[1]+s*x-c*y
        old_translation=translation(expected,old);new_translation=translation(actual,new)
        assert max(abs(a-b) for a,b in zip(old_translation,new_translation))<.002,(key,'Changed fixed baseline placement of artwork')

def minimum_sheet_proof(config,selected_by_group,manifest):
    """Compare a global gap-expanded area lower bound with actual reviewed pages."""
    from optional_sheet_policy import capacity_bound

    def polygons(parts):
        for p in parts:
            paths=[Polygon(q) for q in p['expected_paths']]
            outer=max(paths,key=lambda q:q.area)
            yield outer, 2*outer.area-sum(q.area for q in paths)

    def bounds(parts,groups):
        shapes=list(polygons(parts))
        feasible=sum(len(manifest['groups'][g]) for g in groups)
        canvas=config['canvas_mm']
        capacity=capacity_bound([p for p,_ in shapes],canvas,config['page_margin_mm'],config['piece_gap_mm'],1)
        lower=math.ceil((capacity['expanded_piece_area_lower_mm2']-.01)/capacity['expanded_container_area_upper_mm2'])
        assert lower<=feasible,('Verified placements contradict the area bound',lower,feasible)
        return {'parts':len(shapes),'net_material_area_mm2':sum(a for _,a in shapes),
                'area_lower_bound_sheets':lower,'feasible_sheets':feasible,
                'expanded_piece_area_lower_mm2':capacity['expanded_piece_area_lower_mm2'],
                'expanded_single_sheet_area_upper_mm2':capacity['expanded_container_area_upper_mm2']}

    summary=bounds([p for parts in selected_by_group.values() for p in parts],selected_by_group)
    assert summary['feasible_sheets']==config['selected_primary_pages']
    batches=[]
    for name,groups in config.get('separate_print_batches',{}).items():
        groups=[g for g in groups if g in selected_by_group]
        if groups:
            batches.append({'name':name,**bounds([p for g in groups for p in selected_by_group[g]],groups)})
    return {**summary,'single_A3_area_mm2':math.prod(config['canvas_mm']),
            'optimal_sheet_count_proven':summary['feasible_sheets']==summary['area_lower_bound_sheets'],
            'separate_batches':batches,
            'scope':'Selected 3T inventory. Global lower bound uses the policy clearance, sheet margin and exterior areas. Batch rows describe reviewed placements only.'}

def main(check_zips=True,check_native=True):
    out=ROOT/'output';base=out/'a3_release';manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    wanted=CONFIG['current_groups']
    reviewed=json.loads((ROOT/'configs/a3_placements.json').read_text(encoding='utf-8'))['groups']
    assert set(manifest['groups'])==set(wanted),'Incomplete A3 release'
    assert set(reviewed)==set(wanted),'Incomplete reviewed layout inventory'
    assert CONFIG['include_test_pieces'] is False and manifest['test_pieces_included'] is False
    assert manifest.get('package_archives',True)==CONFIG.get('package_archives',True),'Manifest archive policy changed'
    assert manifest['physical_pages_per_selected_thickness']==CONFIG['selected_primary_pages']
    verify_fixed_placements(CONFIG,reviewed)
    from ascent_size_audit import measure
    fixed=json.loads((ROOT/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts'];sized=[]
    for ident in CONFIG['ascent_remaining']['part_ids']:
        row=fixed[ident];paths=[{'poly':polygon_of(p)} for p in row['paths']]
        sized.append({'id':ident,'bounds':row['source_bounds_mm'],'paths':paths,'poly':max((p['poly'] for p in paths),key=lambda p:p.area)})
    source_size_check=measure(sized)
    saved_size=json.loads((base/'11_ascent_remaining/SIZE_VERIFICATION.json').read_text(encoding='utf-8'))
    assert not saved_size['geometry_size_errors'] and not saved_size['physical_cut_or_fit_test']
    assert [p['id'] for p in saved_size['parts']]==[p['id'] for p in source_size_check['parts']]
    records=[];selected_parts=[];selected_by_group={};pad_print_pages=0
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
                if any(p['id'].startswith('len_pad_') for p in spec['parts']):pad_print_pages+=1
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
            fillers=(CONFIG.get('personal_fill_allocation',{}).get(group,[])
                     +CONFIG.get('pad_fill_allocation',{}).get(group,[])
                     +CONFIG.get('logo_fill_allocation',{}).get(group,[]))
            assert set(ids)==set(expected_ascent+fillers) and not set(ids)&set(CONFIG['cadena_source_part_ids'])
            assert 'ascent_31' not in ids
    selected_ids=[p['id'] for p in selected_parts]
    assert sorted(selected_ids)==CONFIG['primary_inventory'] and len(set(selected_ids))==CONFIG['selected_primary_parts']
    verify_pad_inventory(CONFIG,selected_by_group,fixed)
    verify_personal_inventory(CONFIG,selected_by_group)
    verify_logo_inventory(CONFIG,selected_by_group,fixed)
    from optional_sheet_policy import assess
    fill=assess(ROOT)
    saved_fill=json.loads((base/'OPTIONAL_FILL_ASSESSMENT.json').read_text(encoding='utf-8'))
    assert saved_fill['allocation']==fill['allocation'] and saved_fill['deferred']==fill['deferred'],'Stale optional-fill decision'
    assert saved_fill.get('current_pad_allocation',{})==fill['current_pad_allocation'],'Stale PAD allocation'
    for old,new in [(saved_fill['candidate_sets'][k],v) for k,v in fill['candidate_sets'].items()]+[(saved_fill['ascent_with_PAD']['capacity_bound'],fill['ascent_with_PAD']['capacity_bound'])]:
        assert old['impossible_proven']==new['impossible_proven'] and old['parts']==new['parts']
        for key in ['expanded_piece_area_lower_mm2','expanded_container_area_upper_mm2','excess_area_mm2']:
            assert abs(old[key]-new[key])<.001,('Stale optional capacity bound',key)
    assert saved_fill['ascent_with_PAD']['feasible_two_page_layout_found'] is False
    assert saved_fill['ascent_with_PAD']['mathematical_impossibility_proven'] is False
    assert len(manifest['groups']['02_extra_sheet/3T'])+len(manifest['groups']['05_len/3T'])==2
    selected_yanggum=sorted(x for x in selected_ids if x.startswith('yanggum_'))
    assert selected_yanggum==sorted(CONFIG['optional_fill_policy']['candidate_sets']['yanggum_3T'])
    for group,ids in CONFIG['optional_fill_allocation'].items():
        assert sorted(p['id'] for p in selected_by_group[group] if p['id'].startswith('yanggum_'))==sorted(ids)
    assert sorted(x for x in selected_ids if x.startswith('ascent_'))==sorted(CONFIG['cadena_source_part_ids']+CONFIG['ascent_remaining']['part_ids'])
    minimum_proof=minimum_sheet_proof(CONFIG,selected_by_group,manifest)
    packages=[]
    if check_zips and CONFIG.get('package_archives',True):
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
            'selected_primary_pages':CONFIG['selected_primary_pages'],'selected_thickness':'3T','optional_fill_assessment':fill,'PAD_print_pages':pad_print_pages,
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
