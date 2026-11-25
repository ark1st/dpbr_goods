"""Load artwork and cut paths for the characters on the Danba keyring sheet."""
from functools import lru_cache
import json
from xml.etree import ElementTree
import pymupdf as fitz
from build_a3_release import ROOT, MM, polygon_of
from vector_utils import runvc


@lru_cache(None)
def garam_danpaengi_pieces():
    result = {}
    specs = json.loads((ROOT/'configs/danba_character_keyrings.json').read_text())
    temp = ROOT/'tmp/danba-character-keyrings'
    temp.mkdir(parents=True, exist_ok=True)
    for name, spec in specs.items():
        source = ROOT/'assets/masters'/f'{name}.svg'
        svg = ElementTree.parse(source).getroot()
        w, h = [float(svg.get(k).removesuffix('mm')) for k in ('width', 'height')]
        x, y = spec['art_origin_mm']
        art_pdf = temp/f'{name}.pdf'
        runvc(['convert', source, art_pdf])
        art = fitz.open()
        page = art.new_page(width=100*MM, height=100*MM)
        with fitz.open(art_pdf) as artwork:
            page.show_pdf_page(fitz.Rect(x*MM,y*MM,(x+w)*MM,(y+h)*MM),artwork,0)
        paths = spec['paths']
        outer = polygon_of(paths[-1])
        ident = f'danba_{name}_keyring'
        result[ident] = dict(id=ident, paths=paths, poly=outer, bounds=outer.bounds,
                             source_bounds_mm=list(outer.bounds), art=art)
    return result


@lru_cache(None)
def supplied_saetui_pieces():
    """Use the four small supplied chain links at their registered size."""
    result = {}
    for index in range(1, 5):
        ident = f'supplied_saetui_{index:02}'
        folder = ROOT/'output/individual_assets'/ident
        svg = ElementTree.parse(folder/'03_CUT_ONLY.svg')
        paths = [p.attrib['d'] for p in svg.findall('.//{http://www.w3.org/2000/svg}path')]
        top, bottom, outer = map(polygon_of, paths)
        assert outer.contains(top) and outer.contains(bottom) and top.centroid.y < bottom.centroid.y
        result[ident] = dict(id=ident, paths=paths, poly=outer, bounds=outer.bounds,
                             art=fitz.open(folder/'01_PRINT.pdf'),
                             white=fitz.open(folder/'04_WHITE_INK_MASK.pdf'))
    return result
