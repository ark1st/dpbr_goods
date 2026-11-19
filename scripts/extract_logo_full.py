"""Extract the original symbol + outlined wordmark without redrawing either."""
from pathlib import Path
import sys
import json
import hashlib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pylibs'))
from svgpathtools import parse_path
from vector_utils import runvc, SVG


def extract():
    temp = ROOT / 'tmp/logo_diorama'
    temp.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'assets/source_logo.ai'
    converted = temp / 'source_logo.svg'
    runvc(['convert', source, converted])
    root = ET.parse(converted).getroot()
    group = next(e for e in root.iter() if e.get('id') == '기본')
    paths = [e for e in group.iter() if e.tag == f'{{{SVG}}}path']
    assert len(paths) == 38, 'Unexpected source lockup; inspect original AI before extracting'
    assert not any(e.get('transform') for e in group.iter())
    bounds = [parse_path(e.get('d')).bbox() for e in paths]
    x0, x1 = min(b[0] for b in bounds), max(b[1] for b in bounds)
    y0, y1 = min(b[2] for b in bounds), max(b[3] for b in bounds)
    width, height = x1-x0, y1-y0
    ET.register_namespace('', SVG)
    output = ET.Element(f'{{{SVG}}}svg', {
        'width': f'{width:.9f}', 'height': f'{height:.9f}',
        'viewBox': f'{x0:.9f} {y0:.9f} {width:.9f} {height:.9f}'})
    ET.SubElement(output, f'{{{SVG}}}title').text = '단풍바람 - 원본 심벌과 전체 이름'
    output.append(group)
    ET.ElementTree(output).write(ROOT / 'assets/logo_full.svg', encoding='utf-8', xml_declaration=True)
    provenance = {
        'source': 'assets/source_logo.ai',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'extracted_svg_sha256': hashlib.sha256((ROOT / 'assets/logo_full.svg').read_bytes()).hexdigest(),
        'source_group': '기본', 'path_count': len(paths),
        'symbol_paths': 7, 'outlined_wordmark_paths': 31,
        'source_viewbox': [x0, y0, width, height],
        'aspect_ratio': width/height,
        'changes': 'None: original path data, fills and relative positions retained.'}
    (ROOT / 'assets/logo_full_provenance.json').write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(provenance, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    extract()
