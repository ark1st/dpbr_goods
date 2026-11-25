"""Full current-release audit: archive, contour formats, printed pages and ZIPs."""
from pathlib import Path
import sys,json,subprocess,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image,ImageDraw
from artifact_hash import artifact_sha256

def verify_editor_cut_visible(doc,file):
    """Editable masters open with cut geometry visible and white mask hidden."""
    groups=doc.get_ocgs()
    names={group['name']:xref for xref,group in groups.items()}
    assert len(names)==len(groups) and {'LASER_CUT','WHITE_INK_MASK'}<=set(names),(file,'Missing cut/white OCG layers')
    setting=doc.get_layer() or {};base=setting.get('basestate','ON')
    assert base in ('ON','OFF'),(file,'Unknown OCG default state')
    on,off=set(setting.get('on',[])),set(setting.get('off',[]))
    def visible(name):
        ident=names[name]
        return ident in on or (ident not in off and base=='ON')
    assert visible('LASER_CUT'),(file,'LASER_CUT hidden by default')
    assert not visible('WHITE_INK_MASK'),(file,'WHITE_INK_MASK visible by default')
    red=[d for d in doc[0].get_drawings() if d.get('color') and d['color'][0]>.99
         and d['color'][1]<.01 and d['color'][2]<.01]
    assert red,(file,'No visible red cut geometry')
    return len(red)

