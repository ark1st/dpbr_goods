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

ACTIVE=['a3_release','individual_assets','recut_only']
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


def inspect_pdf(file, extra=False, protected_regions=(), protected_paths=()):
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
        if d['fill'] is not None or abs(d['width']/MM-.001)>.00002:
            raise ValueError(f'Incorrect fill/stroke in cutting plate: {i}')
        # The first 34 drawing objects are the unchanged 30 external pieces.
        bounds=[v/MM for v in d['rect']]
        is_protected=(extra and i<34) or any(
            b[0]-.002<=bounds[0] and b[1]-.002<=bounds[1] and
            b[2]+.002>=bounds[2] and b[3]+.002>=bounds[3] for b in protected_regions)
        for j,path in enumerate(contours(d)):
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
    from verify_repository import output_inventory
    checked={r['file'] for r in records}
    return [{'file':rel,'status':'cut_geometry_checked' if rel in checked else
             'current_release_package' if rel.endswith('.zip') else 'current_supporting_artwork_or_documentation'}
            for rel in output_inventory(ROOT/'output')]


def main(pdf_only=False):
    out=ROOT/'output';tmp=ROOT/'tmp/laser_preflight';tmp.mkdir(parents=True,exist_ok=True)
    records=[];errors=[]
    manifest=json.loads((out/'a3_release/manifest.json').read_text()) if (out/'a3_release/manifest.json').exists() else {'groups':{}}
    current_a3={p['folder'] for pages in manifest['groups'].values() for p in pages}
    catalog_path=out/'individual_assets/manifest.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else {'assets':[]}
    current_assets={a['folder'] for a in catalog['assets']}
    current_recut={a['folder'] for a in manifest.get('recut_recoveries',[])}
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
                elif folder=='individual_assets':
                    assert file.parent.relative_to(out).as_posix() in current_assets
                    spec=json.loads((file.parent/'asset.json').read_text(encoding='utf-8'))
                elif folder=='recut_only':
                    assert file.parent.relative_to(out).as_posix() in current_recut
                    spec=json.loads((file.parent/'validation.json').read_text(encoding='utf-8'))
                from shapely.geometry import Polygon
                protected=[Polygon(q) for p in spec['parts'] if p['protected_original'] for q in p['expected_paths']] if spec else []
                result=inspect_pdf(target,folder=='extra_sheet',(),protected)
                if result is None:continue
                if spec:
                    if result['outer_contours']!=spec['pieces'] or result['contours']!=spec['closed_contours']:
                        result['errors'].append({'reason':'A3 piece/path inventory mismatch'})
                    if any(abs(a-b)>.01 for a,b in zip(result['dimensions_mm'],spec['canvas_mm'])):
                        result['errors'].append({'reason':'Artboard dimensions differ from registered asset'})
                    if folder=='a3_release' and result['minimum_piece_gap_mm'] is not None and result['minimum_piece_gap_mm']<2.998:
                        result['errors'].append({'reason':'A3 exported piece gap below 3 mm tolerance'})
                # Tight production layout: enforce the actual EXPORTED curve gap.
                if folder=='combined_diorama_v3' and ('COMBINED_MASTER' in file.name or file.name.startswith('03_CUT_ONLY')):
                    if result['outer_contours']!=11 or result['contours']!=42 or result['minimum_piece_gap_mm']<3:
                        result['errors'].append({'reason':'Combined inventory or exported 3 mm gap failed'})
                result.update(file=rel,sha256=artifact_sha256(file),
                              sha256_mode='LF-normalized text' if suffix=='.svg' else 'raw bytes')
                records.append(result)
                if result['errors']:errors.append({'file':rel,'errors':result['errors']})
                print(rel, result['contours'],result['segments'],'FAIL' if result['errors'] else 'OK',flush=True)
            except Exception as e:
                errors.append({'file':rel,'errors':[str(e)]});print('FAIL',rel,str(e),flush=True)
    expected_count=len(current_a3)*(3 if pdf_only else 5)+len(current_assets)*(3 if pdf_only else 4)+len(current_recut)*(2 if pdf_only else 4)
    assert len(records)==expected_count,('Incomplete cutting-format coverage',len(records),expected_count)
    inventory=inventory_for(records)
    report={'revision':manifest['revision'],'mode':'pdf-and-ai-only' if pdf_only else 'all-formats','checked_files':len(records),'errors':errors,
            'protected_original_findings':[{'file':r['file'],'findings':r['protected_original_findings']} for r in records if r['protected_original_findings']],
            'records':records,'inventory':inventory,'physical_cut_test':False,
            'superseded_releases':manifest.get('superseded_releases',[]),
            'retired_archive':json.loads((out/'RETIRED.json').read_text()),
            'coverage':{'current_pages':len(current_a3),'individual_assets':len(current_assets),'existing_print_recovery_plates':len(current_recut),'expected_cut_files':expected_count,
                        'retired_files_are_not_counted_as_current_passes':True},
            'limitations':['Raw archive integrity is verified separately; retired files are not re-approved for cutting.',
                           'Protected external originals are inspected without edits; numerical no-ops are reported separately.']}
    destination=(tmp/'ci-report.json') if pdf_only else (out/'LASER_PATH_AUDIT.json')
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if errors:raise SystemExit(f'LASER PREFLIGHT FAILED: {len(errors)} files')
    print(json.dumps({'checked_files':len(records),'errors':0,'protected_findings':len(report['protected_original_findings'])}))
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--pdf-only',action='store_true')
    main(parser.parse_args().pdf_only)
