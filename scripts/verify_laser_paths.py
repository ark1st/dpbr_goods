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

ACTIVE=['production_v4','diorama_v3','logo_diorama_v3','combined_diorama_v3',
        'carabiner_trials_v1','extra_sheet','linked_tuiing_v1']
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


def inspect_pdf(file, extra=False):
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
        is_protected=extra and i<34
        for j,path in enumerate(contours(d)):
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
    out=ROOT/'output'
    import subprocess
    tracked=set(subprocess.check_output(['git','ls-tree','-r','--name-only','origin/output_len','output'],cwd=ROOT,text=True).splitlines())
    for folder in ACTIVE+['cut_quality']:
        tracked.update(p.relative_to(ROOT).as_posix() for p in (out/folder).rglob('*') if p.is_file())
    tracked.update(['output/LASER_PATH_AUDIT.json','output/RELEASE_VALIDATION.json'])
    current_zips={'Danpungbaram_V4_SMALL_BATCH_16pcs.zip','Danpungbaram_Diorama_V3_3T_5T.zip',
        'Danpungbaram_Logo_Diorama_V3_MAIN_3T_5T.zip','Danpungbaram_Combined_Diorama_V3_TRIALS_11pcs.zip',
        'Extra_Sheet_38pcs_3T.zip','Extra_Sheet_38pcs_5T.zip','Tshirt_Fronts_Aing_Changseop_14x16in.zip',
        'Tuiing_Linked_4_Separate_Plates.zip'}
    current_hashes={r['file'] for r in records}
    inventory=[]
    for full in sorted(tracked):
        rel=full.removeprefix('output/');top=rel.split('/')[0]
        if rel in current_hashes:status='cut_geometry_checked'
        elif top in ACTIVE:status='current_supporting_artwork_or_documentation'
        elif top in ['tshirt','tshirt_fronts']:status='print_only_no_laser_path'
        elif top in current_zips:status='current_package_checked_by_release_validator'
        elif top.endswith('.zip'):status='retired_archive_not_for_production'
        elif top=='cut_quality':status='current_cut_quality_report'
        elif '/' in rel:status='retired_not_for_production'
        else:status='release_index_or_supporting_asset'
        inventory.append({'file':rel,'status':status})
    return inventory


def main(pdf_only=False):
    out=ROOT/'output';tmp=ROOT/'tmp/laser_preflight';tmp.mkdir(parents=True,exist_ok=True)
    records=[];errors=[]
    for folder in ACTIVE:
        for file in sorted((out/folder).rglob('*')):
            if not file.is_file() or 'preview' in file.parts or file.name.startswith('00_'):continue
            rel=file.relative_to(out).as_posix();suffix=file.suffix.lower();target=file
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
            elif suffix=='.pdf' and ('CUT_ONLY' in file.name or file.name=='01_COMBINED_SHEET.pdf'):pass
            else:continue
            try:
                result=inspect_pdf(target,folder=='extra_sheet')
                if result is None:continue
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
    inventory=inventory_for(records)
    report={'revision':'smooth-cut-2026-11-20','mode':'pdf-and-ai-only' if pdf_only else 'all-formats','checked_files':len(records),'errors':errors,
            'protected_original_findings':[{'file':r['file'],'findings':r['protected_original_findings']} for r in records if r['protected_original_findings']],
            'records':records,'inventory':inventory,'physical_cut_test':False}
    destination=(tmp/'ci-report.json') if pdf_only else (out/'LASER_PATH_AUDIT.json')
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if errors:raise SystemExit(f'LASER PREFLIGHT FAILED: {len(errors)} files')
    print(json.dumps({'checked_files':len(records),'errors':0,'protected_findings':len(report['protected_original_findings'])}))
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--pdf-only',action='store_true')
    main(parser.parse_args().pdf_only)