def verify_large_plate(out,plate):
    """Check production geometry and 5T mechanical interfaces independently."""
    from shapely.geometry import Polygon, box, LineString
    from build_a3_release import MM, polygon_of, shifted_poly, extract_layers
    from verify_laser_paths import contours, native_pdf
    import xml.etree.ElementTree as ET
    folder=out/plate['folder']
    spec=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
    assert plate['canvas_mm']==spec['canvas_mm']==[800,500]
    assert spec['artwork_scale']==1 and spec['pieces']==plate['pieces']==30
    assert spec['closed_contours']==plate['contours']==70
    ids={f'ascent_{i:02}' for i in range(1,31)}
    assert len(spec['parts'])==30 and {p['id'] for p in spec['parts']}==ids
    canonical_path=ROOT/plate.get('canonical_config','configs/ascent_5t_contours.json')
    canonical=json.loads(canonical_path.read_text(encoding='utf-8'))['parts']
    source=json.loads((ROOT/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts']
    assert set(canonical)==ids
    outer_shapes=[];all_expected=[];slots=0
    for part in spec['parts']:
        ident=part['id'];row=canonical[ident];paths=row['paths']
        assert part['scale']==1 and len(paths)==part['path_count']==len(part['expected_paths'])
        assert max(abs(a-b) for a,b in zip(row['source_bounds_mm'],part['source_bounds_mm']))<.0001
        place={'piece':{'bounds':part['source_bounds_mm']},'rotation':part['rotation_degrees'],
               'x':part['placed_bounds_mm'][0],'y':part['placed_bounds_mm'][1],
               'rotated_origin':part.get('rotated_origin_mm')}
        source_polys=[polygon_of(path) for path in paths]
        expected=[Polygon(q) for q in part['expected_paths']]
        for curve,actual in zip(source_polys,expected,strict=True):
            assert shifted_poly(curve,place).boundary.hausdorff_distance(actual.boundary)<.002,(ident,'changed 5T contour')
        outer=max(source_polys,key=lambda p:p.area);outer_shapes.append(shifted_poly(outer,place));all_expected.extend(expected)
        if int(ident.split('_')[1])<=5:
            assert len(paths)==9
            assert max(abs(a-b) for a,b in zip((outer.bounds[2]-outer.bounds[0],outer.bounds[3]-outer.bounds[1]),(104,38)))<.002,(ident,'base dimensions')
            holes=sorted((p for p in source_polys if p is not outer),key=lambda p:p.centroid.y)
            assert len(holes)==8 and all(outer.contains(p) for p in holes)
            for h in holes:
                w=h.bounds[2]-h.bounds[0];height=h.bounds[3]-h.bounds[1]
                assert abs(w-19.8)<.002 and abs(height-4.85)<.002,(ident,'incorrect 5T slot',w,height)
                assert h.boundary.distance(outer.boundary)>=2.998,(ident,'slot wall too narrow')
            assert all(a.distance(b)>=2.998 for i,a in enumerate(holes) for b in holes[:i]),(ident,'slot separation')
            prior=sorted((polygon_of(q) for q in source[ident]['paths'][:-1]),key=lambda h:h.centroid.y)
            assert sorted(round(h.centroid.x,3) for h in holes)==sorted(round(h.centroid.x,3) for h in prior),(ident,'slot column moved')
            for i in range(0,8,2):
                a,b=sorted(holes[i:i+2],key=lambda h:h.centroid.x)
                assert abs(abs(a.centroid.x-b.centroid.x)-40)<.003,(ident,'slot column pitch')
                axis_y=(a.centroid.y+b.centroid.y)/2
                mid_x=(a.centroid.x+b.centroid.x)/2
                original_y=sum(p.centroid.y for p in prior[i:i+2])/2
                assert abs(axis_y-original_y-(i/2-1.5)*2.5)<.002,(ident,'row centre moved')
                assert abs(a.centroid.y-b.centroid.y)<.002,(ident,'paired slots are staggered')
                # One common pose for both tabs. The opening expands by half
                # the kerf on every side; the tab loses one kerf in width.
                for hole,cx in ((a,mid_x-20),(b,mid_x+20)):
                    tab=box(cx-9.9,axis_y-2.5,cx+9.9,axis_y+2.5)
                    opening=hole.buffer(.1)
                    assert opening.covers(tab) and opening.boundary.distance(tab)>=.024,(ident,'5T tab fit')
            slots+=8
        else:
            assert len(paths)==1
            original=polygon_of(source[ident]['paths'][0])
            x0,y0,x1,old_tip=original.bounds
            shoulder=old_tip-3
            assert abs(outer.bounds[3]-shoulder-5.1)<.002,(ident,'tab engagement depth')
            # Recover the released body and original 20 mm-wide tabs by
            # clipping the extension off. Everything else must match.
            original_region=box(x0-1,y0-1,x1+1,old_tip)
            shortened=outer.intersection(original_region)
            assert shortened.boundary.hausdorff_distance(original.boundary)<.002,(ident,'original panel changed')
            probe=original.intersection(LineString([(x0-1,shoulder+1),(x1+1,shoulder+1)]))
            spans=list(probe.geoms)
            assert len(spans)==2
            for span in spans:
                left,_,right,_=span.bounds
                assert abs(right-left-20)<.002,(ident,'tab width')
            expected=original
            for span in spans:
                left,_,right,_=span.bounds
                expected=expected.union(box(left,old_tip-.01,right,shoulder+5.1))
            assert expected.boundary.hausdorff_distance(outer.boundary)<.002,(ident,'tab footprint changed')
    assert slots==40
    usable=box(7.998,7.998,792.002,492.002)
    assert all(usable.covers(p) for p in outer_shapes)
    min_gap=min(a.distance(b) for i,a in enumerate(outer_shapes) for b in outer_shapes[:i])
    assert min_gap>=2.998,('Large-format piece gap',min_gap)
    deviations={}
    native_cache=ROOT/'tmp/laser_preflight'/('large_plate_'+hashlib.sha256(plate['folder'].encode()).hexdigest()[:16]+'.pdf')
    if not native_cache.exists() or native_cache.stat().st_mtime<(folder/'02_MASTER.vectorcraft').stat().st_mtime:
        native_cache.parent.mkdir(parents=True,exist_ok=True);assert native_pdf(folder/'02_MASTER.vectorcraft',native_cache)
    for name in ['03_CUT_ONLY.pdf','02_MASTER.pdf','02_MASTER.ai','02_MASTER.vectorcraft','03_CUT_ONLY.svg']:
        if name.endswith('.svg'):
            root=ET.parse(folder/name);actual=[polygon_of(e.get('d')) for e in root.iter() if e.tag.endswith('}path')]
        else:
            doc=fitz.open(native_cache if name.endswith('.vectorcraft') else folder/name) if name in ('03_CUT_ONLY.pdf','02_MASTER.vectorcraft') else extract_layers(folder/name,['LASER_CUT'])
            assert len(doc)==1 and max(abs(a-b) for a,b in zip((doc[0].rect.width/MM,doc[0].rect.height/MM),plate['canvas_mm']))<.01
            actual=[polygon_of(q) for drawing in doc[0].get_drawings() for q in contours(drawing)]
        assert len(actual)==len(all_expected),(name,'contour count')
        remaining=set(range(len(actual)));maximum=0
        for expected in all_expected:
            choices=[i for i in remaining if all(abs(a-b)<.01 for a,b in zip(expected.bounds,actual[i].bounds))]
            assert choices,(name,'missing contour',expected.bounds)
            delta,index=min((expected.boundary.hausdorff_distance(actual[i].boundary),i) for i in choices)
            assert delta<.002,(name,'changed contour',delta)
            remaining.remove(index);maximum=max(maximum,delta)
        deviations[name]=maximum
    master=extract_layers(folder/'02_MASTER.pdf',['PRINT_ARTWORK','CORNER_REFERENCE'])
    with fitz.open(folder/'01_PRINT.pdf') as printed:
        assert master[0].get_pixmap(alpha=True).samples==printed[0].get_pixmap(alpha=True).samples,'Large-format master and print do not match'
        blue=[d for d in printed[0].get_drawings() if d.get('color')==(0,0,1)]
        assert len(blue)==1 and max(abs(a-b) for a,b in zip([v/MM for v in blue[0]['rect']],[4,4,796,496]))<.01,'Missing or moved blue reference'
    white_master=extract_layers(folder/'02_MASTER.pdf',['WHITE_INK_MASK'])
    with fitz.open(folder/'04_WHITE_INK_MASK.pdf') as white:
        assert white_master[0].get_pixmap(alpha=True).samples==white[0].get_pixmap(alpha=True).samples,'Large-format master and white mask do not match'
    for name in ['01_PRINT_300ppi.png','04_WHITE_INK_MASK_300ppi.png']:
        with Image.open(folder/name) as im:
            assert im.size==tuple(math.ceil(x*300/25.4) for x in plate['canvas_mm']) and im.mode=='RGBA'
            assert all(abs(x-300)<.1 for x in im.info['dpi'])
    return {'folder':plate['folder'],'canvas_mm':plate['canvas_mm'],'pieces':30,'bases':5,'panels':25,'slots':slots,
            'minimum_gap_mm':min_gap,'tab_depth_mm':5.1,'slot_size_mm':[19.8,4.85],'format_deviation_mm':deviations,
            'sha256':{name:artifact_sha256(folder/name) for name in plate['files']},
            'errors':[],'physical_cut_test':False,
            'limitations':['Nominal 5T slot width does not verify actual material thickness, laser kerf or physical fit.',
                           'Both slots share a mounting axis. Predicted fit assumes 5.0 mm stock and a 0.20 mm kerf.']}

def production_delivery_files(out, plates, laser):
    """Tie each press file to the completed laser audit and registered print pixels."""
    from print_delivery import AI, COMBINED_AI
    delivery_files={}
    records={r['file']:r for r in laser['records']}
    for key in plates:
        folder=out/'print_delivery'/key
        registration=json.loads((folder/'registration.json').read_text())
        hashes=registration['sha256']
        assert all(artifact_sha256(folder/name)==sha for name,sha in hashes.items())
        for name in (AI,COMBINED_AI):
            assert records[f'print_delivery/{key}/{name}']['sha256']==hashes[name]
        cut=records[f'print_delivery/{key}/{AI}']
        delivery_files[key]={'sha256':hashes,'pieces':cut['outer_contours'],'cut_paths':cut['contours']}
    return delivery_files

def main():
    from verify_repository import main as repository_audit
    from verify_laser_paths import main as laser_audit
    from verify_a3_release import main as a3_audit
    repository=repository_audit()
    laser=laser_audit()
    a3=a3_audit()
    from verify_individual_assets import main as asset_audit
    assets=asset_audit() if (ROOT/'output/individual_assets/manifest.json').exists() else None
    from verify_recut import main as recut_audit
    recut=recut_audit() if (ROOT/'output/recut_only').exists() else None
    out=ROOT/'output';qa=ROOT/'tmp/release_qa_current';qa.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((out/'a3_release/manifest.json').read_text(encoding='utf-8'))
    configured=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))
    assert manifest.get('large_format_plates',[])==configured.get('large_format_plates',[]),'Unregistered large-format release or stale manifest'
    editor_visibility=[]
    catalog=json.loads((out/'individual_assets/manifest.json').read_text(encoding='utf-8'))
    editor_folders=[out/p['folder'] for pages in manifest['groups'].values() for p in pages]
    editor_folders.extend(out/p['folder'] for p in manifest.get('large_format_plates',[]))
    editor_folders.extend(out/a['folder'] for a in catalog['assets'])
    for folder in editor_folders:
        for name in ('02_MASTER.ai','02_MASTER.pdf'):
            file=folder/name
            with fitz.open(file) as doc:
                count=verify_editor_cut_visible(doc,file)
            editor_visibility.append({'file':file.relative_to(out).as_posix(),'visible_red_drawing_objects':count})
    renders=[];images=[];tiles=[]
    for group,pages in manifest['groups'].items():
        for page in pages:
            folder=out/page['folder'];slug=group.replace('/','_')+'_'+folder.name
            for file in sorted(folder.iterdir()):
                if file.suffix.lower() in ['.pdf','.ai']:
                    prefix=qa/(slug+'_'+file.stem+file.suffix.replace('.','_'))
                    subprocess.run(['pdftoppm','-r','70','-singlefile','-png',str(file),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                    with fitz.open(file) as doc:
                        assert len(doc)==1 and all(abs(a-b)<.01 for a,b in zip([doc[0].rect.width*25.4/72,doc[0].rect.height*25.4/72],[420,297])),file
                    with Image.open(str(prefix)+'.png') as im:im.verify()
                    renders.append({'file':file.relative_to(out).as_posix(),'sha256':artifact_sha256(file)})
                elif file.suffix=='.png':
                    with Image.open(file) as im:im.verify()
                    images.append({'file':file.relative_to(out).as_posix(),'sha256':artifact_sha256(file)})
            for name in ['preview.png','cut_detail.png']:
                im=Image.open(folder/name).convert('RGB');im.thumbnail((600,450))
                tile=Image.new('RGB',(620,480),'#eeeeee');tile.paste(im,((620-im.width)//2,5));ImageDraw.Draw(tile).text((10,460),slug+'/'+name,fill='black');tiles.append(tile)
    large_records=[]
    for plate in manifest.get('large_format_plates',[]):
        folder=out/plate['folder'];slug=plate['folder'].replace('/','_')
        result=verify_large_plate(out,plate);large_records.append(result)
        for file in sorted(folder.iterdir()):
            if file.suffix.lower() in ['.pdf','.ai']:
                prefix=qa/(slug+'_'+file.stem+file.suffix.replace('.','_'))
                subprocess.run(['pdftoppm','-r','70','-singlefile','-png',str(file),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                with fitz.open(file) as doc:
                    assert len(doc)==1 and all(abs(a-b)<.01 for a,b in zip([doc[0].rect.width*25.4/72,doc[0].rect.height*25.4/72],plate['canvas_mm'])),file
                with Image.open(str(prefix)+'.png') as im:im.verify()
                renders.append({'file':file.relative_to(out).as_posix(),'sha256':artifact_sha256(file)})
            elif file.suffix=='.png':
                with Image.open(file) as im:im.verify()
                images.append({'file':file.relative_to(out).as_posix(),'sha256':artifact_sha256(file)})
        for name in ['preview.png','cut_detail.png']:
            im=Image.open(folder/name).convert('RGB');im.thumbnail((600,450))
            tile=Image.new('RGB',(620,480),'#eeeeee');tile.paste(im,((620-im.width)//2,5));ImageDraw.Draw(tile).text((10,460),slug+'/'+name,fill='black');tiles.append(tile)
    contact=Image.new('RGB',(1240,480*math.ceil(len(tiles)/2)),'white')
    for i,t in enumerate(tiles):contact.paste(t,((i%2)*620,(i//2)*480))
    contact.save(qa/'contact.png')
    report={'revision':manifest['revision'],'errors':[],'repository':repository,'laser_path_audit':{'checked_files':laser['checked_files'],'errors':laser['errors'],'protected_original_findings':laser['protected_original_findings']},
        'a3_release':a3,'large_format_plates':large_records,'individual_assets':assets,'existing_print_recut':recut,'rendered_pdf_and_ai_pages':renders,'png_files_checked':images,'editor_cut_visibility':editor_visibility,'physical_cut_test':False,
        'coverage':{'current_pages_including_thickness_alternatives':a3['checked_pages'],'current_cut_formats':laser['checked_files'],'packages':len(a3['packages']),'rendered_pdf_and_ai_pages':len(renders),
        'large_format_plates':len(large_records),
        'existing_print_recovery_cut_files':len(recut['records']) if recut else 0,'recut_print_pages_added':0,
        'archived_previous_cut_files':126,'archive_cut_quality':'retired; not included in current pass count; exact backup bytes checked'},
        'limitations':a3['limitations']}
    if manifest.get('print_delivery'):
        assert manifest['print_delivery']==configured['print_delivery']
        report['print_delivery']=manifest['print_delivery']
        report['coverage']['physical_plates_to_print']=len(manifest['print_delivery']['plates'])
        report['production_delivery_files']=production_delivery_files(out,manifest['print_delivery']['plates'],laser)
    (out/'RELEASE_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report['coverage']),flush=True)
    return report

if __name__=='__main__':main()
