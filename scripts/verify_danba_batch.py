"""Check keyring contours, hole strength and artwork registration on the mixed A3 sheet."""
from collections import Counter
from itertools import combinations
import json
from xml.etree import ElementTree
import numpy as np
import pymupdf as fitz
from PIL import Image, ImageDraw
from shapely.geometry import MultiPoint

from artifact_hash import artifact_sha256
from build_a3_release import ROOT, MM, extract_layers, polygon_of, shifted_poly
from fixed_page3_checks import verify_exported_paths
from verify_laser_paths import contours

SOURCE = ROOT/'output/individual_assets/danba_logo_smooth'


def basis_points(image):
    matrix = fitz.Matrix(*image['transform'])
    return MultiPoint([tuple(v/MM for v in fitz.Point(x,y)*matrix)
                       for x,y in ((0,0),(1,0),(0,1))])


def signature(doc, image):
    mask, = {row[1] for row in doc[0].get_images() if row[0]==image['xref']}
    assert mask>0
    return image['width'], image['height'], image['digest'], fitz.Pixmap(doc,mask).digest


def verify_layer(master, layer, original, places, outer, hole):
    with fitz.open(original) as src, extract_layers(master,[layer]) as actual:
        source_image, = src[0].get_image_info(xrefs=True)
        source_sig = signature(src,source_image)
        assert not actual[0].get_text().strip()
        if layer=='WHITE_INK_MASK':
            assert not actual[0].get_drawings(), 'Unexpected vector white ink'
        rendered = src[0].get_pixmap(dpi=600,alpha=True)
        alpha = np.frombuffer(rendered.samples,np.uint8).reshape(rendered.height,rendered.width,-1)[:,:,-1]
        allowed = Image.new('L',(rendered.width,rendered.height))
        draw = ImageDraw.Draw(allowed)
        for shape,color in [(outer,255),(hole,0)]:
            draw.polygon([(x*600/25.4,y*600/25.4) for x,y in shape.exterior.coords],fill=color)
        assert np.any(alpha) and not np.any(alpha[np.asarray(allowed)==0]), (layer,'Source ink touches cut')
        images = actual[0].get_image_info(xrefs=True)
        assert len(images)==len(places)
        by_xref = {im['xref']:im for im in images}
        assert all(signature(actual,im)==source_sig for im in by_xref.values()),(layer,'Image pixels or alpha changed')
        remaining = [np.asarray([point.coords[0] for point in basis_points(im).geoms]) for im in images]
        basis = basis_points(source_image)
        for place in places:
            expected = np.asarray([p.coords[0] for p in shifted_poly(basis,place).geoms])
            delta,idx = min((float(np.abs(expected-points).max()),i) for i,points in enumerate(remaining))
            assert delta<.003,(layer,'Image moved relative to cut',delta)
            remaining.pop(idx)


def canonical_view(image, row, outer):
    """Sample a character at fixed positions in its original, upright coordinate frame."""
    from math import cos, sin, radians, ceil
    angle = radians(row['rotation_degrees'])
    c,s = cos(angle),sin(angle)
    pxmm = 300/25.4
    # Six samples/mm resolves the fine details of these small vector characters.
    resolution = 6
    x,y,right,bottom = outer.bounds
    width,height = ceil((right-x)*resolution),ceil((bottom-y)*resolution)
    ox,oy = row['rotated_origin_mm']
    tx,ty = row['placed_bounds_mm'][:2]
    sx,sy = row['source_bounds_mm'][:2]
    dx,dy = x-sx,y-sy
    affine = (pxmm*c/resolution, pxmm*s/resolution, pxmm*(tx-ox+c*dx+s*dy),
              -pxmm*s/resolution, pxmm*c/resolution, pxmm*(ty-oy-s*dx+c*dy))
    view = image.transform((width,height),Image.Transform.AFFINE,affine,Image.Resampling.BILINEAR)
    valid=Image.new('L',(width,height))
    ImageDraw.Draw(valid).polygon([((px-x)*resolution,(py-y)*resolution)
                                  for px,py in outer.exterior.coords],fill=255)
    return np.asarray(view,dtype=float)[np.asarray(valid)>0]


def verify_characters(folder, rows, templates):
    """Use the pinned earlier Garam/Danpaengi print as the independent artwork reference."""
    from print_delivery import PNG
    earlier = ROOT/'output/print_delivery/alternative_page04'
    layout=json.loads((ROOT/'output/a3_options/alternative/page_04/layout.json').read_text())
    with Image.open(earlier/PNG) as prev, Image.open(folder/PNG) as final:
        prev=prev.convert('RGBa')
        final=final.convert('RGBa')
        refs={}
        for name in {r['canonical_id'] for r in rows}:
            source = next(r for r in layout['parts'] if r['canonical_id']==name)
            outer = polygon_of(templates[name][-1])
            refs[name]=(outer,canonical_view(prev,source,outer))
        for row in rows:
            outer,expected = refs[row['canonical_id']]
            actual = canonical_view(final,row,outer)
            errors=np.abs(actual-expected)
            assert expected[:,3].mean()>10 and errors.mean()<2.0 and (errors>40).mean()<.025, (
                row['id'],'Changed character artwork or placement',errors.mean())


