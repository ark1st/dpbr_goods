"""Expose artwork-only editable SVG masters alongside their source references."""
from pathlib import Path
import json
from vector_utils import svg_doc

ROOT=Path(__file__).resolve().parents[1]


def main():
    assets=json.loads((ROOT/'assets/artwork.json').read_text(encoding='utf-8'))
    dest=ROOT/'assets/masters';dest.mkdir(parents=True,exist_ok=True)
    for name,key in [('garam','garam'),('danpaengi','danpaengi'),('logo_symbol','solo_logo')]:
        art=assets[key]
        (dest/f'{name}.svg').write_text(svg_doc(art['w'],art['h'],art['inner'],f'{name} / artwork-only editable master'),encoding='utf-8')
    print('Exported three artwork-only SVG masters; no cut lines or production layout.')


if __name__=='__main__':main()
