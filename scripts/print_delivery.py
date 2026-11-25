"""Export registered print PNGs, cutter AI files and complete layered masters."""
import argparse
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from build_a3_release import ROOT, extract_layers
from pdf_layers import mark_pdf_layers

DELIVERY = ROOT / 'output/print_delivery'
PNG = '01_PRINT_300ppi.png'
AI = '02_CUT_WITH_BLUE.ai'
COMBINED_AI = '03_COMBINED_MASTER.ai'
SOURCES = {
    'page03': 'output/a3_release/11_ascent_remaining/3T/sheet_01',
    'alternative_page04': 'tmp/a3_options/alternative/page_04',
    'ascent_11_sets': 'tmp/ascent_11_sets',
}
REFERENCE_SOURCES = {'alternative_800x500': 'output/large_format/ascent_5T_800x500'}
COLORS = {'LASER_CUT': (1, 0, 0), 'CORNER_REFERENCE': (0, 0, 1)}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def vectors(page, layer):
    """Fingerprint all painted geometry including original controls and line styles."""
    assert not page.get_image_info() and not page.get_text().strip(), 'Unexpected art or text'
    result = []
    for draw in page.get_drawings():
        assert draw['type'] == 's' and draw['color'] == COLORS[layer], (layer, draw['type'], draw['color'])
        # Coordinates remain in the PDF page's original points.
        signature = [str(draw[k]) for k in ('items', 'width', 'closePath', 'lineCap',
                                              'lineJoin', 'dashes', 'stroke_opacity')]
        result.append(hashlib.sha256(json.dumps(signature).encode()).hexdigest())
    assert result and (layer != 'CORNER_REFERENCE' or len(result) == 1), layer
    return sorted(result)


def check_art_pair(directory, manifest):
    """Validate the two distributable files even when temporary nesting files are absent."""
    for name in (AI, PNG, COMBINED_AI):
        assert sha(directory / name) == manifest['sha256'][name], (directory, name)
    with fitz.open(directory / AI) as doc, Image.open(directory / PNG) as png:
        assert len(doc) == 1 and list(doc[0].rect) == manifest['page_rect_pt']
        layers = doc.get_ocgs().values()
        assert {r['name'] for r in layers} == set(COLORS) and all(r['on'] for r in layers)
        assert not doc[0].get_image_info() and not doc[0].get_text().strip()
        assert Counter(d['color'] for d in doc[0].get_drawings()) == Counter({
            COLORS[layer]: len(paths) for layer, paths in manifest['source_vectors'].items()
        })
        assert list(png.size) == manifest['png_pixels'] and png.mode == 'RGBA'
        assert all(abs(v - 300) < .01 for v in png.info['dpi'])
        assert all(abs(dim * 300 / 72 - px) <= 1 for dim, px in zip(doc[0].rect.br, png.size))
    for layer in COLORS:
        with extract_layers(directory / AI, [layer]) as subset:
            assert vectors(subset[0], layer) == manifest['source_vectors'][layer], (directory, layer)


def build_pair(key):
    relative = (SOURCES | REFERENCE_SOURCES)[key]
    source = ROOT / relative
    dest = DELIVERY / key
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest) as tmp:
        stage = Path(tmp)
        with fitz.open(source / '03_CUT_ONLY.pdf') as cut, extract_layers(
            source / '02_MASTER.pdf', ['CORNER_REFERENCE']
        ) as guide, fitz.open() as master:
            assert len(cut) == 1 and cut[0].rect == guide[0].rect
            sources = {'LASER_CUT': cut, 'CORNER_REFERENCE': guide}
            fingerprints = {layer: vectors(doc[0], layer) for layer, doc in sources.items()}
            rect = cut[0].rect
            page = master.new_page(width=rect.width, height=rect.height)
            streams = {}
            for layer, doc in sources.items():
                ocg = master.add_ocg(layer, on=True)
                page.show_pdf_page(page.rect, doc, 0)
                streams[ocg] = [master.xref_stream(page.get_contents()[-1])]
            mark_pdf_layers(page, streams)
            master.save(stage / AI, garbage=4, deflate=True)
        shutil.copyfile(source / PNG, stage / PNG)
        shutil.copyfile(source / '02_MASTER.pdf', stage / COMBINED_AI)
        with Image.open(stage / PNG) as png, fitz.open(source / '01_PRINT.pdf') as doc:
            assert len(doc) == 1 and doc[0].rect == rect
            pix = doc[0].get_pixmap(dpi=300, alpha=True)
            assert (pix.width, pix.height) == png.size and png.mode == 'RGBA'
            # PNG serialization unpremultiplies MuPDF's RGBA channels. Compare
            # decoded samples in the same representation, one strip at a time.
            from io import BytesIO
            with Image.open(BytesIO(pix.tobytes('png'))) as expected:
                del pix
                for y in range(0, png.height, 256):
                    box = (0, y, png.width, min(png.height, y + 256))
                    assert png.crop(box).tobytes() == expected.crop(box).tobytes(), (key, y)
            size = png.size
        manifest = {
            'source': relative, 'page_rect_pt': list(rect), 'png_pixels': list(size),
            'source_vectors': fingerprints, 'print_pdf_sha256': sha(source / '01_PRINT.pdf'),
            'sha256': {name: sha(stage / name) for name in (AI, PNG, COMBINED_AI)},
        }
        check_art_pair(stage, manifest)
        for name in (AI, PNG, COMBINED_AI):
            (stage / name).replace(dest / name)
        (dest / 'registration.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(key, size, 'vector drawings', {k: len(v) for k, v in fingerprints.items()}, flush=True)


def verify_delivery():
    for key, relative in (SOURCES | REFERENCE_SOURCES).items():
        directory = DELIVERY / key
        spec = json.loads((directory / 'registration.json').read_text())
        check_art_pair(directory, spec)
        source = ROOT / relative
        if source.is_dir():
            assert sha(source / PNG) == spec['sha256'][PNG]
            assert sha(source / '01_PRINT.pdf') == spec['print_pdf_sha256']
            with fitz.open(source / '03_CUT_ONLY.pdf') as cut, extract_layers(
                source / '02_MASTER.pdf', ['CORNER_REFERENCE']
            ) as guide:
                for layer, doc in [('LASER_CUT', cut), ('CORNER_REFERENCE', guide)]:
                    assert vectors(doc[0], layer) == spec['source_vectors'][layer]
    from verify_ascent_order import verify_order
    verify_order(DELIVERY/'ascent_11_sets')
    return list(SOURCES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plates', nargs='*')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        print(verify_delivery())
    else:
        for key in args.plates or SOURCES:
            build_pair(key)
