"""Inspect every CURRENT cutting artifact, including AI/PDF and native exports.

Old releases are inventoried as retired, never silently counted as passing.
Protected third-party contours are inspected and reported, not rewritten.
"""
from pathlib import Path
import sys,json,hashlib,collections,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from laser_paths import audit_path
from vector_utils import runvc
from artifact_hash import artifact_sha256

ACTIVE=['a3_release','individual_assets','recut_only','large_format']
MM=72/25.4


def contours(drawing):
    result=[];current=[];start=end=None
    def pt(p):return f'{p.x/MM:.7f} {p.y/MM:.7f}'
    def flush():
        nonlocal current,start,end
        if current:
            if abs(start-end)>.002 and not drawing['closePath']:
                raise ValueError('Open exported contour')
            result.append(' '.join(current)+' Z')
        current=[];start=end=None
    for item in drawing['items']:
        kind=item[0]
        if kind in ['re','qu']:
            flush()
            if kind=='re':
                r=item[1];pts=[r.tl,r.tr,r.br,r.bl]
            else:
                q=item[1];pts=[q.ul,q.ur,q.lr,q.ll]
            result.append('M'+pt(pts[0])+''.join(' L'+pt(p) for p in pts[1:])+' Z')
        else:
            a,b=item[1],item[-1]
            if end is None or abs(a-end)>.002:
                flush();start=a;current=['M'+pt(a)]
            if kind=='l':current.append('L'+pt(b))
            elif kind=='c':current.append('C'+' '.join(pt(p) for p in item[2:]))
            else:raise ValueError(f'Unknown PDF operation {kind}')
            end=b
    flush();return result


def protected_contour(path, expected):
    # Nesting overlaps bounding boxes. A nearby owned contour must not inherit
    # permission for original numerical no-ops merely by being inside that box.
    from build_a3_release import polygon_of
    actual=polygon_of(path)
    return any(all(abs(a-b)<=.002 for a,b in zip(actual.bounds,p.bounds)) and
               actual.boundary.hausdorff_distance(p.boundary)<=.002 for p in expected)


def inspect_pdf(file, extra=False, protected_regions=(), protected_paths=(), fixed_strokes=()):
    with fitz.open(file) as source:
        ocgs=source.get_ocgs()
        ids=[i for i,g in ocgs.items() if g['name'] in ['1_LASER_CUT','LASER_CUT']]
        if ocgs and not ids:return None
        if ids:
            source.set_layer(-1,basestate='OFF',on=ids,off=[i for i in ocgs if i not in ids])
        doc=fitz.open(stream=source.tobytes(),filetype='pdf')
    drawings=doc[0].get_drawings(); rows=[];polys=[];failures=[];protected=[]
    for i,d in enumerate(drawings):
        if d.get('color') is None or not (d['color'][0]>.99 and d['color'][1]<.01 and d['color'][2]<.01):
            raise ValueError(f'Non-red content in cutting plate: {i}')
        if d['fill'] is not None:
            raise ValueError(f'Incorrect fill/stroke in cutting plate: {i}')
        # The first 34 drawing objects are the unchanged 30 external pieces.
        bounds=[v/MM for v in d['rect']]
        is_protected=(extra and i<34) or any(
            b[0]-.002<=bounds[0] and b[1]-.002<=bounds[1] and
            b[2]+.002>=bounds[2] and b[3]+.002>=bounds[3] for b in protected_regions)
        for j,path in enumerate(contours(d)):
            width=d['width']/MM
            original_width=None
            if fixed_strokes:
                from build_a3_release import polygon_of
                actual_shape=polygon_of(path)
                original_width=next((expected for poly,expected in fixed_strokes
                    if all(abs(a-b)<=.002 for a,b in zip(actual_shape.bounds,poly.bounds))
                    and actual_shape.boundary.hausdorff_distance(poly.boundary)<=.002),None)
            if original_width is not None and abs(width-original_width)>.00002:
                raise ValueError(f'Changed fixed original stroke in cutting plate: {i}:{j}')
            if original_width is None and abs(width-.001)>.00002:
                raise ValueError(f'Incorrect fill/stroke in cutting plate: {i}:{j}')
            if protected_paths:
                is_protected=protected_contour(path,protected_paths)
            label=f'{i}:{j}'
            try:
                stats,poly=audit_path(path,allow_original_numerics=is_protected)
                if stats['original_numerical_notes']:
                    protected.append({'path':label,'notes':stats['original_numerical_notes'],
                                      'status':'measured_numerical_no_op_original_preserved'})
                rows.append({'path':label,**stats,'protected_original':is_protected})
                polys.append((label,poly,is_protected))
            except ValueError as e:
                failures.append({'path':label,'reason':str(e),'protected_original':is_protected})
    for i,(label,p,protected_p) in enumerate(polys):
        for qlabel,q,protected_q in polys[:i]:
            if p.equals(q):
                failures.append({'path':label,'reason':f'Duplicate of {qlabel}'})
            elif p.boundary.intersects(q.boundary):
                failures.append({'path':label,'reason':f'Intersecting cut contour {qlabel}'})
    outer=[p for i,(_,p,_) in enumerate(polys) if not any(q.contains(p) for j,(_,q,_) in enumerate(polys) if i!=j)]
    gap=min((p.distance(q) for i,p in enumerate(outer) for q in outer[:i]),default=None)
    dims=[doc[0].rect.width/MM,doc[0].rect.height/MM];doc.close()
    return {'dimensions_mm':dims,'drawing_objects':len(drawings),'contours':sum(len(contours(d)) for d in drawings),
            'outer_contours':len(outer),'minimum_piece_gap_mm':gap,
            'segments':sum(r['segments'] for r in rows),'curves':sum(r['curves'] for r in rows),
            'paths':rows,'errors':failures,'protected_original_findings':protected}


