"""Narrow verification of the user-provided, already-cut page-three baseline."""
import hashlib
import json
from pathlib import Path
from shapely.geometry import Polygon

# These are measured from the supplied AI, not adjustable nesting tolerances.
SOURCE_SHA256 = '3cfadac25e60f7650ac18dcf4f1972e078bff9a5adb6fab49b0b34ca51e82fc0'
BASELINE_GAPS = {
    frozenset(('fixed_06', 'fixed_14')): 2.2580706252261056,
    frozenset(('fixed_04', 'fixed_07')): 2.3025760601153182,
    frozenset(('fixed_13', 'fixed_14')): 2.7087347211384842,
}
BASELINE_EDGES = {
    'fixed_04': 7.355245375, 'fixed_09': 6.12241211328125,
    'fixed_10': 5.4631766, 'fixed_12': 5.4631766,
    'fixed_13': 5.4233164, 'fixed_14': 6.6726749,
    'fixed_16': 5.9708619, 'fixed_20': 6.139414878601599,
}
FIXED_IDS = {f'fixed_{i:02}' for i in range(1, 27)}


def _path(root, name):
    p = Path(name)
    return p if p.is_absolute() else root / p


def verify_frozen_pages(root, config):
    """Read only: detect byte changes to the two existing output folders."""
    pages = config['frozen_pages']
    assert len(pages) == 2 and len({p['folder'] for p in pages}) == 2
    for page in pages:
        folder = root / 'output' / page['folder']
        expected = page['files']
        assert expected and {p.name for p in folder.iterdir() if p.is_file()} == set(expected), (folder, 'Frozen file inventory changed')
        for name, digest in expected.items():
            assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest, (folder / name, 'Frozen file changed')


def check_page_geometry(parts, actual_paths=None):
    """Audit individual outer boundaries, with only measured baseline exceptions."""
    ids = [p['id'] for p in parts]
    assert len(ids) == len(set(ids)) and FIXED_IDS <= set(ids), 'Changed fixed source inventory'
    shapes = {}
    for part in parts:
        polygons = [Polygon(path) for path in part['expected_paths']]
        assert polygons and all(p.is_valid and p.area > 0 for p in polygons), (part['id'], 'Invalid path')
        shapes[part['id']] = max(polygons, key=lambda p: p.area)
    if actual_paths is not None:
        # Match each exported outer curve to its approved expected geometry. All
        # internal curves are independently checked by compare_geometry/audit.
        from build_a3_release import polygon_of
        available = [polygon_of(path) for path in actual_paths]
        for ident, expected in shapes.items():
            options = [(expected.boundary.hausdorff_distance(p.boundary), i) for i, p in enumerate(available)
                       if all(abs(a-b) < .01 for a, b in zip(expected.bounds, p.bounds))]
            assert options, (ident, 'Missing exported outer contour')
            delta, index = min(options)
            assert delta <= .002, (ident, 'Changed exported outer contour', delta)
            shapes[ident] = available.pop(index)
    gaps = {}
    for i, ident in enumerate(ids):
        shape = shapes[ident]
        x0, y0, x1, y1 = shape.bounds
        edge = min(x0, y0, 420-x1, 297-y1)
        required = BASELINE_EDGES.get(ident, 8.0)
        assert edge >= required - .002, (ident, 'Changed or insufficient edge margin', edge, required)
        if ident in BASELINE_EDGES:
            assert abs(edge-required) <= .002, (ident, 'Changed baseline edge', edge, required)
        for other in ids[:i]:
            gap = shape.distance(shapes[other])
            pair = frozenset((ident, other))
            if pair in BASELINE_GAPS:
                assert abs(gap-BASELINE_GAPS[pair]) <= .002, (tuple(pair), 'Changed baseline gap', gap)
                gaps[tuple(sorted(pair))] = gap
            else:
                assert gap >= 2.998, (ident, other, 'New or unapproved gap below 3mm', gap)
    assert len(gaps) == len(BASELINE_GAPS), 'Missing baseline exception'
    return {'baseline_gap_exceptions_mm': {' / '.join(k): v for k, v in sorted(gaps.items())},
            'baseline_edge_exceptions_mm': dict(BASELINE_EDGES),
            'new_piece_minimum_gap_mm': 3, 'new_piece_minimum_edge_mm': 8}


