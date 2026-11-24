"""Sources for additions to the immutable user-supplied third acrylic plate."""
from pathlib import Path
import json
import pymupdf as fitz
from shapely.geometry import box
from laser_paths import audit_path
from build_a3_release import ROOT, MM, extract_layers, polygon_of, pieces_from, apply_canonical_contours
from reference_cut_style import build_reference_additions
from source_cache import source_path, restore_inputs


def templates():
    reference=ROOT/'assets/incoming/fixed_page3.ai'
    records=build_reference_additions(reference,ROOT/'tmp/fixed_page3_prepared',ROOT/'assets/incoming/muhani.png')
    names={'렘샤_stand':'remsha_stand_body','렘샤_star_base':'remsha_stand_base',
           '적매화검_stand':'redflower_stand_body','적매화검_star_base':'redflower_stand_base',
           '렘샤_keyring':'remsha_keyring','적매화검_keyring':'redflower_keyring','무한이_keyring':'muhani_keyring',
           '마가다락방_keyring':'zero_duo_keyring','마가다락방_stand':'zero_duo_stand_body','마가다락방_star_base':'zero_duo_stand_base'}
    result={}
    for row in records:
        ident=names[row['id']]; paths=[]
        for path in row['paths']:
            stats,poly=audit_path(path)
            paths.append(dict(path=path,poly=poly,stats=stats,protected=False,deviation=0.))
        art=fitz.open();page=art.new_page(width=420*MM,height=297*MM)
        if row.get('image'):
            page.insert_image(fitz.Rect(*(v*MM for v in row['art_rect_mm'])),filename=str(ROOT/row['image']) if not Path(row['image']).is_absolute() else row['image'])
        outer=max((e['poly'] for e in paths),key=lambda p:p.area)
        result[ident]=dict(id=ident,source='fixed_page3_reference_style',paths=paths,poly=outer,
            bounds=outer.bounds,art=art,white=None,design_metadata={k:v for k,v in row.items() if k not in ('paths','image')})
    geometry=json.loads((ROOT/'configs/fixed_page3_source_geometry.json').read_text())
    art=extract_layers(reference,['PRINT_ARTWORK'])
    stand=next(p for p in geometry['parts'] if abs(p['bounds_mm'][2]-413.860585)<.001)
    # The supplied Muhani uses these exact insert and mounting-base vectors.
    base=next(p for p in geometry['parts'] if len(p['source_holes'])==2 and
              any(abs((polygon_of(h['path']).bounds[2]-polygon_of(h['path']).bounds[0])-15.912)<.02 for h in p['source_holes']))
    for ident,row,artdoc in [('muhani_stand_body',stand,art),('muhani_stand_base',base,None)]:
        paths=[]
        for entry in [*row['source_holes'],row['source_outer']]:
            stats,poly=audit_path(entry['path']);paths.append(dict(path=entry['path'],poly=poly,stats=stats,protected=False,deviation=0.))
        outer=max((e['poly'] for e in paths),key=lambda p:p.area)
        result[ident]=dict(id=ident,source='fixed_page3_exact_muhani_copy',paths=paths,poly=outer,bounds=outer.bounds,
            art=artdoc,white=None,design_metadata={'reference_part_id':row['id'],'exact_reference_vectors':True})
    restore_inputs()
    for name in ['tuiing','golden','burnt','unfried']:
        folder=source_path(f'output/linked_tuiing_v1/{name}/02_MASTER.ai').parent
        ink=extract_layers(folder/'02_MASTER.ai',['PRINT_ARTWORK','3_ARTWORK','2_ARTWORK'])
        p=pieces_from(fitz.open(folder/'03_CUT_ONLY.pdf'),ink,fitz.open(folder/'04_WHITE_INK_MASK.pdf'),name)[0]
        apply_canonical_contours(p);result[p['id']]=p
    for piece in result.values():
        original=[e['poly'] for e in piece['paths']]
        apply_canonical_contours(piece)
        if piece['id'] not in ['tuiing_01','golden_01','burnt_01','unfried_01']:
            # Canonical exterior review must never alter copied mounting parts.
            exact=(piece.get('design_metadata') or {}).get('exact_reference_vectors')
            indexes=range(len(original)) if piece['id'].endswith('_base') or exact else range(len(original)-1)
            assert all(original[i].boundary.hausdorff_distance(piece['paths'][i]['poly'].boundary)<.000002 for i in indexes),piece['id']
            meta=piece.get('design_metadata') or {}
            if meta.get('tab_depth_mm'):
                cx=original[0].centroid.x;depth=meta['tab_depth_mm'];width=meta['tab_width_mm'];bottom=piece['bounds'][3]
                zone=box(cx-width/2-.1,bottom-depth+.04,cx+width/2+.1,bottom+.1)
                assert original[-1].intersection(zone).boundary.hausdorff_distance(piece['poly'].intersection(zone).boundary)<.002,piece['id']
    return result


def additions():
    plan=json.loads((ROOT/'configs/fixed_page3_additions.json').read_text())
    source=templates();result=[]
    for row in plan['placements']:
        original=source[row['source_id']]
        result.append({**original,'id':row['id'],'canonical_id':row['source_id']})
    return result