def native_pdf(file,dest):
    info=json.loads(runvc(['run','--in',file,'--cmd','document.inspect']).splitlines()[-1])['result']
    layers=[g['id'] for g in info['layers'] if g['name'] in ['1_LASER_CUT','LASER_CUT']]
    if not layers:return False
    all_ids=[g['id'] for g in info['layers']]
    commands=[{'command':'layer.setProps','params':{'ids':all_ids,'visible':False,'printable':False}},
              {'command':'layer.setProps','params':{'ids':layers,'visible':True,'printable':True}},
              {'command':'document.export','params':{'path':str(dest),'format':'pdf'}}]
    job=dest.with_suffix('.json');job.write_text(json.dumps(commands),encoding='utf-8')
    runvc(['run','--in',file,'--commands',job]);return True


def inventory_for(records):
    from verify_repository import output_inventory,retired_package_paths
    out=ROOT/'output'
    manifest=json.loads((out/'a3_release/manifest.json').read_text(encoding='utf-8'))
    retired=retired_package_paths(manifest)
    checked={r['file'] for r in records}
    return [{'file':rel,'status':'cut_geometry_checked' if rel in checked else
             'retired_previous_revision_package' if rel in retired else
             'current_release_package' if rel.endswith('.zip') else 'current_supporting_artwork_or_documentation'}
            for rel in output_inventory(out)]


def inspection_fingerprint(pdf_only=False):
    """Invalidate reuse when the local evaluator, geometry backend, or converter changes."""
    import inspect
    from importlib.metadata import version
    from build_a3_release import polygon_of
    from vector_utils import cli_path
    functions=(inspect_pdf,contours,protected_contour,native_pdf,polygon_of)
    values=[inspect.getsource(fn) for fn in functions]
    # Keep existing full-format cache entries when selecting the PDF-only toolchain.
    evaluator=inspect.getsource(main).split('    expected_count=')[0]
    values.append(evaluator.replace('fingerprint=inspection_fingerprint(pdf_only=pdf_only)',
                                    'fingerprint=inspection_fingerprint()'))
    values.extend(artifact_sha256(ROOT/'scripts'/name) for name in
                  ('laser_paths.py','artifact_hash.py','vector_utils.py'))
    values.extend(version(name) for name in ('PyMuPDF','shapely','svgpathtools','numpy'))
    values.extend([str(MM),sys.version])
    if pdf_only:
        values.append('pdf-only')
    else:
        converter=cli_path()
        values.extend([str(converter),artifact_sha256(converter)])
    return hashlib.sha256('\n'.join(values).encode()).hexdigest()