def verify_exported_paths(spec, actual_paths):
    """Match every exported curve, including interior holes, to its reviewed path."""
    from build_a3_release import polygon_of
    expected = [Polygon(q) for part in spec['parts'] for q in part['expected_paths']]
    actual = [polygon_of(path) for path in actual_paths]
    assert len(expected) == len(actual), 'Changed exported path inventory'
    remaining = set(range(len(actual)))
    for path in expected:
        candidates = [i for i in remaining if all(abs(a-b)<.01 for a,b in zip(path.bounds,actual[i].bounds))]
        assert candidates, ('Missing exported path',path.bounds)
        delta,index = min((path.boundary.hausdorff_distance(actual[i].boundary),i) for i in candidates)
        assert delta <= .002, ('Changed exported path',delta,path.bounds)
        remaining.remove(index)


def verify_fixed_source(root, config, spec):
    """Re-read the pinned source AI; compare all 73 fixed curves to exported spec."""
    from build_a3_release import polygon_of
    from verify_laser_paths import contours
    import pymupdf as fitz
    assert config['source_sha256'] == SOURCE_SHA256
    source_path = _path(root, config['source_file'])
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == SOURCE_SHA256, 'Fixed source AI changed'
    geometry = json.loads(_path(root, config['geometry_file']).read_text(encoding='utf-8'))
    assert geometry['sha256'] == SOURCE_SHA256 and geometry['red_closed_curves'] == 73
    originals = {p['id']: p for p in geometry['parts']}
    assert set(originals) == FIXED_IDS
    parts = {p['id']: p for p in spec['parts'] if p['id'] in FIXED_IDS}
    assert set(parts) == FIXED_IDS
    with fitz.open(source_path) as source:
        drawings = source[0].get_drawings()
        count = 0
        for ident, original in originals.items():
            entries = [original['source_outer'], *original['source_holes']]
            expected = [Polygon(p) for p in parts[ident]['expected_paths']]
            assert len(expected) == len(entries), (ident, 'Changed source contour count')
            for entry, actual in zip(entries, expected):
                draw, subpath = map(int, entry['label'].split(':'))
                source_path_data = contours(drawings[draw])[subpath]
                original_poly = polygon_of(source_path_data)
                assert original_poly.boundary.hausdorff_distance(polygon_of(entry['path']).boundary) <= .002, (ident, 'Baseline geometry does not match source AI')
                assert original_poly.boundary.hausdorff_distance(actual.boundary) <= .002, (ident, 'Changed source contour')
                count += 1
        assert count == 73
    return check_page_geometry(spec['parts'])


def verify_fixed_artwork(root, config, master):
    """Ensure all source images and the blue reference survive at their positions."""
    import pymupdf as fitz
    from collections import Counter
    from build_a3_release import MM

    def image_records(doc):
        page = doc[0]
        masks = {item[0]: item[1] for item in page.get_images(full=True)}
        rows = []
        for image in page.get_image_info(hashes=True, xrefs=True):
            mask = masks.get(image['xref'], 0)
            mask_digest = hashlib.sha256(fitz.Pixmap(doc, mask).samples).hexdigest() if mask else None
            rows.append((image['digest'].hex(), mask_digest,
                         tuple(round(v / MM, 3) for v in image['bbox'])))
        return Counter(rows)

    with fitz.open(_path(root, config['source_file'])) as source, fitz.open(master) as result:
        source_images, result_images = image_records(source), image_records(result)
        assert sum(source_images.values()) == 21
        assert not source_images - result_images, 'Source artwork images changed or moved'
        def blue(doc):
            return [d for d in doc[0].get_drawings() if d['color'] is not None
                    and d['color'][0] < .01 and d['color'][1] < .01 and d['color'][2] > .99]
        source_blue, result_blue = blue(source), blue(result)
        assert len(source_blue) == 1, 'Unexpected source blue reference'
        orig = source_blue[0]
        assert any(abs(d['width']-orig['width']) < .002 and
                   all(abs(a-b) < .005 for a,b in zip(d['rect'], orig['rect']))
                   for d in result_blue), 'Blue reference changed or moved'


