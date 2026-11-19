"""Place the two supplied VectorCraft AI layouts on one acrylic sheet at 100%."""

import argparse
from contextlib import ExitStack
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf as fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, FloatObject, NameObject, NumberObject
from reportlab.lib.units import mm
from vector_utils import runvc

OUT = Path(__file__).resolve().parents[1] / 'output/extra_sheet'
WIDTH, HEIGHT = 640, 225
DPI = 300
CUT_WIDTH = 0.001 * mm


def export_layer(reader, name):
    """Extract a VectorCraft layer, whose marked content wraps a single PDF form."""
    source = reader.pages[0]
    resources = source['/Resources']
    groups = resources['/Properties']
    operations = source.get_contents().operations
    for i, (operands, operator) in enumerate(operations):
        if operator == b'BDC' and operands[0] == '/OC' and groups[operands[1]]['/Name'] == name:
            draw, end = operations[i + 1:i + 3]
            if draw[1] != b'Do' or end[1] != b'EMC':
                raise ValueError(f'Unexpected VectorCraft layer structure: {name}')
            break
    else:
        raise ValueError(f'Missing source layer: {name}')

    writer = PdfWriter()
    page = writer.add_page(source)
    forms = page['/Resources']['/XObject']
    form_key = draw[0][0]
    for key in list(forms):
        if key != form_key:
            del forms[key]
    if name == '칼선':
        form = forms[form_key]
        content = ContentStream(form, writer)
        supported = {b'q', b'Q', b'cm', b'K', b'w', b'm', b'l', b'c', b'h', b'S'}
        if any(op not in supported for _, op in content.operations):
            raise ValueError('Unexpected operation in the source cut layer')
        if any(args[:4] != [1, 0, 0, -1] for args, op in content.operations if op == b'cm'):
            raise ValueError('The source cut layer uses a scaled transform')
        content.operations = [
            ([FloatObject(CUT_WIDTH)], b'w'),
            ([NumberObject(1), NumberObject(0), NumberObject(0)], b'RG'),
            *((args, op) for args, op in content.operations if op not in (b'K', b'w')),
        ]
        form.set_data(content.get_data())
    contents = ContentStream(None, writer)
    contents.operations = [draw]
    page.replace_contents(contents)
    page['/Resources'].pop(NameObject('/Properties'), None)
    writer.compress_identical_objects(remove_unreferenced=True)
    stream = BytesIO()
    writer.write(stream)
    return fitz.open(stream=stream.getvalue(), filetype='pdf')


def layer_bounds(layers):
    bounds = fitz.Rect()
    for doc in layers.values():
        for _, rect in doc[0].get_bboxlog():
            bounds |= fitz.Rect(rect)
    return bounds


def save_png(page, path):
    pix = page.get_pixmap(dpi=DPI, alpha=True)
    # MuPDF stores premultiplied RGBA internally. Its PNG encoder restores
    # straight alpha for print applications.
    pix.save(path)
    with Image.open(path) as png:
        assert png.mode == 'RGBA' and png.getpixel((0, 0))[3] == 0
        assert png.size == (7560, 2658)
        assert all(abs(value - DPI) < .1 for value in png.info['dpi'])
        assert png.getchannel('A').getextrema() == (0, 255)


def mark_pdf_layers(page, layer_streams):
    """Use page-level optional content, which VectorCraft imports as layers."""
    doc = page.parent
    resources = int(doc.xref_get_key(page.xref, 'Resources')[1].split()[0])
    properties = ' '.join(f'/L{layer} {layer} 0 R' for layer in layer_streams)
    doc.xref_set_key(resources, 'Properties', f'<< {properties} >>')
    marked = [
        f'/OC /L{layer} BDC\n'.encode() + b'\n'.join(streams) + b'\nEMC'
        for layer, streams in layer_streams.items()
    ]
    content = page.get_contents()[0]
    page.set_contents(content)
    doc.update_stream(content, b'\n'.join(marked))


def save_vectorcraft(master, print_layer, cut_layer, white_layer):
    with TemporaryDirectory() as temp:
        source = Path(temp) / 'Additional acrylic sheet.pdf'
        # VectorCraft imports artwork from visible PDF layers. Hide the plates
        # after import so the native file opens ready for color printing.
        master.set_layer(-1, basestate='ON', on=[print_layer, cut_layer, white_layer], off=[])
        master.save(source, garbage=4, deflate=True)
        result = runvc(['run', '--in', source, '--cmd', 'document.inspect'])
        doc = json.loads(result.splitlines()[-1])['result']
        layers = {layer['name']: layer for layer in doc['layers']}
        assert {name: len(layer['children']) for name, layer in layers.items()} == {
            'PRINT_ARTWORK': 32, 'LASER_CUT': 34, 'WHITE_INK_MASK': 4,
        }
        commands = [
            {'command': 'document.setUnits', 'params': {'units': 'Millimeters'}},
            {'command': 'layer.setProps', 'params': {
                'ids': [layers[name]['id'] for name in ('LASER_CUT', 'WHITE_INK_MASK')],
                'visible': False, 'printable': False,
            }},
            {'command': 'document.save', 'params': {
                'path': str(OUT / '05_MASTER.vectorcraft'), 'format': 'vectorcraft',
            }},
        ]
        job = Path(temp) / 'export.json'
        job.write_text(json.dumps(commands), encoding='utf-8')
        runvc(['run', '--in', source, '--commands', job])