def verify_len_delivery(file, layout, canonical):
    from build_a3_release import extract_layers, shifted_poly, polygon_of
    from fixed_page3_checks import verify_exported_paths
    from shapely.geometry import box

    rows=layout['parts']
    source_ids=collections.Counter(row['canonical_id'] for row in rows)
    assert sum(v for k,v in source_ids.items() if k.startswith('len_pad_'))==7
    assert source_ids['danba_logo_smooth']==layout['danba_keyrings']>0
    extras=layout['additional_source_paths']
    assert len([key for key in extras if key.startswith('mascot_')])==6
    assert all(source_ids[key]>=1 for key in extras)
    fillers=layout['filler_counts']
    assert all(source_ids[key]>=qty>0 for key,qty in fillers.items())
    assert 'muhani_keyring' not in source_ids  # Earlier cyan star-hat avatar
    assert source_ids['mascot_blue_keyring']>source_ids['danba_logo_smooth']
    assert set(('mascot_blue_keyring','danba_logo_smooth',
                'tuiing_01','golden_01','burnt_01','unfried_01'))<=set(fillers)
    assert any('garam' in key for key in fillers) and any('danpaengi' in key for key in fillers)
    assert len(rows)==layout['pieces'] and len(set(r['id'] for r in rows))==len(rows)
    expected=[]
    for row in rows:
        key=row['canonical_id']
        paths=extras[key] if key in extras else canonical[key]['paths']
        assert len(paths)==row['path_count'] and row['scale']==1
        if key=='danba_logo_smooth' or key.endswith('_keyring'):
            assert len(paths)==2
        placement={'piece':{'bounds':row['source_bounds_mm']},'x':row['placed_bounds_mm'][0],
                   'y':row['placed_bounds_mm'][1],'rotated_origin':row['rotated_origin_mm'],
                   'rotation':row['rotation_degrees']}
        shapes=[shifted_poly(polygon_of(path),placement) for path in paths]
        assert all(box(7.998,7.998,412.002,289.002).covers(q) for q in shapes)
        expected.append({'expected_paths':[q.exterior.coords for q in shapes]})
    with extract_layers(file,['LASER_CUT']) as doc:
        actual=[path for drawing in doc[0].get_drawings() for path in contours(drawing)]
    verify_exported_paths({'parts':expected},actual)