def verify_fixed_additions(root, spec):
    """Check each requested design and the number of loose-keyring holes."""
    from collections import Counter
    from build_a3_release import polygon_of, shifted_poly
    plan = json.loads((root/'configs/fixed_page3_additions.json').read_text(encoding='utf-8'))
    canonical = json.loads((root/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts']
    rows = plan['placements']
    ids = [r['id'] for r in rows]
    assert len(ids) == len(set(ids)) and not (set(ids) & FIXED_IDS)
    mandatory = {
        'remsha_stand_body':'remsha_stand_body', 'remsha_stand_base':'remsha_stand_base',
        'remsha_keyring':'remsha_keyring', 'redflower_stand_body':'redflower_stand_body',
        'redflower_stand_base':'redflower_stand_base', 'redflower_keyring':'redflower_keyring',
        'zero_duo_stand_body':'zero_duo_stand_body', 'zero_duo_stand_base':'zero_duo_stand_base',
        'zero_duo_keyring':'zero_duo_keyring', 'page3_tuiing_01':'tuiing_01', 'page3_golden_01':'golden_01',
        'page3_burnt_01':'burnt_01', 'page3_unfried_01':'unfried_01',
    }
    assignments = {r['id']:r['source_id'] for r in rows}
    assert all(assignments.get(ident)==source for ident,source in mandatory.items()), 'Missing a requested addition'
    extras = {ident:source for ident,source in assignments.items() if ident not in mandatory}
    for ident,source in extras.items():
        assert source in ('muhani_stand_body','muhani_stand_base','muhani_keyring')
        assert ident.startswith(source+'_') and ident[len(source)+1:].isdigit(), (ident, 'Unexpected repeat')
    counts = Counter(extras.values())
    sets, extra_keyrings = verify_muhani_counts(counts)
    parts = {p['id']:p for p in spec['parts']}
    assert set(parts)==FIXED_IDS | set(ids), 'Unexpected fixed-page inventory'
    for ident, source in assignments.items():
        part = parts[ident]
        original = canonical[source]
        if source in ('remsha_keyring','redflower_keyring','muhani_keyring','zero_duo_keyring'):
            assert len(original['paths'])==2, (ident, 'Expected one upper hole and one exterior')
            hole,outer=map(polygon_of,original['paths'])
            assert outer.contains(hole) and hole.centroid.y < outer.centroid.y, ident
        assert part['scale']==1 and len(part['expected_paths'])==len(original['paths']), ident
        assert max(abs(a-b) for a,b in zip(part['source_bounds_mm'],original['source_bounds_mm']))<.0001, ident
        place={'piece':{'bounds':part['source_bounds_mm']},'rotation':part['rotation_degrees'],
               'x':part['placed_bounds_mm'][0],'y':part['placed_bounds_mm'][1],
               'rotated_origin':part.get('rotated_origin_mm')}
        remaining=[Polygon(q) for q in part['expected_paths']]
        for path in original['paths']:
            expected=shifted_poly(polygon_of(path),place)
            delta,index=min((expected.boundary.hausdorff_distance(p.boundary),i) for i,p in enumerate(remaining))
            assert delta<.002, (ident, 'Addition geometry differs from canonical', delta)
            remaining.pop(index)
    return {'required_additions':len(mandatory),'complete_muhani_sets':sets,
            'extra_muhani_keyrings':extra_keyrings}


def verify_muhani_counts(counts):
    bodies=counts['muhani_stand_body']; bases=counts['muhani_stand_base']; keys=counts['muhani_keyring']
    assert bodies==bases and bodies>0 and keys>=bodies, 'Incomplete Muhani set'
    return bodies,keys-bodies