def build(keyring, yun):
    with ExitStack() as stack:
        sheets = []
        for source, layer_names in (
            (keyring, ('인쇄', '칼선')),
            (yun, ('인쇄', '화이트', '칼선')),
        ):
            reader = PdfReader(source)
            if len(reader.pages) != 1 or reader.pages[0].rotation != 0:
                raise ValueError(f'Expected a single unrotated artboard: {source}')
            layers = {name: stack.enter_context(export_layer(reader, name)) for name in layer_names}
            sheets.append((layers, layer_bounds(layers)))

        placed = []
        for i, (layers, clip) in enumerate(sheets):
            x = 10 * mm if i == 0 else (WIDTH - 10) * mm - clip.width
            y = (HEIGHT * mm - clip.height) / 2
            dest = fitz.Rect(x, y, x + clip.width, y + clip.height)
            if not fitz.Rect(0, 0, WIDTH * mm, HEIGHT * mm).contains(dest) or clip.is_empty:
                raise ValueError('Source layout does not fit at 100%')
            placed.append((layers, clip, dest))
        if placed[1][2].x0 - placed[0][2].x1 < 5 * mm:
            raise ValueError('The two layouts need at least 5 mm between them')

        OUT.mkdir(parents=True, exist_ok=True)
        master, cutting, white = [stack.enter_context(fitz.open()) for _ in range(3)]
        master_page, cut_page, white_page = [
            doc.new_page(width=WIDTH * mm, height=HEIGHT * mm) for doc in (master, cutting, white)
        ]
        print_layer = master.add_ocg('PRINT_ARTWORK')
        cut_layer = master.add_ocg('LASER_CUT', on=False)
        white_layer = master.add_ocg('WHITE_INK_MASK', on=False)
        layer_streams = {layer: [] for layer in (print_layer, cut_layer, white_layer)}
        for layers, clip, dest in placed:
            for name, layer in (('인쇄', print_layer), ('칼선', cut_layer), ('화이트', white_layer)):
                if name in layers:
                    master_page.show_pdf_page(dest, layers[name], 0, clip=clip)
                    layer_streams[layer].append(master.xref_stream(master_page.get_contents()[-1]))
            cut_page.show_pdf_page(dest, layers['칼선'], 0, clip=clip)
            if '화이트' in layers:
                white_page.show_pdf_page(dest, layers['화이트'], 0, clip=clip)

        mark_pdf_layers(master_page, layer_streams)
        # The print layer alone is visible when the combined PDF opens.
        master.set_layer(-1, basestate='OFF', on=[print_layer], off=[cut_layer, white_layer])
        master_path, cut_path = OUT / '01_COMBINED_SHEET.pdf', OUT / '03_CUT_ONLY.pdf'
        master.save(master_path, garbage=4, deflate=True)
        cutting.save(cut_path, garbage=4, deflate=True)
        with fitz.open(master_path) as result, fitz.open(cut_path) as cutter:
            assert len(result) == len(cutter) == 1
            assert result[0].rect == cutter[0].rect == white_page.rect
            assert {g['name']: g['on'] for g in result.get_ocgs().values()} == {
                'PRINT_ARTWORK': True, 'LASER_CUT': False, 'WHITE_INK_MASK': False,
            }
            assert len(result[0].get_image_info()) == 28
            assert {p['layer'] for p in result[0].get_drawings()} == {'PRINT_ARTWORK'}
            paths = cutter[0].get_drawings()
            assert len(paths) == 34
            assert all(
                p['color'] == (1, 0, 0) and p['fill'] is None and abs(p['width'] - CUT_WIDTH) < 1e-6
                for p in paths
            )
            save_png(result[0], OUT / '02_PRINT_300ppi.png')
            save_png(white_page, OUT / '04_WHITE_INK_MASK_300ppi.png')
        save_vectorcraft(master, print_layer, cut_layer, white_layer)
    print(f'Extra acrylic sheet verified: {WIDTH} × {HEIGHT} mm, {OUT}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('keyring', type=Path, help='아크릴키링.ai')
    parser.add_argument('yun', type=Path, help='yun_image.ai')
    args = parser.parse_args()
    build(args.keyring, args.yun)
