"""Validate A3 artifacts against source contours after rigid placement."""
from pathlib import Path
import sys,json,zipfile,math,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image
from shapely.geometry import Polygon
from build_a3_release import polygon_of,extract_layers,MM
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
    wanted={'02_extra_sheet/3T':38,'02_extra_sheet/5T':38,'03_linked_keyrings':8,'04_ascent_original':31,'05_len/3T':9,'05_len/5T':9}
    assert set(manifest['groups'])==set(wanted),'Incomplete A3 release'
    records=[]
    for group,pages in manifest['groups'].items():
        assert sum(p['pieces'] for p in pages)==wanted[group]
        assert len(pages)==(2 if 'ascent' in group else 1)
        protected_count=0;ids=[]
        for page in pages:
            folder=out/page['folder'];spec=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
            assert spec['canvas_mm']==[420,297] and spec['artwork_scale']==1
            assert spec['pieces']==page['pieces'] and spec['closed_contours']==page['contours']
            assert spec['minimum_gap_mm']>=2.998
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
        if 'extra' in group:assert protected_count==30
    packages=[]
    if check_zips:
        for file in sorted(base.glob('*.zip')):
            with zipfile.ZipFile(file) as z:
                assert z.testzip() is None
                for name in z.namelist():
                    if name.endswith('/'):continue
                    current=out/name
                    assert current.is_file(),(file,name)
                    assert artifact_sha256(current,z.read(name))==artifact_sha256(current),(file,name,'stale ZIP entry')
            assert file.stat().st_size<100*1024*1024,file
            packages.append({'file':file.relative_to(out).as_posix(),'bytes':file.stat().st_size,'sha256':artifact_sha256(file)})
        assert len(packages)==6,len(packages)
    result={'checked_pages':len(records),'native_geometry_checked':check_native,'records':records,'packages':packages,'errors':[],
            'source_artwork_scale':1,'physical_cut_test':False,
            'limitations':['Software checks do not validate physical kerf, material thickness or printer registration.',
                           'Ascent original has 26 upright plates but only 5 bases; quantity and interfaces preserved.',
                           'Ascent paired slots have original ~0.195mm vertical stagger; not silently aligned.',
                           'Native editing state is in .vectorcraft. Compact .ai retains PDF-compatible vector layers.']}
    (base/'A3_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'a3_pages_checked':len(records),'a3_packages':len(packages),'errors':0}),flush=True)
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--skip-native',action='store_true')
    main(check_native=not parser.parse_args().skip_native)
