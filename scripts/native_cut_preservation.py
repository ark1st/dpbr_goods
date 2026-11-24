"""Replace only a native VectorCraft cut layer with source-precise SVG paths.

The PDF importer can quantize very short original segments into an invalid
intersection. Importing the approved cutting SVG separately preserves valid
topology; its original line/cubic controls are then written into the native
document as exact source coordinates. Artwork and embedded image bytes are
never rebuilt. Use the separately verified PDF/SVG for manufacturing.
"""
import argparse
import copy
import hashlib
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from svgpathtools import CubicBezier, Line, parse_path
from vector_utils import runvc

MM = 72 / 25.4


def _read_native(path):
    raw = Path(path).read_bytes()
    marker = b'\n\x00VCBLOBS\x00'
    end = raw.find(marker)
    assert end >= 0, 'Unsupported native blob format'
    header = json.loads(raw[:end].decode('utf-8'))
    assert header['format'] == 'vectorcraft' and header['version'] == 4
    return header, raw[end:]


def _svg_paths(path):
    root = ET.parse(path).getroot()
    assert root.get('viewBox') and [float(x) for x in root.get('viewBox').split()] == [0, 0, 420, 297]
    assert root.get('width', '').endswith('mm') and root.get('height', '').endswith('mm')
    assert abs(float(root.get('width')[:-2]) - 420) < .00001
    assert abs(float(root.get('height')[:-2]) - 297) < .00001
    assert not any(e.get('transform') for e in root.iter()), 'Transformed SVG paths are unsupported'
    paths = [e.get('d') for e in root.iter() if e.tag.endswith('}path')]
    assert paths and all(paths), 'Empty cutting SVG'
    return paths


def preserve_native_cut_layer(native_path, svg_path, output_path):
    """Copy cut paths into native while preserving every other layer/blob."""
    original, tail = _read_native(native_path)
    baseline_tail = hashlib.sha256(tail).hexdigest()
    source_paths = _svg_paths(svg_path)
    layers = original['document']['layers']
    targets = [layer for layer in layers if layer.get('name') == 'LASER_CUT']
    assert len(targets) == 1 and targets[0]['kind']['type'] == 'layer'
    untouched = copy.deepcopy([x for x in layers if x.get('name') != 'LASER_CUT'])
    image_descriptors = copy.deepcopy(original.get('images'))
    with tempfile.TemporaryDirectory(prefix='native-cuts-') as folder:
        svg_native = Path(folder) / 'cuts.vectorcraft'
        runvc(['convert', Path(svg_path).resolve(), svg_native])
        imported, _ = _read_native(svg_native)
    cut_layers = [x for x in imported['document']['layers'] if x.get('name') == 'LASER_CUT']
    assert len(cut_layers) == 1
    objects = cut_layers[0]['kind']['children']
    assert len(objects) == len(source_paths)
    first_id = original['document']['next_id']
    control_count = 0
    for i, (obj, source) in enumerate(zip(objects, source_paths, strict=True)):
        assert obj['kind']['type'] == 'path'
        subpaths = obj['kind']['path']['subpaths']
        assert len(subpaths) == 1
        closed = subpaths[0]['closed']
        anchors = subpaths[0]['anchors']
        segments = list(parse_path(source))
        assert len(anchors) == len(segments) + (not closed), ('Changed source path topology', i)
        for j, seg in enumerate(segments):
            here, following = anchors[j], anchors[(j+1) % len(anchors)]
            here['p'] = [seg.start.real * MM, seg.start.imag * MM]
            control_count += 1
            if isinstance(seg, CubicBezier):
                here['out'] = [seg.control1.real * MM, seg.control1.imag * MM]
                following['in'] = [seg.control2.real * MM, seg.control2.imag * MM]
                control_count += 2
            elif isinstance(seg, Line):
                assert 'out' not in here and 'in' not in following, ('Changed line into cubic', i, j)
            else:
                raise ValueError(('Unsupported original segment', i, type(seg).__name__))
        if not closed:
            anchors[-1]['p'] = [segments[-1].end.real * MM, segments[-1].end.imag * MM]
        obj['id'] = first_id + i
    targets[0]['kind']['children'] = objects
    original['document']['next_id'] = first_id + len(objects)
    # Its embedded compatible PDF is a cached serialization of the old layer.
    # Leaving it would serve stale invalid cuts to a PDF-only reader.
    original['pdfCompatible'] = False
    original.pop('pdf', None)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(json.dumps(original, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + tail)
    written, written_tail = _read_native(output_path)
    assert hashlib.sha256(written_tail).hexdigest() == baseline_tail
    assert written.get('images') == image_descriptors
    assert [x for x in written['document']['layers'] if x.get('name') != 'LASER_CUT'] == untouched
    return {'path': str(output_path), 'paths': len(objects), 'anchors_and_controls': control_count,
            'other_layers_unchanged': True, 'embedded_blobs_sha256': baseline_tail,
            'pdf_cache_removed': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('native_path', type=Path)
    parser.add_argument('svg_path', type=Path)
    parser.add_argument('output_path', type=Path)
    args = parser.parse_args()
    print(json.dumps(preserve_native_cut_layer(args.native_path, args.svg_path, args.output_path), ensure_ascii=False))