def main(pdf_only=False):
    out=ROOT/'output';tmp=ROOT/'tmp/laser_preflight';tmp.mkdir(parents=True,exist_ok=True)
    records=[];errors=[]
    manifest=json.loads((out/'a3_release/manifest.json').read_text()) if (out/'a3_release/manifest.json').exists() else {'groups':{}}
    current_a3={p['folder'] for pages in manifest['groups'].values() for p in pages}
    catalog_path=out/'individual_assets/manifest.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else {'assets':[]}
    current_assets={a['folder'] for a in catalog['assets']}
    current_recut={a['folder'] for a in manifest.get('recut_recoveries',[])}
    current_large={a['folder'] for a in manifest.get('large_format_plates',[])}
    fingerprint=inspection_fingerprint(pdf_only=pdf_only)
    cache=tmp/'pass_records'/fingerprint
    cache.mkdir(parents=True,exist_ok=True)
    prior_path=out/'LASER_PATH_AUDIT.json'
    prior=json.loads(prior_path.read_text()) if prior_path.exists() else {}
    prior_records={r['file']:r for r in prior.get('records',[]) if not r.get('errors') and r.get('inspection_fingerprint')==fingerprint}
    from build_a3_release import CONFIG
    fixed=CONFIG.get('fixed_source_page3',{})
    retired_a3=['a3_release/'+g+'/' for g in manifest.get('retired_groups',[])]
    for folder in ACTIVE:
        for file in sorted((out/folder).rglob('*')):
            if not file.is_file() or 'preview' in file.parts or file.name.startswith('00_'):continue
            rel=file.relative_to(out).as_posix();suffix=file.suffix.lower();target=file
            if folder=='a3_release':
                if any(rel.startswith(p) for p in retired_a3):continue
                if suffix in ['.ai','.vectorcraft'] or file.name.startswith('03_CUT_ONLY'):
                    assert file.parent.relative_to(out).as_posix() in current_a3,('Unregistered A3 production artifact',rel)
            if pdf_only and suffix not in ['.ai','.pdf']:continue
            cache_path=cache/(hashlib.sha256(rel.encode()).hexdigest()+'.json')
            source_record=prior_records.get(rel)
            if not source_record and cache_path.exists():
                source_record=json.loads(cache_path.read_text())
            expected=file.parent/('asset.json' if folder=='individual_assets' else 'validation.json')
            # Fixed-source exceptions depend on paths and source-specific stroke widths.
            # Recheck that page in all formats on every publication.
            is_fixed_page=folder=='a3_release' and file.parent.relative_to(out).as_posix()==fixed.get('folder')
            reusable=(not is_fixed_page and source_record and expected.is_file()
                      and source_record.get('spec_sha256')==artifact_sha256(expected)
                      and source_record['sha256']==artifact_sha256(file))
            if reusable:
                registered={'a3_release':current_a3,'individual_assets':current_assets,'large_format':current_large,'recut_only':current_recut}
                assert file.parent.relative_to(out).as_posix() in registered[folder],rel
                records.append(dict(source_record,reused_geometry_result=True))
                continue
            if suffix not in ('.pdf','.ai','.svg','.vectorcraft'):continue
            if suffix=='.pdf' and 'CUT_ONLY' not in file.name and file.name not in ('01_COMBINED_SHEET.pdf','02_MASTER.pdf'):continue
            assert expected.exists(),(rel,'Missing inspection specification')
            input_sha=artifact_sha256(file)
            spec_sha=artifact_sha256(expected)
            if suffix=='.svg':
                tree=ET.parse(file)
                cutgroups=[e for e in tree.iter() if e.get('id') in ['1_LASER_CUT','LASER_CUT']]
                if not cutgroups:continue
                # Export just the cut layer in original page coordinates. No parent transforms
                # exist on the layer itself in our generators; child transforms are preserved.
                svg=tree.getroot();children=list(svg)
                for child in children:
                    if child not in cutgroups and not child.tag.endswith('}defs'):svg.remove(child)
                target=tmp/(hashlib.sha256(rel.encode()).hexdigest()[:16]+'.pdf')
                clean=target.with_suffix('.svg');tree.write(clean,encoding='utf-8',xml_declaration=True)
                runvc(['convert',clean,target])
            elif suffix=='.vectorcraft':
                target=tmp/(hashlib.sha256(rel.encode()).hexdigest()[:16]+'.pdf')
                if not native_pdf(file,target):continue
            elif suffix=='.ai':pass
            elif suffix=='.pdf' and ('CUT_ONLY' in file.name or file.name in ['01_COMBINED_SHEET.pdf','02_MASTER.pdf']):pass
            else:continue
            try:
                spec=None
                if folder=='a3_release':
                    spec=json.loads((file.parent/'validation.json').read_text(encoding='utf-8'))
                elif folder=='large_format':
                    assert file.parent.relative_to(out).as_posix() in current_large,('Unregistered large-format artifact',rel)
                    spec=json.loads((file.parent/'validation.json').read_text(encoding='utf-8'))
                elif folder=='individual_assets':
                    assert file.parent.relative_to(out).as_posix() in current_assets
                    spec=json.loads((file.parent/'asset.json').read_text(encoding='utf-8'))
                elif folder=='recut_only':
                    assert file.parent.relative_to(out).as_posix() in current_recut
                    spec=json.loads((file.parent/'validation.json').read_text(encoding='utf-8'))
                from shapely.geometry import Polygon
                protected=[Polygon(q) for p in spec['parts'] if p['protected_original'] for q in p['expected_paths']] if spec else []
                from fixed_page3_checks import FIXED_IDS
                fixed_strokes=[]
                if is_fixed_page:
                    baseline=json.loads((ROOT/fixed['geometry_file']).read_text(encoding='utf-8'))
                    baseline_parts={p['id']:p for p in baseline['parts']}
                    assert set(baseline_parts)==FIXED_IDS
                    for p in spec['parts']:
                        if p['id'] in FIXED_IDS:
                            original=baseline_parts[p['id']]
                            entries=[original['source_outer'],*original['source_holes']]
                            assert len(entries)==len(p['expected_paths'])
                            fixed_strokes.extend((Polygon(q),entry['stroke_mm']) for q,entry in zip(p['expected_paths'],entries))
                result=inspect_pdf(target,folder=='extra_sheet',(),protected,fixed_strokes)
                if result is None:continue
                if spec:
                    if result['outer_contours']!=spec['pieces'] or result['contours']!=spec['closed_contours']:
                        result['errors'].append({'reason':'A3 piece/path inventory mismatch'})
                    if any(abs(a-b)>.01 for a,b in zip(result['dimensions_mm'],spec['canvas_mm'])):
                        result['errors'].append({'reason':'Artboard dimensions differ from registered asset'})
                    if is_fixed_page:
                        from fixed_page3_checks import check_page_geometry,verify_exported_paths
                        with fitz.open(target) as source:
                            ocgs=source.get_ocgs()
                            ids=[i for i,g in ocgs.items() if g['name'] in ['1_LASER_CUT','LASER_CUT']]
                            if ids:source.set_layer(-1,basestate='OFF',on=ids,off=[i for i in ocgs if i not in ids])
                            doc=fitz.open(stream=source.tobytes(),filetype='pdf')
                        paths=[p for d in doc[0].get_drawings() for p in contours(d)]
                        verify_exported_paths(spec,paths)
                        result['fixed_source_spacing_exceptions']=check_page_geometry(spec['parts'],paths)
                        doc.close()
                    if folder in ('a3_release','large_format') and result['minimum_piece_gap_mm'] is not None and result['minimum_piece_gap_mm']<2.998:
                        if not is_fixed_page:
                            result['errors'].append({'reason':'A3 exported piece gap below 3 mm tolerance'})
                # Tight production layout: enforce the actual EXPORTED curve gap.
                if folder=='combined_diorama_v3' and ('COMBINED_MASTER' in file.name or file.name.startswith('03_CUT_ONLY')):
                    if result['outer_contours']!=11 or result['contours']!=42 or result['minimum_piece_gap_mm']<3:
                        result['errors'].append({'reason':'Combined inventory or exported 3 mm gap failed'})
                assert input_sha==artifact_sha256(file) and spec_sha==artifact_sha256(expected),(rel,'Inputs changed during inspection')
                result.update(file=rel,sha256=input_sha,spec_sha256=spec_sha,
                              inspection_fingerprint=fingerprint,reused_geometry_result=False,
                              sha256_mode='LF-normalized text' if suffix=='.svg' else 'raw bytes')
                if not result['errors'] and not is_fixed_page:
                    import os
                    pending=cache_path.with_suffix(f'.{os.getpid()}.tmp')
                    pending.write_text(json.dumps(result))
                    pending.replace(cache_path)
                records.append(result)
                if result['errors']:errors.append({'file':rel,'errors':result['errors']})
                print(rel, result['contours'],result['segments'],'FAIL' if result['errors'] else 'OK',flush=True)
            except Exception as e:
                errors.append({'file':rel,'errors':[str(e)]});print('FAIL',rel,str(e),flush=True)
    expected_count=(len(current_a3)+len(current_large))*(3 if pdf_only else 5)+len(current_assets)*(3 if pdf_only else 4)+len(current_recut)*(2 if pdf_only else 4)
    delivery_keys=[]
    active_masters=[]
    reference_records=[]
    if manifest.get('print_delivery'):
        from print_delivery import AI, verify_delivery
        delivery_keys=verify_delivery()
        assert set(delivery_keys)==set(manifest['print_delivery']['plates'])
        for key in delivery_keys:
            file=out/'print_delivery'/key/AI
            if key=='page03':
                # The pair verifier matches every original red drawing and its
                # line style to this independently audited master at exact coordinates.
                source=manifest['fixed_source_page3']['folder']+'/03_CUT_ONLY.pdf'
                result=dict(next(row for row in records if row['file']==source))
            else:
                result=inspect_pdf(file)
                assert result and result['minimum_piece_gap_mm']>=2.998, key
            if key=='alternative_page04':
                layout=json.loads((out/'a3_options/alternative/page_04/layout.json').read_text())
                canonical=json.loads((ROOT/'configs/individual_contours.json').read_text())['parts']
                verify_len_delivery(file,layout,canonical)
            result.update(file=file.relative_to(out).as_posix(),sha256=artifact_sha256(file),sha256_mode='raw bytes')
            records.append(result)
            if result['errors']:errors.append({'file':result['file'],'errors':result['errors']})
        expected_count+=len(delivery_keys)
        from print_delivery import SOURCES, REFERENCE_SOURCES
        active=set(delivery_keys)
        assert set(REFERENCE_SOURCES)==set(manifest['print_delivery']['reference_plates'])
        for key,relative in (SOURCES|REFERENCE_SOURCES).items():
            combined_rel=f'print_delivery/{key}/03_COMBINED_MASTER.ai'
            assert combined_rel in manifest['print_delivery']['layout_files'],combined_rel
            master=out/combined_rel
            verify_combined_master(master, key, relative)
            if key=='page03':
                # All source-specific red paths and widths match the registered
                # pair; the fixed source retains the user's original exceptions.
                source=f'print_delivery/{key}/{AI}'
                result=dict(next(row for row in records if row['file']==source))
            else:
                result=inspect_pdf(master)
                assert result and result['minimum_piece_gap_mm']>=2.998,key
            result.update(file=combined_rel,sha256=artifact_sha256(master),sha256_mode='raw bytes')
            if result['errors']:errors.append({'file':combined_rel,'errors':result['errors']})
            if key in active:
                records.append(result)
                active_masters.append(combined_rel)
            else:
                reference_records.append(result)
        expected_count+=len(active_masters)
    assert len(records)==expected_count,('Incomplete cutting-format coverage',len(records),expected_count)
    inventory=inventory_for(records)
    references={str(Path(row['file']).parent) for row in reference_records}
    for entry in inventory:
        if str(Path(entry['file']).parent) in references:
            entry['status']='superseded_print_reference'

    report={'revision':manifest['revision'],'mode':'pdf-and-ai-only' if pdf_only else 'all-formats','checked_files':len(records),'errors':errors,
            'protected_original_findings':[{'file':r['file'],'findings':r['protected_original_findings']} for r in records if r['protected_original_findings']],
            'records':records,'reference_combined_masters':reference_records,'inventory':inventory,'physical_cut_test':False,
            'superseded_releases':manifest.get('superseded_releases',[]),
            'retired_archive':json.loads((out/'RETIRED.json').read_text()),
            'coverage':{'current_pages':len(current_a3),'large_format_plates':len(current_large),'individual_assets':len(current_assets),'existing_print_recovery_plates':len(current_recut),'expected_cut_files':expected_count,'cut_with_blue_ai':len(delivery_keys),'combined_masters':len(active_masters),
                        'retired_files_are_not_counted_as_current_passes':True},
            'limitations':['Raw archive integrity is verified separately; retired files are not re-approved for cutting.',
                           'Protected external originals are inspected without edits; numerical no-ops are reported separately.']}
    destination=(tmp/'ci-report.json') if pdf_only else (out/'LASER_PATH_AUDIT.json')
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if errors:raise SystemExit(f'LASER PREFLIGHT FAILED: {len(errors)} files')
    print(json.dumps({'checked_files':len(records),'errors':0,'protected_findings':len(report['protected_original_findings'])}))
    return report