def verify_batch(folder):
    from print_delivery import AI, COMBINED_AI, vectors
    layout = json.loads((folder/'layout.json').read_text())
    plan = json.loads((ROOT/'configs/danba_batch_placements.json').read_text())
    design = json.loads((ROOT/'configs/danba_mass_contour.json').read_text())
    asset = json.loads((SOURCE/'asset.json').read_text())
    for name in ('01_PRINT.pdf','04_WHITE_INK_MASK.pdf','03_CUT_ONLY.svg'):
        assert artifact_sha256(SOURCE/name)==asset['files'][name]==design['source_sha256'][name]
    old = [p.get('d') for p in ElementTree.parse(SOURCE/'03_CUT_ONLY.svg').iter()
           if p.tag.endswith('}path')]
    character_specs = json.loads((ROOT/'configs/danba_character_keyrings.json').read_text())
    templates = {f'danba_{name}_keyring':spec['paths'] for name,spec in character_specs.items()}
    templates['danba_mass_contour'] = design['paths']
    hole_path, outer_path = design['paths']
    assert hole_path==old[0] and outer_path!=old[-1]
    shapes = {name:tuple(map(polygon_of,paths)) for name,paths in templates.items()}
    for name,(hole,outer) in shapes.items():
        assert outer.contains(hole) and outer.boundary.distance(hole.boundary)>=2.999, name
        assert max(abs(a-b-4) for a,b in zip(hole.bounds[2:],hole.bounds[:2]))<.015, name
        assert hole.centroid.y<outer.centroid.y, name
    rows = layout['parts']
    assert layout['canvas_mm']==[420,297] and layout['stock']=='3T'
    assert len(rows)==len({r['id'] for r in rows})==layout['pieces'] and rows
    assert layout['closed_contours']==2*len(rows)
    counts=Counter(row['canonical_id'] for row in rows)
    assert set(counts)==set(templates)
    assert layout['ratio']==plan['ratio']=={
        'danba_mass_contour':4,'danba_garam_keyring':1,'danba_danpaengi_keyring':1}
    assert counts==layout['counts']=={k:counts['danba_garam_keyring']*n for k,n in plan['ratio'].items()}
    assert counts['danba_garam_keyring']>=layout['rectangular_baseline_sets']>=1
    places,exteriors,expected = [],[],[]
    characters=[]
    for row,pose in zip(rows,plan['placements'],strict=True):
        assert row['scale']==1 and row['path_count']==2
        bounds = row['placed_bounds_mm']
        name=row['canonical_id']
        assert name==pose['source_id'] and row['rotation_degrees']==pose['rotation'],row['id']
        assert abs(bounds[0]-pose['x'])<.002 and abs(bounds[1]-pose['y'])<.002,row['id']
        row_hole,row_outer=shapes[name]
        assert max(abs(a-b) for a,b in zip(row['source_bounds_mm'],row_outer.bounds,strict=True))<.002
        place={'piece':{'bounds':row_outer.bounds},'x':bounds[0],'y':bounds[1],
               'rotated_origin':row['rotated_origin_mm'],'rotation':row['rotation_degrees']}
        placed=[shifted_poly(q,place) for q in (row_hole,row_outer)]
        assert max(abs(a-b) for a,b in zip(placed[1].bounds,bounds,strict=True))<.002
        if name=='danba_mass_contour':
            places.append(place)
        else:
            characters.append(row)
        exteriors.append(placed[1])
        expected.append({'expected_paths':[q.exterior.coords for q in placed]})
    gap = min(a.distance(b) for a,b in combinations(exteriors,2))
    edge = min(min(x,y,420-r,297-b) for x,y,r,b in (q.bounds for q in exteriors))
    assert gap>=2.998 and abs(gap-layout['minimum_gap_mm'])<.002,(gap,layout['minimum_gap_mm'])
    assert edge>=7.998 and abs(edge-layout['minimum_margin_mm'])<.002,(edge,layout['minimum_margin_mm'])
    with extract_layers(folder/AI,['LASER_CUT']) as cutter:
        paths=[path for d in cutter[0].get_drawings() for path in contours(d)]
        verify_exported_paths({'parts':expected},paths)
    guide = 'CORNER_REFERENCE'
    prior = ROOT/'output/a3_release/19_personal_fill/3T/sheet_01/02_MASTER.pdf'
    with extract_layers(prior,[guide]) as source, extract_layers(folder/AI,[guide]) as actual:
        assert vectors(source[0],guide)==vectors(actual[0],guide), 'Blue A3 registration moved'
    hole,outer = shapes['danba_mass_contour']
    for layer,name in [('PRINT_ARTWORK','01_PRINT.pdf'),('WHITE_INK_MASK','04_WHITE_INK_MASK.pdf')]:
        verify_layer(folder/COMBINED_AI,layer,SOURCE/name,places,outer,hole)
    verify_characters(folder,characters,templates)
    print(f'Danba A3: {dict(counts)}, {len(paths)} cut loops, '
          f'minimum gap {gap:.3f} mm, edge {edge:.3f} mm',flush=True)
