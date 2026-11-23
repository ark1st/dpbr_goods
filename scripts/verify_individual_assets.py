"""Check independent pieces against every corresponding A3 placement."""
import json, math
from pathlib import Path
from build_a3_release import ROOT,MM,CONFIG,extract_layers,polygon_of,transformed_cut_path,draw_path
from verify_laser_paths import contours
from artifact_hash import artifact_sha256
import pymupdf as fitz
from PIL import Image,ImageDraw
from shapely.geometry import Polygon

def main():
    base=ROOT/'output/individual_assets';m=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    a3=json.loads((ROOT/'output/a3_release/manifest.json').read_text(encoding='utf-8'))
    locations={}
    for group,pages in a3['groups'].items():
        for page in pages:
            spec=json.loads((ROOT/'output'/page['folder']/'validation.json').read_text(encoding='utf-8'))
            for p in spec['parts']:locations.setdefault(p['id'],[]).append((group,p))
    assert set(locations)=={a['id'] for a in m['assets']}
    assert len(m['assets'])==m['asset_count']
    personal=CONFIG.get('personal_fill_allocation',{})
    if personal:
        expected={ident:group for group,ids in personal.items() for ident in ids}
        policy=CONFIG['personal_fill_policy']
        expected_count=policy['stand_pieces']+policy['keyring_pieces']
        assert len(expected)==expected_count and set(expected)==set(policy['new_part_ids']),'Incomplete personal catalog'
        assert m['asset_count']==policy['baseline_asset_count']+expected_count,'Incomplete catalog of original and personal pieces'
        for ident,group in expected.items():
            assert [g for g,_ in locations.get(ident,[])]==[group],(ident,'Changed personal asset placement')
    canonical=json.loads((ROOT/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts']
    assert set(canonical)==set(locations)
    records=[];tiles=[];rendered=0
    qa=ROOT/'tmp/individual_qa';qa.mkdir(parents=True,exist_ok=True)
    for asset in m['assets']:
        folder=ROOT/'output'/asset['folder'];s=json.loads((folder/'asset.json').read_text(encoding='utf-8'))
        assert s['artwork_scale']==1 and s['rotation_degrees']==0 and s['pieces']==1
        assert sorted(s['a3_groups'])==sorted(g for g,p in locations[s['id']])
        for file,sha in s['files'].items():assert artifact_sha256(folder/file)==sha,(s['id'],file,'stale asset')
        expected=[Polygon(q) for q in s['parts'][0]['expected_paths']]
        assert len(expected)==s['closed_contours']
        from shapely import affinity
        fixed=canonical[s['id']]
        assert fixed['source_bounds_mm']==s['source_bounds_mm']
        for actual,path in zip(expected,fixed['paths']):
            source=affinity.translate(actual,-s['translation_mm'][0],-s['translation_mm'][1])
            assert source.boundary.hausdorff_distance(polygon_of(path).boundary)<.002
        worst=0
        for file in ['03_CUT_ONLY.pdf','02_MASTER.pdf','02_MASTER.ai']:
            doc=fitz.open(folder/file) if file.startswith('03') else extract_layers(folder/file,['LASER_CUT'])
            dims=[doc[0].rect.width/MM,doc[0].rect.height/MM]
            assert max(abs(a-b) for a,b in zip(dims,s['canvas_mm']))<.002
            actual=[polygon_of(q) for d in doc[0].get_drawings() for q in contours(d)]
            assert len(actual)==len(expected)
            for p,q in zip(actual,expected):
                delta=p.boundary.hausdorff_distance(q.boundary);assert delta<.002;worst=max(worst,delta)
        import xml.etree.ElementTree as ET
        svg=ET.parse(folder/'03_CUT_ONLY.svg')
        actual=[polygon_of(e.get('d')) for e in svg.iter() if e.tag.endswith('}path')]
        assert len(actual)==len(expected)
        assert max(p.boundary.hausdorff_distance(q.boundary) for p,q in zip(actual,expected))<.002
        # Convert local geometry back to source coordinates, then use the exact
        # A3 rigid transform. This independently detects shifted holes and tabs.
        from shapely import affinity
        for group,row in locations[s['id']]:
            assert max(abs(a-b) for a,b in zip(row['source_bounds_mm'],s['source_bounds_mm']))<.0001
            theta=math.radians(row['rotation_degrees']);c,si=math.cos(theta),math.sin(theta)
            bounds=s['source_bounds_mm'];origin=row.get('rotated_origin_mm')
            if origin is None:
                w,h=bounds[2]-bounds[0],bounds[3]-bounds[1]
                corners=[(c*x+si*y,-si*x+c*y) for x,y in [(0,0),(w,0),(0,h),(w,h)]]
                origin=[min(x for x,y in corners),min(y for x,y in corners)]
            for q,raw in zip(expected,row['expected_paths']):
                original=affinity.translate(q,-s['translation_mm'][0]-bounds[0],-s['translation_mm'][1]-bounds[1])
                mapped=affinity.affine_transform(original,[c,si,-si,c,0,0])
                mapped=affinity.translate(mapped,row['placed_bounds_mm'][0]-origin[0],row['placed_bounds_mm'][1]-origin[1])
                assert mapped.boundary.hausdorff_distance(Polygon(raw).boundary)<.002,(s['id'],'changed from A3')
        art=extract_layers(folder/'02_MASTER.pdf',['PRINT_ARTWORK'])
        pr=fitz.open(folder/'01_PRINT.pdf')
        assert art[0].get_pixmap(alpha=True).samples==pr[0].get_pixmap(alpha=True).samples
        for file in folder.iterdir():
            if file.suffix in ['.pdf','.ai']:
                with fitz.open(file) as doc:
                    pix=doc[0].get_pixmap(dpi=70,alpha=False)
                    assert pix.width>0 and pix.height>0;rendered+=1
                    if file.name=='02_MASTER.ai':pix.save(qa/(s['id']+'.png'))
            elif file.suffix=='.png':
                with Image.open(file) as im:im.verify()
        im=Image.open(qa/(s['id']+'.png')).convert('RGB');im.thumbnail((230,190))
        tile=Image.new('RGB',(250,220),'#f5f4ee');tile.paste(im,((250-im.width)//2,4))
        ImageDraw.Draw(tile).text((6,202),s['id'],fill='black');tiles.append(tile)
        records.append({'id':s['id'],'max_geometry_deviation_mm':worst,'a3_occurrences':len(locations[s['id']]),'files':s['files']})
    contact=Image.new('RGB',(1500,220*math.ceil(len(tiles)/6)),'white')
    for i,tile in enumerate(tiles):contact.paste(tile,((i%6)*250,(i//6)*220))
    contact.save(qa/'contact.png')
    result={'individual_assets':len(records),'cut_formats_per_asset':4,'rendered_pdf_ai_pages':rendered,
        'records':records,'errors':[],'physical_cut_test':False,
        'limitations':['Artwork isolated at600ppi; original source bytes remain pinned and archived.',
                       'Linked chain hardware is illustrative; physical ring dimensions and assembly are untested.']}
    (base/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'individual_assets_checked':len(records),'rendered_pages':rendered,'errors':0}),flush=True)
    return result

if __name__=='__main__':main()