def verify_combined_master(path, key, relative):
    """Cross-check the printer's layered master against the approved PNG/cut pair."""
    from io import BytesIO
    from PIL import Image
    from build_a3_release import extract_layers
    from print_delivery import PNG, vectors, sha

    folder=path.parent
    registration=json.loads((folder/'registration.json').read_text())
    with fitz.open(path) as doc:
        assert len(doc)==1 and list(doc[0].rect)==registration['page_rect_pt']
        defaults={g['name']:g['on'] for g in doc.get_ocgs().values()}
        assert defaults==({'PRINT_ARTWORK':True,'LASER_CUT':True,'CORNER_REFERENCE':True} | ({} if key=='alternative_page04' else {'WHITE_INK_MASK':False})),defaults
    for layer, fingerprints in registration['source_vectors'].items():
        with extract_layers(path,[layer]) as subset:
            assert vectors(subset[0],layer)==fingerprints,(path,layer)
    original=ROOT/relative/'02_MASTER.pdf'
    if original.is_file():
        assert sha(original)==sha(path),'Combined AI differs from the generated master PDF'
    with extract_layers(path,['PRINT_ARTWORK','CORNER_REFERENCE']) as printed, Image.open(folder/PNG) as source:
        pix=printed[0].get_pixmap(dpi=300,alpha=True)
        with Image.open(BytesIO(pix.tobytes('png'))) as actual:
            del pix
            assert actual.size==source.size and actual.mode==source.mode=='RGBA'
            for top in range(0, source.height, 256):
                region=(0,top,source.width,min(source.height,top+256))
                assert source.crop(region).tobytes()==actual.crop(region).tobytes(),(path,'Print pixels differ',top)
    print(f'{key} combined AI verified: registered artwork pixels, red/blue vectors and layer defaults match.',flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--pdf-only',action='store_true')
    main(parser.parse_args().pdf_only)
