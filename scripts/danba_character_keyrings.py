"""Original 4 mm keyrings with the current Garam and Danpaengi vector masters."""
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
