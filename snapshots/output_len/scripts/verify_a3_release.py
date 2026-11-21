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
    assert set(manifest['groups'])==set(wanted),'Incomplete A3 release'
    assert CONFIG['include_test_pieces'] is False and manifest['test_pieces_included'] is False
    records=[]
    for group,pages in manifest['groups'].items():
        assert sum(p['pieces'] for p in pages)==wanted[group]
        assert len(pages)==1
        protected_count=0;ids=[]
        for page in pages:
            folder=out/page['folder'];spec=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
            assert spec['canvas_mm']==[420,297] and spec['artwork_scale']==1
            assert spec['pieces']==page['pieces'] and spec['closed_contours']==page['contours']
            assert spec['minimum_gap_mm']>=2.998
            if group.startswith('05_len/'):
                assert spec['layout_method']=='15-degree contour nesting'
                assert all(p['rotation_degrees']%15==0 and p.get('rotated_origin_mm') is not None for p in spec['parts'])
            protected_count+=sum(p['protected_original'] for p in spec['parts'])
            ids.extend(p['id'] for p in spec['parts'])
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
        if group=='04_ascent_cadena':assert set(ids)==set(CONFIG['cadena_source_part_ids'])
        if group.startswith('05_len/'):
            t=group.split('/')[-1]
            assert sum(x.startswith(f'len_{t}_') for x in ids)==7
            assert sum(x.startswith(f'len_dot_{t}_') for x in ids)==1
            assert set(CONFIG['linked_allocation']['05_len']).issubset(ids)
        # Exactly four assigned keyrings on each page, never duplicates or extra designs.
        keyids=sum(CONFIG['linked_allocation'].values(),[])
        expected_keys=CONFIG['linked_allocation'].get(group.split('/')[0],[])
        assert sorted(x for x in ids if x in keyids)==sorted(expected_keys)
    packages=[]
    if check_zips:
        for group in sorted(wanted):
            file=base/(group.replace('/','_')+'_A3.zip')
            with zipfile.ZipFile(file) as z:
                assert z.testzip() is None
                for name in z.namelist():
                    if name.endswith('/'):continue
                    current=out/name
                    assert current.is_file(),(file,name)
                    assert artifact_sha256(current,z.read(name))==artifact_sha256(current),(file,name,'stale ZIP entry')
            assert file.stat().st_size<100*1024*1024,file
            packages.append({'file':file.relative_to(out).as_posix(),'bytes':file.stat().st_size,'sha256':artifact_sha256(file)})
        assert len(packages)==len(wanted),len(packages)
    result={'checked_pages':len(records),'native_geometry_checked':check_native,'records':records,'packages':packages,'errors':[],
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
